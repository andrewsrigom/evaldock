"""Load and verify catalog-v1 through the public API; no targets, models or human reviews.

Reuses this pack's resources and runs on subsequent invocations. Stops on divergence.
Credentials are read from the local .env via Settings and never written to reports.
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
PACK = ROOT / "calibration" / "catalog-v1"
NAME = "Calibração de catálogo · sintética v1"
DESCRIPTION = "catalog-v1 | 40 casos sintéticos: 30 calibração + 10 validação. Referências propostas pelo assistente; aprovação humana pendente. Execuções de controle importadas; nenhuma IA ou integração externa."
STATE = ROOT / "work" / "catalog-calibration-state.json"
REPORT = ROOT / "docs" / "catalog-calibration-v1.json"


def read(name):
    return json.loads((PACK / name).read_text(encoding="utf-8"))


def main():
    manifest = read("manifest.json")
    for name, checksum in manifest["sha256"].items():
        assert hashlib.sha256((PACK / name).read_bytes()).hexdigest() == checksum, name
    datasets = {}
    for split in ("calibration", "validation"):
        cases, errors = parse_jsonl((PACK / f"{split}.jsonl").read_text())
        assert not errors, errors
        datasets[split] = cases
    assert not (
        {c["case_id"] for c in datasets["calibration"]}
        & {c["case_id"] for c in datasets["validation"]}
    )
    oracle = {r["case_id"]: r["expected_metrics"] for r in read("expected-decisions.json")}
    config = settings()
    state = json.loads(STATE.read_text()) if STATE.exists() else {}

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
        original_ids = {
            p["id"] for p in projects if p["name"] in {"Catalog extraction", "Support triage"}
        }
        assert len(original_ids) == 2
        project = next((p for p in projects if p["name"] == NAME), None)
        if project is None:
            workspace_id = next(
                p["workspace_id"] for p in projects if p["name"] == "Catalog extraction"
            )
            project = request(
                "POST",
                "/projects",
                json={"workspace_id": workspace_id, "name": NAME, "description": DESCRIPTION},
            )
            state["project_id"] = project["id"]
            checkpoint()
        assert project["description"] == DESCRIPTION, (
            "Existing project has a different provenance; stop."
        )
        project_id = project["id"]
        assert not state.get("project_id") or state["project_id"] == project_id
        state["project_id"] = project_id
        checkpoint()
        detail = request("GET", f"/projects/{project_id}")

        def resource(kind, name, content, cases=None):
            matches = [r for r in detail["resources"] if r["name"] == name and r["kind"] == kind]
            assert len(matches) <= 1, "Ambiguous resource"
            if matches:
                current = request("GET", f"/versions/{matches[0]['versions'][0]['id']}")
                assert len(matches[0]["versions"]) == 1, (
                    "Pack was revised; create a new pack version."
                )
                assert all(current["config"].get(k) == v for k, v in content.items()), name
                if cases:
                    assert current["cases"] == cases, name
                return current["id"]
            payload = {"kind": kind, "name": name, "config": content}
            if cases:
                payload["cases"] = cases
            created = request("POST", f"/projects/{project_id}/resources", json=payload)
            checkpoint()
            return created["version"]["id"]

        versions = {}
        for split, rows in datasets.items():
            title = (
                "Calibração · 30 casos sintéticos v1"
                if split == "calibration"
                else "Validação reservada · 10 casos sintéticos v1"
            )
            versions[split] = resource(
                "dataset",
                title,
                {
                    "held_out": split == "validation",
                    "description": f"catalog-v1: {split}; referências propostas pelo assistente, sem aprovação humana. Ver RUBRIC.md e human-review.csv.",
                },
                rows,
            )
            exported = request("GET", f"/versions/{versions[split]}")
            assert exported["cases"] == rows
        evaluator_ids = [
            resource(
                "evaluator", ev["name"], EvaluatorConfig.model_validate(ev["config"]).model_dump()
            )
            for ev in read("evaluators.json")
        ]
        suite = resource(
            "suite",
            "Critérios determinísticos · catálogo v1",
            {
                "evaluator_version_ids": evaluator_ids,
                "description": "Seis critérios objetivos. Controles sintéticos; não mede qualidade de modelo nem aprovação humana.",
            },
        )
        current_gate = request("GET", f"/projects/{project_id}/gate")
        gate = read("gate.json")
        assert not current_gate["min_accuracy"] or current_gate == gate, (
            "Existing gate changed; stop."
        )
        if current_gate != gate:
            request("PUT", f"/projects/{project_id}/gate", json=gate)
        before = httpx.get("http://localhost:8099/health").json()["calls_since_process_start"]
        runs = {}

        def run(split, kind, title, baseline_name):
            name = f"{title} · {'30 calibração' if split == 'calibration' else '10 validação'} v1"
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
                        "imports": read(f"{split}-{kind}-outputs.json")["outputs"],
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
            assert result["status"] == "completed", result["status"]
            assert len(result["executions"]) == len(datasets[split])
            inputs = {o["case_id"]: o for o in read(f"{split}-{kind}-outputs.json")["outputs"]}
            for execution in result["executions"]:
                assert execution["output"] == inputs[execution["case_id"]]["output"]
                assert execution["target_latency_ms"] is None
                assert not execution["reviews"]
                assert len(execution["results"]) == 6
                for metric in execution["results"]:
                    expected = (
                        1
                        if kind == "reference"
                        else oracle[execution["case_id"]][metric["metric_key"]]
                    )
                    assert metric["status"] == "scored"
                    assert math.isclose(metric["score"], expected), (
                        execution["case_id"],
                        metric,
                        expected,
                    )
                    assert metric["passed"] == (expected == 1)
            assert result["calibration"]["reviewed_decisions"] == 0
            assert result["calibration"]["agreement"] is None
            for metric in result["summary"]["metrics"].values():
                assert metric["coverage"] == 1 and metric["scored"] == len(datasets[split])
            return result

        # The suite and oracle are frozen before either split is executed.
        for split in ("validation", "calibration"):
            baseline_name = "main" if split == "calibration" else "validation-v1"
            baseline = run(
                split, "reference", "Referência sintética · controle positivo", baseline_name
            )
            existing_baseline = next(
                (b for b in detail["baselines"] if b["name"] == baseline_name), None
            )
            assert not existing_baseline or existing_baseline["experiment_id"] == baseline["id"]
            if not existing_baseline:
                request(
                    "POST",
                    f"/projects/{project_id}/baselines",
                    json={"experiment_id": baseline["id"], "name": baseline_name},
                )
            challenge = run(
                split, "challenge", "Falhas injetadas · controle negativo", baseline_name
            )
            assert challenge["baseline_id"] == baseline["id"]
            comparison = request(
                "GET",
                "/compare",
                params={
                    "baseline": baseline["id"],
                    "candidate": challenge["id"],
                    "metric": "record_exact",
                },
            )
            failures = manifest["expected_challenge_failures"][split]
            assert comparison["counts"]["regressed"] == failures
            assert comparison["counts"].get("improved", 0) == 0
            gate_result = request(
                "GET", f"/experiments/{challenge['id']}/gate", params={"metric": "record_exact"}
            )
            assert gate_result["exit_code"] == 1
            artifact_key = f"{split}_artifact"
            if not state.get(artifact_key):
                state[artifact_key] = request(
                    "POST",
                    f"/experiments/{challenge['id']}/artifacts",
                    params={"metric": "record_exact"},
                )["id"]
                checkpoint()
            stored = request("GET", f"/artifacts/{state[artifact_key]}")
            assert stored["id"] == challenge["id"] and stored["gate"]["exit_code"] == 1
            runs[split] = {
                "dataset_version_id": versions[split],
                "baseline_id": baseline["id"],
                "challenge_id": challenge["id"],
                "artifact_id": state[artifact_key],
                "cases": len(datasets[split]),
                "metrics": challenge["summary"]["metrics"],
                "paired_counts": comparison["counts"],
                "gate": gate_result,
                "reviewed_decisions": 0,
            }
            print(
                f"{split}: reference all pass; {failures} deliberate record failures detected; gate exit 1 as expected.",
                flush=True,
            )
        after = httpx.get("http://localhost:8099/health").json()["calls_since_process_start"]
        assert before == after, "Unexpected calls to sample targets during imported controls"
        current_ids = {p["id"] for p in request("GET", "/projects")}
        assert original_ids <= current_ids
        results = {
            "pack": "catalog-v1",
            "project_id": project_id,
            "project_url": f"{config.public_origin}/projects/{project_id}/overview",
            "synthetic": True,
            "human_approved": False,
            "live_model_calls": 0,
            "sample_target_calls": after - before,
            "execution_count": 80,
            "metric_decisions_verified": 480,
            "suite_version_id": suite,
            "pack_manifest_sha256": hashlib.sha256(
                (PACK / "manifest.json").read_bytes()
            ).hexdigest(),
            "runs": runs,
        }
        REPORT.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
        request("POST", "/auth/logout")
        print(
            json.dumps(
                {
                    "project_id": project_id,
                    "verified": 480,
                    "target_calls": 0,
                    "human_review": "pending",
                }
            )
        )


if __name__ == "__main__":
    main()
