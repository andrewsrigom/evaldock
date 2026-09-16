import asyncio
from datetime import timedelta

import httpx
import pytest
from evaldock.api import app
from evaldock.config import settings
from evaldock.contracts import Launch
from evaldock.datasets import create_version
from evaldock.db import Session, now, uid
from evaldock.execution import launch, run_experiment
from evaldock.models import (
    ApiToken,
    Credential,
    Experiment,
    Membership,
    Project,
    Resource,
    User,
    Workspace,
)
from evaldock.security import digest, passwords
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def setup_project(role="owner"):
    assert settings().database_url.rsplit("/", 1)[-1] == "evaldock_test", (
        "Integration tests require isolated evaldock_test database"
    )
    async with Session() as db:
        user = User(
            email=f"{uid()}@test.local",
            name="Test",
            password_hash=passwords.hash("test-password-long"),
        )
        workspace = Workspace(name="Test workspace")
        db.add_all([user, workspace])
        await db.flush()
        db.add(Membership(workspace_id=workspace.id, user_id=user.id, role=role))
        project = Project(workspace_id=workspace.id, name="Test project")
        db.add(project)
        await db.flush()
        raw = uid()
        db.add(
            ApiToken(
                workspace_id=workspace.id,
                user_id=user.id,
                digest=digest(raw),
                name="tests",
                scopes=["read", "write"],
                expires_at=now() + timedelta(hours=1),
            )
        )
        await db.commit()
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {raw}"},
    )
    return project, user, client


async def add_resource(db, project_id, kind, config, cases=None):
    resource = Resource(project_id=project_id, kind=kind, name=uid())
    db.add(resource)
    await db.flush()
    return await create_version(db, resource, config, cases)


async def prepare(project, cases=None, evaluator=None):
    async with Session() as db:
        dataset = await add_resource(
            db,
            project.id,
            "dataset",
            {},
            cases
            or [
                {
                    "case_id": "a",
                    "input": {"value": 1},
                    "expected": {"value": 1},
                    "context": {"hidden": "NEVER_SEND"},
                }
            ],
        )
        target = await add_resource(
            db,
            project.id,
            "target",
            {"endpoint": "http://localhost:8099/catalog/baseline", "max_attempts": 2},
        )
        ev = await add_resource(
            db,
            project.id,
            "evaluator",
            evaluator or {"kind": "exact_match", "metric_key": "exact", "max_attempts": 2},
        )
        suite = await add_resource(db, project.id, "suite", {"evaluator_version_ids": [ev.id]})
        exp = await launch(
            db,
            project.id,
            Launch(
                name="Test run",
                dataset_version_id=dataset.id,
                target_version_id=target.id,
                suite_version_id=suite.id,
            ),
        )
        exp.dispatch_pending = False
        await db.commit()
        return exp, dataset, target, suite


async def test_immutable_versions_import_and_workspace_isolation():
    project, _, client = await setup_project()
    exp, dataset, _, _ = await prepare(project)
    async with Session() as db:
        with pytest.raises(DBAPIError):
            await db.execute(
                text("UPDATE versions SET config='{}'::jsonb WHERE id=:id"), {"id": dataset.id}
            )
        await db.rollback()
    result = await client.post(
        "/api/datasets/preview",
        json={"content": '{"case_id":"a","input":{}}\n{"case_id":"a","input":{}}'},
    )
    assert result.status_code == 200 and result.json()["errors"][0]["line"] == 2
    other, _, outsider = await setup_project()
    assert (await outsider.get(f"/api/experiments/{exp.id}")).status_code == 404
    assert (await outsider.get(f"/api/versions/{dataset.id}")).status_code == 404
    assert (await outsider.get(f"/api/experiments/{exp.id}/events")).status_code == 404
    mismatch = await outsider.post(
        f"/api/projects/{other.id}/experiments",
        json={
            "name": "cross",
            "dataset_version_id": dataset.id,
            "suite_version_id": exp.suite_version_id,
            "mode": "imported",
            "import_dataset_version_id": dataset.id,
        },
    )
    assert mismatch.status_code == 404
    await client.aclose()
    await outsider.aclose()


async def test_viewer_cannot_write_and_secret_masking():
    project, _, viewer = await setup_project("viewer")
    assert (
        await viewer.post(
            f"/api/projects/{project.id}/credentials", json={"name": "x", "value": "secret"}
        )
    ).status_code == 403
    owner, _, client = await setup_project()
    secret = "test-secret-never-return"
    result = await client.post(
        f"/api/projects/{owner.id}/credentials", json={"name": "provider", "value": secret}
    )
    assert result.status_code == 200 and secret not in result.text
    async with Session() as db:
        credential = await db.get(Credential, result.json()["id"])
        assert secret not in credential.ciphertext
    assert secret not in (await client.get(f"/api/projects/{owner.id}/credentials")).text
    await viewer.aclose()
    await client.aclose()


async def test_independent_retries_duplicate_delivery_and_rescore(monkeypatch):
    import evaldock.execution as module

    real_evaluate = module.evaluate
    calls = {"target": 0, "evaluator": 0}

    async def target(config, case_input, key, secret):
        calls["target"] += 1
        assert case_input == {"value": 1}
        return {"output": {"value": 1}, "trace": None, "metadata": {}, "target_latency_ms": 12.0}

    async def evaluator(*args, **kwargs):
        calls["evaluator"] += 1
        if calls["evaluator"] == 1:
            raise RuntimeError("transient judge error")
        return await real_evaluate(*args, **kwargs)

    monkeypatch.setattr(module, "invoke", target)
    monkeypatch.setattr(module, "evaluate", evaluator)
    project, _, client = await setup_project()
    exp, _, _, suite = await prepare(project)
    await run_experiment(exp.id)
    await run_experiment(exp.id)
    assert calls == {"target": 1, "evaluator": 2}
    result = (await client.get(f"/api/experiments/{exp.id}")).json()
    assert result["status"] == "completed"
    execution = result["executions"][0]
    attempts = (await client.get(f"/api/executions/{execution['id']}")).json()["attempts"]
    assert [a["status"] for a in attempts if a["phase"] == "evaluator"] == ["error", "succeeded"]
    rescore = await client.post(
        f"/api/experiments/{exp.id}/rescore",
        json={"suite_version_id": suite.id, "name": "rescored"},
    )
    assert rescore.status_code == 200
    await run_experiment(rescore.json()["id"])
    assert calls["target"] == 1
    res = (await client.get(f"/api/experiments/{rescore.json()['id']}")).json()
    assert res["parent_id"] == exp.id and res["executions"][0]["target_latency_ms"] is None
    await client.aclose()


async def test_cancellation_late_output_and_no_new_calls(monkeypatch):
    import evaldock.execution as module

    started, release = asyncio.Event(), asyncio.Event()
    count = 0

    async def target(*args):
        nonlocal count
        count += 1
        started.set()
        await release.wait()
        return {"output": {"value": 1}, "trace": None, "metadata": {}, "target_latency_ms": 10}

    monkeypatch.setattr(module, "invoke", target)
    project, _, client = await setup_project()
    cases = [{"case_id": str(i), "input": {"value": 1}, "expected": {"value": 1}} for i in range(3)]
    exp, *_ = await prepare(project, cases)
    async with Session() as db:
        saved = await db.get(Experiment, exp.id)
        saved.concurrency = 1
        await db.commit()
    task = asyncio.create_task(run_experiment(exp.id))
    await started.wait()
    assert (await client.post(f"/api/experiments/{exp.id}/cancel")).status_code == 200
    release.set()
    await task
    result = (await client.get(f"/api/experiments/{exp.id}")).json()
    assert result["status"] == "canceled" and count == 1
    assert result["executions"][0]["late_completion"] is True
    assert result["executions"][0]["output_present"] is True
    await client.aclose()


async def test_human_disagreement_preserves_judge_and_import_coverage():
    project, _, client = await setup_project()
    exp, dataset, _, suite = await prepare(
        project,
        [
            {"case_id": "a", "input": {}, "expected": 1},
            {"case_id": "b", "input": {}, "expected": None},
        ],
        {
            "kind": "llm_judge",
            "metric_key": "judge",
            "config": {"mode": "fixture", "rubric": "match", "rubric_version": "v1"},
        },
    )
    launch_body = {
        "name": "Imported",
        "dataset_version_id": dataset.id,
        "suite_version_id": suite.id,
        "mode": "imported",
        "import_dataset_version_id": dataset.id,
        "imports": [{"case_id": "a", "output": 1}],
    }
    duplicate = await client.post(
        f"/api/projects/{project.id}/experiments",
        json={
            **launch_body,
            "imports": [{"case_id": "a", "output": 1}, {"case_id": "a", "output": 2}],
        },
    )
    assert duplicate.status_code == 422
    response = await client.post(f"/api/projects/{project.id}/experiments", json=launch_body)
    assert response.status_code == 200
    imported_id = response.json()["id"]
    await run_experiment(imported_id)
    result = (await client.get(f"/api/experiments/{imported_id}")).json()
    assert (
        result["status"] == "partially_failed"
        and result["summary"]["metrics"]["judge"]["coverage"] == 0.5
    )
    execution = result["executions"][0]
    review = await client.post(
        f"/api/executions/{execution['id']}/reviews",
        json={
            "metric_key": "judge",
            "passed": False,
            "note": "Human disagrees with fixture equality.",
        },
    )
    assert review.status_code == 200
    result = (await client.get(f"/api/experiments/{imported_id}")).json()
    assert result["executions"][0]["results"][0]["passed"] is True
    assert result["calibration"]["agreement"] == 0
    assert len(result["calibration"]["disagreements"]) == 1
    artifact = await client.post(f"/api/experiments/{imported_id}/artifacts?metric=judge")
    assert artifact.status_code == 200
    _, _, outsider = await setup_project()
    assert (await outsider.get(f"/api/artifacts/{artifact.json()['id']}")).status_code == 404
    await client.aclose()
    await outsider.aclose()


async def test_cookie_sessions_csrf_and_logout():
    project, user, token_client = await setup_project()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post(
            "/api/auth/login", json={"email": user.email, "password": "test-password-long"}
        )
        assert result.status_code == 200 and "HttpOnly" in result.headers["set-cookie"]
        assert (await client.get("/api/auth/me")).status_code == 200
        assert (await client.post("/api/auth/logout")).status_code == 403
        assert (
            await client.post(
                "/api/auth/logout",
                headers={"Origin": settings().public_origin, "X-EvalDock-CSRF": "1"},
            )
        ).status_code == 200
        assert (await client.get("/api/auth/me")).status_code == 401
    await token_client.aclose()


@pytest.mark.parametrize(
    "role,scopes",
    [("owner", ["read"]), ("owner", ["read", "write"]), ("viewer", ["read"])],
)
async def test_token_revocation_requires_browser_session(role, scopes):
    project, user, token_client = await setup_project(role)
    async with Session() as db:
        caller = await db.scalar(select(ApiToken).where(ApiToken.user_id == user.id))
        caller.scopes = scopes
        other = Workspace(name="Other workspace")
        db.add(other)
        await db.flush()
        db.add(Membership(workspace_id=other.id, user_id=user.id, role=role))
        targets = [
            ApiToken(
                user_id=user.id,
                workspace_id=workspace_id,
                name="Revocation target",
                digest=digest(uid()),
                scopes=["read"],
                expires_at=now() + timedelta(hours=1),
            )
            for workspace_id in [project.workspace_id, other.id]
        ]
        db.add_all(targets)
        await db.commit()
        target_ids = [token.id for token in targets]
    try:
        for token_id in target_ids:
            response = await token_client.delete(f"/api/tokens/{token_id}")
            assert response.status_code == 403
        async with Session() as db:
            for token_id in target_ids:
                token = await db.get(ApiToken, token_id)
                assert token.revoked is False
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as browser:
            login = await browser.post(
                "/api/auth/login", json={"email": user.email, "password": "test-password-long"}
            )
            assert login.status_code == 200
            for token_id in target_ids:
                assert (await browser.delete(f"/api/tokens/{token_id}")).status_code == 403
                response = await browser.delete(
                    f"/api/tokens/{token_id}",
                    headers={"Origin": settings().public_origin, "X-EvalDock-CSRF": "1"},
                )
                assert response.status_code == 200
            async with Session() as db:
                for token_id in target_ids:
                    token = await db.get(ApiToken, token_id)
                    assert token.revoked is True
    finally:
        await token_client.aclose()
