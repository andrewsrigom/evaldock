import json
from types import SimpleNamespace

import pytest
from evaldock import evaluators, targets
from evaldock.config import settings
from evaldock.contracts import Judgment, Launch
from evaldock.db import Session
from evaldock.execution import launch, run_experiment
from evaldock.models import Credential, Experiment
from evaldock.security import decrypt
from pydantic import SecretStr
from sqlalchemy import func, select
from test_integration import add_resource, setup_project
from test_openai_target import SCHEMA, mock_transport

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_slot_rotation_permissions_and_no_secret_disclosure():
    project, _, client = await setup_project()
    path = f"/api/projects/{project.id}/credentials"
    async with client:
        reserved = await client.post(path + "/slot", json={"name": "OpenAI"})
        assert reserved.status_code == 200
        slot = reserved.json()
        assert slot["configured"] is False and slot["value"] == ""
        assert (await client.post(path + "/slot", json={"name": "OpenAI"})).json()["id"] == slot[
            "id"
        ]
        assert (await client.put(path + "/" + slot["id"], json={"value": " "})).status_code == 422
        for key in ["test-only-key-one", "test-only-key-two"]:
            saved = await client.put(path + "/" + slot["id"], json={"value": key})
            assert saved.status_code == 200 and saved.json()["configured"] is True
            assert key not in saved.text and key not in (await client.get(path)).text
            assert key not in (await client.get(f"/api/projects/{project.id}/audit")).text
            async with Session() as db:
                row = await db.get(Credential, slot["id"])
                assert row.ciphertext != key and decrypt(row.ciphertext) == key
        other, _, outsider = await setup_project()
        async with outsider:
            assert (
                await outsider.put(
                    f"/api/projects/{other.id}/credentials/{slot['id']}",
                    json={"value": "cannot-overwrite"},
                )
            ).status_code == 404
        viewer, _, reader = await setup_project("viewer")
        async with reader:
            assert (
                await reader.post(
                    f"/api/projects/{viewer.id}/credentials/slot", json={"name": "OpenAI"}
                )
            ).status_code == 403
            assert (
                await reader.put(
                    f"/api/projects/{viewer.id}/credentials/{slot['id']}", json={"value": "denied"}
                )
            ).status_code == 403


@pytest.mark.parametrize("environment", [False, True])
async def test_preflight_and_complete_native_generation_judgment_flow(monkeypatch, environment):
    project, _, client = await setup_project()
    async with client:
        slot = (
            await client.post(
                f"/api/projects/{project.id}/credentials/slot", json={"name": "OpenAI"}
            )
        ).json()

        if environment:
            monkeypatch.setattr(settings(), "openai_credential_id", slot["id"])
            monkeypatch.setattr(settings(), "openai_api_key", SecretStr(""))
            row = (await client.get(f"/api/projects/{project.id}/credentials")).json()[0]
            assert row["source"] == "environment" and row["configured"] is False

        async def validate(url):
            return ["8.8.8.8"]

        monkeypatch.setattr(targets, "validate_destination", validate)
        async with Session() as db:
            dataset = await add_resource(
                db,
                project.id,
                "dataset",
                {"held_out": False},
                [
                    {
                        "case_id": "a",
                        "input": {"passage": "observed"},
                        "expected": {"answer": "REFERENCE_ONLY"},
                        "context": {"evidence": "CONTEXT_ONLY"},
                    }
                ],
            )
            target = await add_resource(
                db,
                project.id,
                "target",
                {
                    "kind": "openai",
                    "model": "test-model",
                    "instructions": "Extract the observed answer",
                    "output_schema": SCHEMA,
                    "credential_id": slot["id"],
                    "max_attempts": 1,
                },
            )
            exact = await add_resource(
                db, project.id, "evaluator", {"kind": "exact_match", "metric_key": "exact"}
            )
            judge = await add_resource(
                db,
                project.id,
                "evaluator",
                {
                    "kind": "llm_judge",
                    "metric_key": "support",
                    "max_attempts": 1,
                    "config": {
                        "mode": "live",
                        "template": "context_support",
                        "model": "test-model",
                        "rubric": "Use supplied evidence",
                        "rubric_version": "v1",
                        "credential_id": slot["id"],
                        "parameters": {"reasoning_effort": "low", "max_output_tokens": 2000},
                    },
                },
            )
            suite = await add_resource(
                db, project.id, "suite", {"evaluator_version_ids": [exact.id, judge.id]}
            )
            await db.commit()
        body = {
            "name": "Native AI verification",
            "dataset_version_id": dataset.id,
            "target_version_id": target.id,
            "suite_version_id": suite.id,
        }
        blocked = await client.post(f"/api/projects/{project.id}/experiments", json=body)
        assert blocked.status_code == 422 and "API key" in blocked.text
        test = await client.post(f"/api/targets/{target.id}/test", json={"input": {}})
        assert test.status_code == 422 and "API key" in test.text
        imported = {
            **body,
            "mode": "imported",
            "target_version_id": None,
            "import_dataset_version_id": dataset.id,
            "imports": [{"case_id": "a", "output": {"answer": "observed"}}],
        }
        assert (
            await client.post(f"/api/projects/{project.id}/experiments", json=imported)
        ).status_code == 422
        async with Session() as db:
            assert (
                await db.scalar(
                    select(func.count())
                    .select_from(Experiment)
                    .where(Experiment.project_id == project.id)
                )
                == 0
            )
        saved = await client.put(
            f"/api/projects/{project.id}/credentials/{slot['id']}",
            json={"value": "test-only-secret"},
        )
        if environment:
            assert saved.status_code == 422 and "server .env" in saved.text
            monkeypatch.setattr(settings(), "openai_api_key", SecretStr("test-only-secret"))
            status = await client.get(f"/api/projects/{project.id}/credentials")
            assert status.json()[0]["configured"] is True
            assert "test-only-secret" not in status.text
            async with Session() as db:
                stored = await db.get(Credential, slot["id"])
                assert decrypt(stored.ciphertext) == "", (
                    "Environment key must not be copied to the database"
                )
        else:
            assert saved.status_code == 200
        sent = mock_transport(monkeypatch)
        judge_requests = []

        class JudgeClient:
            def __init__(self, **kwargs):
                assert kwargs["api_key"] == "test-only-secret" and kwargs["max_retries"] == 0
                self.responses = self

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

            async def parse(self, **kwargs):
                judge_requests.append(kwargs)
                return SimpleNamespace(
                    output_parsed=Judgment(
                        score=0,
                        passed=False,
                        justification="The supplied context does not support the answer.",
                        evidence=["CONTEXT_ONLY"],
                    ),
                    usage=SimpleNamespace(
                        model_dump=lambda: {"input_tokens": 80, "output_tokens": 12}
                    ),
                )

        monkeypatch.setattr(evaluators, "AsyncOpenAI", JudgeClient)
        async with Session() as db:
            experiment = await launch(db, project.id, Launch.model_validate(body))
            experiment.dispatch_pending = False
            await db.commit()
        await run_experiment(experiment.id)
        report = (await client.get(f"/api/experiments/{experiment.id}")).json()
        assert report["status"] == "completed"
        row = report["executions"][0]
        assert row["output"] == {"answer": "observed"} and row["target_latency_ms"] >= 0
        assert row["metadata"]["target_usage"]["input_tokens"] == 40
        assert len(row["results"]) == 2 and all(r["passed"] is False for r in row["results"])
        assert len(sent) == len(judge_requests) == 1, "Valid failing judgments must not be retried"
        assert "REFERENCE_ONLY" not in json.dumps(sent) and "CONTEXT_ONLY" not in json.dumps(sent)
        assert judge_requests[0]["reasoning"] == {"effort": "low"}
        assert judge_requests[0]["store"] is False
        assert "CONTEXT_ONLY" in judge_requests[0]["input"][1]["content"]
        assert "test-only-secret" not in json.dumps(report)
