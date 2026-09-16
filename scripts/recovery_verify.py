"""Kill only this project's worker, then prove persisted experiment recovery."""

import json
import subprocess
import time
from pathlib import Path

import httpx
from evaldock.config import settings

ROOT = Path(__file__).resolve().parents[1]
client = httpx.Client(
    base_url="http://localhost:5188/api",
    timeout=60,
    headers={"Origin": settings().public_origin, "X-EvalDock-CSRF": "1"},
)


def req(method, path, **kwargs):
    response = client.request(method, path, **kwargs)
    response.raise_for_status()
    return response.json()


def main():
    req(
        "POST",
        "/auth/login",
        json={"email": "demo@evaldock.local", "password": settings().demo_password},
    )
    verification = json.loads((ROOT / "docs" / "verification.json").read_text())
    project_id = verification["integrations"][0]["project_id"]
    project = req("GET", f"/projects/{project_id}")
    source = next(
        r
        for r in project["resources"]
        if r["kind"] == "dataset" and r["name"] == "Product evidence"
    )
    cases = req("GET", f"/versions/{source['versions'][0]['id']}")["cases"][:10]
    for case in cases:
        case["input"]["delay_ms"] = 1200
    dataset = req(
        "POST",
        f"/projects/{project_id}/resources",
        json={
            "kind": "dataset",
            "name": f"Recovery verification {int(time.time())}",
            "config": {},
            "cases": cases,
        },
    )["version"]["id"]
    target = next(
        r for r in project["resources"] if r["kind"] == "target" and "baseline" in r["name"]
    )["versions"][0]["id"]
    suite = next(
        r for r in project["resources"] if r["kind"] == "suite" and r["name"] == "Release criteria"
    )["versions"][0]["id"]
    experiment = req(
        "POST",
        f"/projects/{project_id}/experiments",
        json={
            "name": "Worker recovery · SIGKILL verification",
            "dataset_version_id": dataset,
            "target_version_id": target,
            "suite_version_id": suite,
            "concurrency": 2,
        },
    )
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        result = req("GET", f"/experiments/{experiment['id']}")
        completed = [e["id"] for e in result["executions"] if e["status"] == "completed"]
        running = [e for e in result["executions"] if e["status"] == "running"]
        if len(completed) >= 2 and running:
            break
        time.sleep(0.2)
    else:
        raise AssertionError("No suitable in-flight state for recovery test")
    subprocess.run(
        ["docker", "compose", "kill", "-s", "SIGKILL", "worker"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["docker", "compose", "up", "-d", "--no-build", "worker"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    start = time.monotonic()
    while time.monotonic() - start < 150:
        result = req("GET", f"/experiments/{experiment['id']}")
        if result["status"] not in {"queued", "running"}:
            break
        time.sleep(1)
    assert result["status"] == "completed", result["status"]
    attempts = []
    for execution in result["executions"]:
        detail = req("GET", f"/executions/{execution['id']}")
        target_attempts = [a for a in detail["attempts"] if a["phase"] == "target"]
        if execution["id"] in completed:
            assert len(target_attempts) == 1, "Completed work was executed again"
        attempts.extend(target_attempts)
    interrupted = sum(a["status"] == "interrupted" for a in attempts)
    assert interrupted > 0, "Expected persisted interrupted attempt evidence"
    # Deliver the already-completed experiment once again through the actual queue.
    before = httpx.get("http://localhost:8099/health").json()["calls_since_process_start"]
    code = (
        "import asyncio; from evaldock.worker import queue, experiment_job\nasync def run():\n async with queue.open_async():\n  await experiment_job.configure(lock='experiment:"
        + experiment["id"]
        + "').defer_async(experiment_id='"
        + experiment["id"]
        + "')\nasyncio.run(run())"
    )
    subprocess.run(["uv", "run", "python", "-c", code], cwd=ROOT, check=True, capture_output=True)
    time.sleep(5)
    after = httpx.get("http://localhost:8099/health").json()["calls_since_process_start"]
    assert before == after
    verification["worker_recovery"] = {
        "experiment_id": experiment["id"],
        "signal": "SIGKILL",
        "status": result["status"],
        "completed_before_kill": len(completed),
        "interrupted_attempts": interrupted,
        "recovery_seconds": round(time.monotonic() - start, 1),
        "duplicate_delivery_target_calls": after - before,
        "execution_count": len(result["executions"]),
    }
    (ROOT / "docs" / "verification.json").write_text(json.dumps(verification, indent=2))
    print(json.dumps(verification["worker_recovery"], indent=2), flush=True)


if __name__ == "__main__":
    main()
