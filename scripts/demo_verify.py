"""Exercise both fixture integrations through the public API and live worker.

Never reports fixtures as model quality. Writes a machine-readable verification record.
"""

import json
import os
import subprocess
import time
from pathlib import Path

import httpx
from evaldock.config import settings

ROOT = Path(__file__).resolve().parents[1]
client = httpx.Client(
    base_url="http://localhost:5188",
    timeout=130,
    headers={"Origin": settings().public_origin, "X-EvalDock-CSRF": "1"},
)


def request(method, path, **kwargs):
    response = client.request(method, "/api" + path, **kwargs)
    response.raise_for_status()
    return response.json()


def wait(experiment_id, timeout=180):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = request("GET", f"/experiments/{experiment_id}")
        if result["status"] not in {"queued", "running"}:
            return result
        time.sleep(1)
    raise AssertionError(f"Experiment {experiment_id} did not finish")


def main():
    request(
        "POST",
        "/auth/login",
        json={"email": "demo@evaldock.local", "password": settings().demo_password},
    )
    projects = request("GET", "/projects")
    verification = {"fixture_mode": True, "real_model_evaluation": False, "integrations": []}
    for project in projects:
        if not project["fixture"]:
            continue
        detail = request("GET", f"/projects/{project['id']}")
        resources = detail["resources"]

        def version(kind, part):
            return next(r for r in resources if r["kind"] == kind and part in r["name"])[
                "versions"
            ][0]["id"]

        dataset = version("dataset", "")
        suite = version("suite", "Release")
        params = {
            "dataset_version_id": dataset,
            "suite_version_id": suite,
            "concurrency": 2,
            "repetitions": 2,
        }
        baseline = request(
            "POST",
            f"/projects/{project['id']}/experiments",
            json={
                **params,
                "name": "Baseline · release v1",
                "target_version_id": version("target", "baseline"),
            },
        )
        base = wait(baseline["id"])
        assert base["status"] == "completed", base["summary"]
        request("POST", f"/projects/{project['id']}/baselines", json={"experiment_id": base["id"]})
        candidate = request(
            "POST",
            f"/projects/{project['id']}/experiments",
            json={
                **params,
                "name": "Candidate · release v2",
                "target_version_id": version("target", "candidate"),
            },
        )
        result = wait(candidate["id"])
        assert result["status"] == "completed", result["summary"]
        comparison = request(
            "GET",
            "/compare",
            params={"baseline": base["id"], "candidate": result["id"], "metric": "field_accuracy"},
        )
        assert comparison["counts"]["improved"] > 0 and comparison["counts"]["regressed"] > 0
        regressed = next(row for row in comparison["rows"] if row["state"] == "regressed")
        case = request("GET", f"/executions/{regressed['candidate']['id']}")
        assert case["attempts"] and case["output_present"]
        request(
            "POST",
            f"/executions/{case['id']}/reviews",
            json={
                "metric_key": "field_accuracy",
                "passed": True,
                "note": "Calibration example: human accepts this case despite the automated field mismatch. Preserve both decisions.",
            },
        )
        reviewed = request("GET", f"/experiments/{result['id']}")
        assert reviewed["calibration"]["disagreements"]
        gate = request(
            "GET", f"/experiments/{result['id']}/gate", params={"metric": "field_accuracy"}
        )
        assert gate["exit_code"] == 1
        before = httpx.get("http://localhost:8099/health").json()["calls_since_process_start"]
        rescore = request(
            "POST",
            f"/experiments/{result['id']}/rescore",
            json={
                "suite_version_id": version("suite", "Judge"),
                "name": "Judge calibration · saved outputs",
            },
        )
        rescored = wait(rescore["id"])
        assert rescored["status"] == "completed"
        after = httpx.get("http://localhost:8099/health").json()["calls_since_process_start"]
        assert before == after
        assert all(e["target_latency_ms"] is None for e in rescored["executions"])
        artifact = request(
            "POST", f"/experiments/{result['id']}/artifacts", params={"metric": "field_accuracy"}
        )
        assert request("GET", f"/artifacts/{artifact['id']}")["gate"]["exit_code"] == 1
        token = request(
            "POST",
            "/tokens",
            json={
                "workspace_id": project["workspace_id"],
                "name": "Temporary CI verification",
                "scopes": ["read", "write"],
                "days": 1,
            },
        )
        env = {
            **os.environ,
            "EVALDOCK_TOKEN": token["token"],
            "EVALDOCK_URL": "http://localhost:5188",
        }
        cli = subprocess.run(
            ["uv", "run", "evaldock", "gate", result["id"], "--metric", "field_accuracy"],
            env=env,
            capture_output=True,
            text=True,
        )
        assert cli.returncode == 1 and json.loads(cli.stdout)["exit_code"] == 1, (
            "CLI gate did not return a quality failure"
        )
        for fmt in ["json", "junit"]:
            exported = subprocess.run(
                [
                    "uv",
                    "run",
                    "evaldock",
                    "export",
                    result["id"],
                    str(
                        ROOT
                        / "docs"
                        / f"{project['name'].split()[0].lower()}-report.{'xml' if fmt == 'junit' else 'json'}"
                    ),
                    "--format",
                    fmt,
                ],
                env=env,
                capture_output=True,
                text=True,
            )
            if exported.returncode:
                print(exported.stderr.replace(token["token"], "[REDACTED]"), flush=True)
                raise AssertionError("CLI report export failed")
        request("DELETE", f"/tokens/{token['id']}")
        verification["integrations"].append(
            {
                "project": project["name"],
                "project_id": project["id"],
                "baseline": base["id"],
                "candidate": result["id"],
                "rescore": rescore["id"],
                "case_count": 24,
                "executions_per_run": 48,
                "paired_counts": comparison["counts"],
                "gate_exit_code": cli.returncode,
                "rescore_target_calls": after - before,
                "human_disagreements": len(reviewed["calibration"]["disagreements"]),
            }
        )
        print(project["name"], comparison["counts"], "CI exit", cli.returncode, flush=True)
    # Imported tool traces include an explicit missing output, never a fabricated latency.
    project = projects[0]
    case_rows = [
        json.loads(line)
        for line in (ROOT / "fixtures" / "agent-cases.jsonl").read_text().splitlines()
    ]
    dataset = request(
        "POST",
        f"/projects/{project['id']}/resources",
        json={
            "kind": "dataset",
            "name": f"Agent trace example {int(time.time())}",
            "config": {},
            "cases": case_rows,
        },
    )["version"]["id"]
    ev = request(
        "POST",
        f"/projects/{project['id']}/resources",
        json={
            "kind": "evaluator",
            "name": f"Tool trace assertions {int(time.time())}",
            "config": {
                "kind": "tool_calls",
                "metric_key": "tool_safety",
                "config": {
                    "required": ["lookup_order"],
                    "forbidden": ["delete_order"],
                    "order": ["lookup_order", "respond"],
                    "arguments": {"lookup_order": {"type": "object", "required": ["order_id"]}},
                },
            },
        },
    )["version"]["id"]
    suite = request(
        "POST",
        f"/projects/{project['id']}/resources",
        json={
            "kind": "suite",
            "name": f"Observable agent trace {int(time.time())}",
            "config": {"evaluator_version_ids": [ev]},
        },
    )["version"]["id"]
    outputs = json.loads((ROOT / "fixtures" / "agent-outputs.json").read_text())["outputs"]
    imported = request(
        "POST",
        f"/projects/{project['id']}/experiments",
        json={
            "name": "Imported agent trace · missing output visible",
            "dataset_version_id": dataset,
            "suite_version_id": suite,
            "mode": "imported",
            "import_dataset_version_id": dataset,
            "imports": outputs,
        },
    )
    result = wait(imported["id"])
    assert result["status"] == "partially_failed" and result["summary"]["total"] == 3
    assert result["summary"]["metrics"]["tool_safety"]["coverage"] == 2 / 3
    verification["imported_trace"] = {
        "experiment_id": imported["id"],
        "status": result["status"],
        "coverage": 2 / 3,
    }
    (ROOT / "docs" / "verification.json").write_text(json.dumps(verification, indent=2))
    print("Demo workflows verified; docs/verification.json written", flush=True)


if __name__ == "__main__":
    main()
