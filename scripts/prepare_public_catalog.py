"""Build the public-source pilot and actual offline extractor outputs, without network calls."""

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "calibration/catalog-public-v1"
IMPLEMENTATION = ROOT / "examples/catalog_rules.py"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(name, data):
    (PACK / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def main():
    sources = json.loads((PACK / "sources.json").read_text())
    spec = importlib.util.spec_from_file_location("catalog_rules", IMPLEMENTATION)
    rules = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rules)
    implementation_hash = digest(IMPLEMENTATION)
    for split in ("calibration", "validation"):
        cases = []
        outputs = {"baseline": [], "candidate": []}
        for source in sources:
            if source["split"] != split:
                continue
            case_id = "public-v1-" + source["key"]
            cases.append(
                {
                    "case_id": case_id,
                    "input": {"passage": source["passage"]},
                    "expected": source["expected"],
                    "context": {
                        "product": source["title"],
                        "source_url": source["url"],
                        "observed_on": source["observed_on"],
                        "evidence_scope": source["evidence_scope"],
                        "reference_passage": source["passage"],
                        "label_rationale": source["rationale"],
                        "rubric_version": "catalog-public-v1",
                        "assistant_review_status": "reviewed",
                        "human_review_status": "pending",
                    },
                    "tags": ["public-source", "curated-paraphrase", split, source["challenge"]],
                    "slices": {
                        "brand": "TOAKS" if source["key"].startswith("toaks") else "Nalgene",
                        "challenge": source["challenge"],
                        "split": split,
                        "language": "en-US",
                    },
                    "acceptance_criteria": source["rationale"],
                    "references": [source["url"]],
                }
            )
            for kind in outputs:
                # Crucially, the extractor only receives input.passage, never the reference.
                output = getattr(rules, kind)(source["passage"])
                outputs[kind].append(
                    {
                        "case_id": case_id,
                        "replicate": 0,
                        "output": output,
                        "metadata": {
                            "producer": f"offline-rules-{kind}-v1",
                            "implementation_sha256": implementation_hash,
                            "input_sha256": hashlib.sha256(source["passage"].encode()).hexdigest(),
                            "live_model": False,
                        },
                    }
                )
        (PACK / f"{split}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in cases))
        for kind, rows in outputs.items():
            write_json(f"{split}-{kind}-outputs.json", {"outputs": rows})
    evaluators = json.loads((ROOT / "calibration/catalog-v2/evaluators.json").read_text())
    for ev in evaluators:
        ev["name"] = ev["name"].replace("catalog v2", "public-source v1")
    write_json("evaluators.json", evaluators)
    write_json("gate.json", json.loads((ROOT / "calibration/catalog-v2/gate.json").read_text()))
    write_json(
        "manifest.json",
        {
            "pack": "catalog-public-v1",
            "case_count": 12,
            "calibration": 8,
            "validation": 4,
            "source_type": "curated manufacturer factual paraphrases",
            "human_approved": False,
            "blind_validation": False,
            "live_model_calls": 0,
            "implementation_sha256": implementation_hash,
            "sha256": {
                p.name: digest(p) for p in sorted(PACK.iterdir()) if p.name != "manifest.json"
            },
        },
    )
    print("Prepared 12 public-source cases and 24 actual offline outputs; no model calls.")


if __name__ == "__main__":
    main()
