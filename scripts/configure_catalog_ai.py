"""Prepare the public pilot for one user-supplied OpenAI key; make no model calls."""

import copy
import json
from pathlib import Path

import httpx
from evaldock.config import settings

ROOT = Path(__file__).resolve().parents[1]


def main():
    preset = json.loads((ROOT / "examples/catalog_ai.json").read_text())
    config = settings()
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
        projects = [
            p
            for p in request("GET", "/projects")
            if p["name"] == "Catalog extraction · public-source pilot"
        ]
        assert len(projects) == 1, "Load the public-source pilot first"
        project_id = projects[0]["id"]
        detail = request("GET", f"/projects/{project_id}")
        before_experiments = {e["id"] for e in detail["experiments"]}
        credential = request(
            "POST", f"/projects/{project_id}/credentials/slot", json={"name": "OpenAI"}
        )

        def resource(kind, name, content):
            matches = [r for r in detail["resources"] if r["kind"] == kind and r["name"] == name]
            assert len(matches) <= 1, name
            if matches:
                for version in matches[0]["versions"]:
                    if all(version["config"].get(k) == v for k, v in content.items()):
                        return version["id"]
                raise ValueError(f"{name} has changed; existing versions were preserved")
            return request(
                "POST",
                f"/projects/{project_id}/resources",
                json={"kind": kind, "name": name, "config": content},
            )["version"]["id"]

        target_config = copy.deepcopy(preset["target"])
        target_config["credential_id"] = credential["id"]
        from evaldock.contracts import EvaluatorConfig, TargetConfig

        target_id = resource(
            "target",
            "Catalog extraction · OpenAI",
            TargetConfig.model_validate(target_config).model_dump(),
        )
        judge_config = copy.deepcopy(preset["judge"])
        judge_config["config"]["credential_id"] = credential["id"]
        judge_id = resource(
            "evaluator",
            "Source support · OpenAI",
            EvaluatorConfig.model_validate(judge_config).model_dump(),
        )
        deterministic = next(
            r["versions"][0]
            for r in detail["resources"]
            if r["name"] == "Catalog public-source criteria v1" and r["kind"] == "suite"
        )
        suite_id = resource(
            "suite",
            "Release criteria + AI review",
            {
                "evaluator_version_ids": [
                    *deterministic["config"]["evaluator_version_ids"],
                    judge_id,
                ],
                "description": "Six deterministic checks plus source-support review. AI review is not a calibrated release gate.",
            },
        )
        after = request("GET", f"/projects/{project_id}")
        assert before_experiments == {e["id"] for e in after["experiments"]}
        result = {
            "project_id": project_id,
            "settings_url": f"{config.public_origin}/projects/{project_id}/settings",
            "target_version_id": target_id,
            "judge_version_id": judge_id,
            "suite_version_id": suite_id,
            "model": preset["target"]["model"],
            "credential_configured": credential["configured"],
            "model_calls_during_setup": 0,
        }
        (ROOT / "docs/ai-setup.json").write_text(json.dumps(result, indent=2) + "\n")
        request("POST", "/auth/logout")
        print(json.dumps(result))


if __name__ == "__main__":
    main()
