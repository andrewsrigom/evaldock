"""Publish and verify an immutable public-source pilot through EvalDock's API.

No direct database writes, model requests or fabricated human reviews. Reruns
reuse matching versions and experiments; divergence requires a new pack version.
"""

import hashlib
import json
import math
import time
from pathlib import Path

import httpx
from evaldock.config import settings
from evaldock.contracts import EvaluatorConfig, parse_jsonl

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "calibration/catalog-public-v1"
NAME = "Catalog extraction · public-source pilot"
DESCRIPTION = "catalog-public-v1 | 12 real products represented by curated manufacturer facts. Actual offline rule-based outputs; no model or external project integration. Assistant-reviewed references; independent human review pending."
STATE = ROOT / "work/catalog-public-v1-state.json"
REPORT = ROOT / "docs/catalog-public-v1.json"


def read(name):
    return json.loads((PACK / name).read_text())


def main():
    manifest = read("manifest.json")
    for name, digest in manifest["sha256"].items():
        assert hashlib.sha256((PACK / name).read_bytes()).hexdigest() == digest, name
    assert (
        hashlib.sha256((ROOT / "examples/catalog_rules.py").read_bytes()).hexdigest()
        == manifest["implementation_sha256"]
    )
    datasets = {}
    for split in ("calibration", "validation"):
        rows, errors = parse_jsonl((PACK / f"{split}.jsonl").read_text())
        assert not errors, errors
        assert len(rows) == manifest[split]
        datasets[split] = rows
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    config = settings()

    def checkpoint():
        STATE.parent.mkdir(exist_ok=True)
        STATE.write_text(json.dumps(state, indent=2) + "\n")

    with httpx.Client(
        base_url=config.public_origin + "/api",
        timeout=60,
        headers={"Origin": config.public_origin, "X-EvalDock-CSRF": "1"},
    ) as client:

        def request(method, path, **kwargs):
            response = client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()

        request(
            "POST",
            "/auth/login",
            json={"email": "demo@evaldock.local", "password": config.demo_password},
        )
        projects = request("GET", "/projects")
        prior_ids = {p["id"] for p in projects}
        matching = [p for p in projects if p["name"] == NAME]
        assert len(matching) <= 1, "Ambiguous pilot project"
        project = (
            matching[0]
            if matching
            else request(
                "POST",
                "/projects",
                json={
                    "workspace_id": next(
                        p["workspace_id"] for p in projects if p["name"] == "Catalog extraction"
                    ),
                    "name": NAME,
                    "description": DESCRIPTION,
                },
            )
        )
        assert project["description"] == DESCRIPTION, "Project provenance changed"
        project_id = project["id"]
        assert not state.get("project_id") or state["project_id"] == project_id
        state["project_id"] = project_id
        checkpoint()
        detail = request("GET", f"/projects/{project_id}")

        def resource(kind, name, content, cases=None):
            matches = [r for r in detail["resources"] if r["name"] == name and r["kind"] == kind]
            assert len(matches) <= 1, name
            if matches:
                assert len(matches[0]["versions"]) == 1, "Published pack was revised"
                current = request("GET", f"/versions/{matches[0]['versions'][0]['id']}")
                assert all(current["config"].get(k) == v for k, v in content.items()), name
                if cases:
                    assert {row["case_id"]: row for row in current["cases"]} == {
                        row["case_id"]: row for row in cases
                    }, name
                return current["id"]
            payload = {"kind": kind, "name": name, "config": content}
            if cases:
                payload["cases"] = cases
            return request("POST", f"/projects/{project_id}/resources", json=payload)["version"][
                "id"
            ]

        versions = {
            split: resource(
                "dataset",
                f"{split.title()} · {len(rows)} public-source cases v1",
                {
                    "held_out": split == "validation",
                    "description": f"{split.title()}; curated manufacturer facts, assistant-reviewed references. Separate validation is visible, not blind. See catalog-public-v1/RUBRIC.md.",
                },
                rows,
            )
            for split, rows in datasets.items()
        }
        ev_ids = [
            resource(
                "evaluator", ev["name"], EvaluatorConfig.model_validate(ev["config"]).model_dump()
            )
            for ev in read("evaluators.json")
        ]
        suite = resource(
            "suite",
            "Catalog public-source criteria v1",
            {
                "evaluator_version_ids": ev_ids,
                "description": "Six deterministic checks on canonical extraction. Pilot acceptance, not calibrated model quality.",
            },
        )
        current_gate = request("GET", f"/projects/{project_id}/gate")
        gate = read("gate.json")
        assert not current_gate["min_accuracy"] or current_gate == gate, "Gate was revised"
        if current_gate != gate:
            request("PUT", f"/projects/{project_id}/gate", json=gate)
        target_calls_before = httpx.get("http://localhost:8099/health").json()[
            "calls_since_process_start"
        ]

        def run(split, kind, baseline_name):
            title = (
                "Naive first-mention baseline"
                if kind == "baseline"
                else "Scoped specification candidate"
            )
            name = f"{title} · {split} v1"
            imported = read(f"{split}-{kind}-outputs.json")["outputs"]
            existing = [e for e in detail["experiments"] if e["name"] == name]
            assert len(existing) <= 1
            if existing:
                experiment = existing[0]
                assert (
                    experiment["dataset_version_id"] == versions[split]
                    and experiment["suite_version_id"] == suite
                )
            else:
                experiment = request(
                    "POST",
                    f"/projects/{project_id}/experiments",
                    json={
                        "name": name,
                        "dataset_version_id": versions[split],
                        "suite_version_id": suite,
                        "mode": "imported",
                        "import_dataset_version_id": versions[split],
                        "imports": imported,
                        "repetitions": 1,
                        "concurrency": 2,
                        "baseline_name": baseline_name,
                    },
                )
            state[f"{split}_{kind}"] = experiment["id"]
            checkpoint()
            deadline = time.monotonic() + 120
            while True:
                result = request("GET", f"/experiments/{experiment['id']}")
                if result["status"] not in {"queued", "running"}:
                    break
                assert time.monotonic() < deadline, "Worker timeout"
                time.sleep(0.5)
            assert result["status"] == "completed"
            assert len(result["executions"]) == len(datasets[split])
            output_by_id = {o["case_id"]: o["output"] for o in imported}
            references = {c["case_id"]: c["expected"] for c in datasets[split]}
            for execution in result["executions"]:
                actual = output_by_id[execution["case_id"]]
                expected = references[execution["case_id"]]
                assert execution["output"] == actual
                assert execution["target_latency_ms"] is None and not execution["reviews"]
                decisions = {
                    f"{field}_correct": float(actual[key] == expected[key])
                    for field, key in [
                        ("material", "material"),
                        ("weight", "weight_g"),
                        ("country", "country"),
                    ]
                }
                decisions.update(
                    schema_valid=1.0,
                    record_exact=float(actual == expected),
                    field_accuracy=sum(decisions.values()) / 3,
                )
                assert len(execution["results"]) == 6
                for metric in execution["results"]:
                    assert metric["status"] == "scored"
                    assert math.isclose(metric["score"], decisions[metric["metric_key"]]), metric
                    assert metric["passed"] == (decisions[metric["metric_key"]] == 1)
            assert result["calibration"]["reviewed_decisions"] == 0
            assert result["calibration"]["agreement"] is None
            for metric in result["summary"]["metrics"].values():
                assert metric["coverage"] == 1 and metric["scored"] == len(datasets[split])
            return result

        runs = {}
        # Immutable configuration and actual saved outputs are frozen before all runs.
        for split in ("validation", "calibration"):
            baseline_name = "main" if split == "calibration" else "public-validation-v1"
            baseline = run(split, "baseline", baseline_name)
            pinned = next((b for b in detail["baselines"] if b["name"] == baseline_name), None)
            assert not pinned or pinned["experiment_id"] == baseline["id"]
            if not pinned:
                request(
                    "POST",
                    f"/projects/{project_id}/baselines",
                    json={"experiment_id": baseline["id"], "name": baseline_name},
                )
            candidate = run(split, "candidate", baseline_name)
            assert candidate["baseline_id"] == baseline["id"]
            comparison = request(
                "GET",
                "/compare",
                params={
                    "baseline": baseline["id"],
                    "candidate": candidate["id"],
                    "metric": "record_exact",
                },
            )
            gate_result = request(
                "GET", f"/experiments/{candidate['id']}/gate", params={"metric": "record_exact"}
            )
            artifact_key = f"{split}_artifact"
            if not state.get(artifact_key):
                state[artifact_key] = request(
                    "POST",
                    f"/experiments/{candidate['id']}/artifacts",
                    params={"metric": "record_exact"},
                )["id"]
                checkpoint()
            stored = request("GET", f"/artifacts/{state[artifact_key]}")
            assert stored["id"] == candidate["id"] and stored["gate"] == gate_result
            runs[split] = {
                "cases": len(datasets[split]),
                "dataset_version_id": versions[split],
                "baseline_id": baseline["id"],
                "candidate_id": candidate["id"],
                "baseline_metrics": baseline["summary"]["metrics"],
                "candidate_metrics": candidate["summary"]["metrics"],
                "paired_counts": comparison["counts"],
                "gate": gate_result,
                "artifact_id": state[artifact_key],
            }
            print(
                f"{split}: {comparison['counts']}; gate exit {gate_result['exit_code']}", flush=True
            )
        target_calls_after = httpx.get("http://localhost:8099/health").json()[
            "calls_since_process_start"
        ]
        assert target_calls_after == target_calls_before
        assert prior_ids <= {p["id"] for p in request("GET", "/projects")}
        result = {
            "pack": manifest["pack"],
            "project_id": project_id,
            "project_url": f"{config.public_origin}/projects/{project_id}/overview",
            "language": "en-US",
            "source_type": manifest["source_type"],
            "blind_validation": False,
            "human_approved": False,
            "live_model_calls": 0,
            "sample_target_calls": 0,
            "execution_count": 24,
            "metric_decisions_verified": 144,
            "suite_version_id": suite,
            "implementation_sha256": manifest["implementation_sha256"],
            "pack_manifest_sha256": hashlib.sha256(
                (PACK / "manifest.json").read_bytes()
            ).hexdigest(),
            "runs": runs,
        }
        REPORT.write_text(json.dumps(result, indent=2) + "\n")
        request("POST", "/auth/logout")
        print(json.dumps({"project_id": project_id, "verified_decisions": 144, "model_calls": 0}))


if __name__ == "__main__":
    main()
