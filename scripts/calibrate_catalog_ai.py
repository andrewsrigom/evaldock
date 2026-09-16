"""Run the bounded catalog AI pilot through the public API; never retry model calls."""

import argparse
import copy
import hashlib
import json
import subprocess
import time
from pathlib import Path

import httpx
from evaldock.config import settings
from evaldock.contracts import EvaluatorConfig, TargetConfig, parse_jsonl

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "calibration/catalog-public-v1"
OUT = ROOT / "docs/catalog-ai-v2"
PHASES = ("controls", "calibration", "repeat", "validation")
NAMES = {
    "controls": "AI judge controls v2",
    "calibration": "OpenAI calibration v2",
    "repeat": "OpenAI calibration repeat v2",
    "validation": "OpenAI validation v2",
}
# One deliberately incorrect field per negative control; all remain schema-valid.
MUTATIONS = {
    "public-v1-toaks-750": ("weight_g", 86),
    "public-v1-toaks-550": ("material", "titanium"),
    "public-v1-toaks-450": ("country", "US"),
    "public-v1-toaks-spoon": ("weight_g", 0.65),
    "public-v1-nalgene-wide-32": ("weight_g", 32),
    "public-v1-nalgene-silo": ("country", "CN"),
    "public-v1-nalgene-ultralite-32": ("country", "US"),
    "public-v1-nalgene-cap": ("material", "Tritan Renew"),
}


def read(path):
    return json.loads(path.read_text())


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def save(path, value, secret):
    encoded = json.dumps(value, indent=2, ensure_ascii=False) + "\n"
    assert secret not in encoded, "Secret found in report; refusing to write"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encoded)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("preflight", *PHASES, "summary"))
    args = parser.parse_args()
    cfg = settings()
    secret = cfg.openai_api_key.get_secret_value().strip()
    assert secret and cfg.openai_credential_id, "Configure the server .env first"
    assert (ROOT / ".env").stat().st_mode & 0o777 == 0o600
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).split(b"\0")
    for raw in filter(None, tracked):
        path = ROOT / raw.decode()
        assert path.name != ".env", "The environment file must not be tracked"
        assert secret.encode() not in path.read_bytes(), "Secret found in tracked content"
    compose = json.loads(
        subprocess.check_output(["docker", "compose", "config", "--format", "json"], cwd=ROOT)
    )
    for name, service in compose["services"].items():
        env = service.get("environment", {})
        assert bool(env.get("OPENAI_API_KEY")) == (name in {"api", "worker"}), name
        for port in service.get("ports", []):
            assert port.get("host_ip") == "127.0.0.1", "Public port binding found"
    manifest = read(PACK / "manifest.json")
    for name, expected in manifest["sha256"].items():
        assert hashlib.sha256((PACK / name).read_bytes()).hexdigest() == expected, name
    setup = read(ROOT / "docs/ai-setup.json")
    pilot = read(ROOT / "docs/catalog-public-v1.json")
    preset = read(ROOT / "examples/catalog_ai.json")
    project_id = setup["project_id"]
    with httpx.Client(
        base_url=cfg.public_origin + "/api",
        timeout=30,
        headers={"Origin": cfg.public_origin, "X-EvalDock-CSRF": "1"},
    ) as client:

        def request(method, path, **kwargs):
            response = client.request(method, path, **kwargs)
            response.raise_for_status()
            assert secret not in response.text, "API response exposed a secret"
            return response.json()

        request("GET", "/health")
        request(
            "POST",
            "/auth/login",
            json={
                "email": "demo@evaldock.local",
                "password": cfg.demo_password,
            },
        )
        try:
            detail = request("GET", f"/projects/{project_id}")
            credentials = request("GET", f"/projects/{project_id}/credentials")
            bound = next(c for c in credentials if c["id"] == cfg.openai_credential_id)
            assert bound["source"] == "environment" and bound["configured"]
            versions = {v["id"]: v for r in detail["resources"] for v in r["versions"]}
            target = versions[setup["target_version_id"]]["config"]
            judge = versions[setup["judge_version_id"]]["config"]
            suite = versions[setup["suite_version_id"]]["config"]
            target_preset = {**preset["target"], "credential_id": cfg.openai_credential_id}
            judge_preset = copy.deepcopy(preset["judge"])
            judge_preset["config"]["credential_id"] = cfg.openai_credential_id
            assert target == TargetConfig.model_validate(target_preset).model_dump()
            assert judge == EvaluatorConfig.model_validate(judge_preset).model_dump()
            assert target["max_attempts"] == judge["max_attempts"] == 1
            assert (
                target["max_output_tokens"]
                == judge["config"]["parameters"]["max_output_tokens"]
                == 2000
            )
            assert len(suite["evaluator_version_ids"]) == 7
            assert suite["evaluator_version_ids"][-1] == setup["judge_version_id"]
            datasets = {}
            for split in ("calibration", "validation"):
                rows, errors = parse_jsonl((PACK / f"{split}.jsonl").read_text())
                assert not errors and len(rows) == manifest[split]
                version_id = pilot["runs"][split]["dataset_version_id"]
                actual = request("GET", f"/versions/{version_id}")["cases"]
                assert {c["case_id"]: c for c in actual} == {c["case_id"]: c for c in rows}
                datasets[split] = rows
                baseline_name = "main" if split == "calibration" else "public-validation-v1"
                pinned = next(b for b in detail["baselines"] if b["name"] == baseline_name)
                assert pinned["experiment_id"] == pilot["runs"][split]["baseline_id"]
            imports = []
            for case in datasets["calibration"]:
                wrong = copy.deepcopy(case["expected"])
                field, value = MUTATIONS[case["case_id"]]
                assert wrong[field] != value
                wrong[field] = value
                for replicate, output in enumerate((case["expected"], wrong)):
                    imports.append(
                        {"case_id": case["case_id"], "replicate": replicate, "output": output}
                    )
            plan = {
                "pack": "catalog-ai-v2",
                "model": setup["model"],
                "project_id": project_id,
                "target_version_id": setup["target_version_id"],
                "judge_version_id": setup["judge_version_id"],
                "suite_version_id": setup["suite_version_id"],
                "config_sha256": digest({"target": target, "judge": judge, "suite": suite}),
                "dataset_versions": {s: pilot["runs"][s]["dataset_version_id"] for s in datasets},
                "source_manifest_sha256": hashlib.sha256(
                    (PACK / "manifest.json").read_bytes()
                ).hexdigest(),
                "max_provider_calls": 56,
                "max_output_tokens_per_call": 2000,
                "automatic_model_retries": 0,
                "concurrency": 2,
                "control_imports": imports,
                "control_design": "Replicate 0 is the reviewed reference. Replicate 1 has one incorrect field. Control labels are not sent to the judge.",
                "human_approved": False,
                "blind_validation": False,
                "judge_used_as_release_gate": False,
            }
            if (OUT / "plan.json").exists():
                assert read(OUT / "plan.json") == plan, (
                    "Frozen plan changed; publish a new revision"
                )
            else:
                save(OUT / "plan.json", plan, secret)
            if args.phase == "preflight":
                print(json.dumps({"preflight": "passed", "max_provider_calls": 56}), flush=True)
                return
            if args.phase == "summary":
                reports = {phase: read(OUT / f"{phase}.json") for phase in PHASES}
                first = {e["case_id"]: e for e in reports["calibration"]["executions"]}
                second = {e["case_id"]: e for e in reports["repeat"]["executions"]}
                stable = sum(first[k]["output"] == second[k]["output"] for k in first)
                usage = {
                    "target": {"calls": 0, "input_tokens": 0, "output_tokens": 0},
                    "judge": {"calls": 0, "input_tokens": 0, "output_tokens": 0},
                }
                for report in reports.values():
                    for execution in report["executions"]:
                        usages = [("target", execution.get("metadata", {}).get("target_usage"))]
                        usages += [
                            ("judge", r.get("details", {}).get("judge_usage"))
                            for r in execution["results"]
                        ]
                        for role, measured in usages:
                            if measured:
                                usage[role]["calls"] += 1
                                for key in ("input_tokens", "output_tokens"):
                                    usage[role][key] += measured[key]
                preliminary = read(ROOT / "docs/catalog-ai-v1/controls.json")
                prior_usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0}
                for execution in preliminary["executions"]:
                    for result in execution["results"]:
                        measured = result.get("details", {}).get("judge_usage")
                        if measured:
                            prior_usage["calls"] += 1
                            for key in ("input_tokens", "output_tokens"):
                                prior_usage[key] += measured[key]
                summary = {
                    "completed_at": max(r["finished_at"] for r in reports.values()),
                    "preliminary_controls": {
                        "id": preliminary["id"],
                        "controls": preliminary["controls"],
                        "usage": prior_usage,
                    },
                    "total_provider_calls": prior_usage["calls"]
                    + sum(v["calls"] for v in usage.values()),
                    "evaluator_implementation_sha256": hashlib.sha256(
                        (ROOT / "apps/api/evaldock/evaluators.py").read_bytes()
                    ).hexdigest(),
                    "pack": plan["pack"],
                    "model": plan["model"],
                    "usage": usage,
                    "stable_outputs": stable,
                    "repeat_cases": len(first),
                    "runs": {
                        phase: {
                            "id": report["id"],
                            "url": cfg.public_origin + "/experiments/" + report["id"],
                            "status": report["status"],
                            "summary": report["summary"],
                            "gate": report.get("gate"),
                            "controls": report.get("controls"),
                        }
                        for phase, report in reports.items()
                    },
                    "human_approved": False,
                    "blind_validation": False,
                    "judge_used_as_release_gate": False,
                }
                assert sum(v["calls"] for v in usage.values()) <= plan["max_provider_calls"]
                save(OUT / "summary.json", summary, secret)
                print(
                    json.dumps(
                        {
                            "status": "complete",
                            "stable_outputs": stable,
                            "repeat_cases": len(first),
                            "usage": usage,
                        }
                    ),
                    flush=True,
                )
                return
            phase = args.phase
            # Fail closed between phases; validation never triggers automatic tuning.
            for prior in PHASES[: PHASES.index(phase)]:
                previous = read(OUT / f"{prior}.json")
                assert previous["accepted"], f"Review {prior} before continuing"
            split = "validation" if phase == "validation" else "calibration"
            dataset_id = plan["dataset_versions"][split]
            payload = {
                "name": NAMES[phase],
                "dataset_version_id": dataset_id,
                "suite_version_id": setup["suite_version_id"],
                "concurrency": 2,
                "repetitions": 2 if phase == "controls" else 1,
                "mode": "imported" if phase == "controls" else "http",
                "baseline_name": "public-validation-v1" if split == "validation" else "main",
            }
            if phase == "controls":
                payload.update(import_dataset_version_id=dataset_id, imports=imports)
            else:
                payload.update(
                    target_version_id=setup["target_version_id"],
                    max_target_calls=len(datasets[split]),
                )
            existing = [e for e in detail["experiments"] if e["name"] == payload["name"]]
            assert len(existing) <= 1, "Ambiguous experiment name"
            experiment = (
                existing[0]
                if existing
                else request("POST", f"/projects/{project_id}/experiments", json=payload)
            )
            for key in ("name", "dataset_version_id", "suite_version_id", "mode", "repetitions"):
                assert experiment[key] == payload[key], "Existing run differs from frozen plan"
            assert experiment["target_version_id"] == payload.get("target_version_id")
            print(
                json.dumps(
                    {"phase": phase, "experiment_id": experiment["id"], "reused": bool(existing)}
                ),
                flush=True,
            )
            deadline = time.monotonic() + 600
            while True:
                report = request("GET", f"/experiments/{experiment['id']}")
                if report["status"] not in {"queued", "running"}:
                    break
                if time.monotonic() > deadline:
                    request("POST", f"/experiments/{experiment['id']}/cancel")
                    raise RuntimeError("Timed out; cancellation requested, no automatic retry")
                time.sleep(2)
            metrics = report["summary"]["metrics"]
            complete = report["status"] == "completed" and all(
                m["coverage"] == 1 and not m["errors"] for m in metrics.values()
            )
            if phase == "controls":
                expected = {(r["case_id"], r["replicate"]): r["output"] for r in imports}
                correct = rejected = 0
                score_errors = []
                for execution in report["executions"]:
                    assert (
                        execution["output"]
                        == expected[(execution["case_id"], execution["replicate"])]
                    )
                    result = next(
                        r for r in execution["results"] if r["metric_key"] == "source_support"
                    )
                    positive = execution["replicate"] == 0
                    if result["status"] == "scored":
                        correct += int(positive and result["passed"] is True)
                        rejected += int(not positive and result["passed"] is False)
                        score_errors.append(abs(result["score"] - (1 if positive else 2 / 3)))
                report["controls"] = {
                    "correct_accepted": correct,
                    "correct_total": 8,
                    "incorrect_rejected": rejected,
                    "incorrect_total": 8,
                    "max_score_error": max(score_errors, default=None),
                }
                report["accepted"] = (
                    complete and correct == rejected == 8 and max(score_errors, default=1) <= 0.05
                )
            else:
                report["gate"] = request(
                    "GET",
                    f"/experiments/{experiment['id']}/gate",
                    params={"metric": "record_exact"},
                )
                report["accepted"] = (
                    complete
                    and report["gate"]["passed"]
                    and metrics["source_support"]["pass_rate"] == 1
                )
            save(OUT / f"{phase}.json", report, secret)
            print(
                json.dumps(
                    {
                        "phase": phase,
                        "accepted": report["accepted"],
                        "status": report["status"],
                        "controls": report.get("controls"),
                        "gate": report.get("gate"),
                        "metrics": {
                            k: {"mean": v["mean"], "passed": v["passed"], "scored": v["scored"]}
                            for k, v in metrics.items()
                        },
                    }
                ),
                flush=True,
            )
            assert report["accepted"], "Review saved results; no further model calls made"
        finally:
            request("POST", "/auth/logout")


if __name__ == "__main__":
    main()
