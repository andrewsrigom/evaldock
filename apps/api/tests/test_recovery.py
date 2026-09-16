import pytest
from evaldock.db import Session, now
from evaldock.execution import run_experiment
from evaldock.models import Attempt, Execution, Experiment
from sqlalchemy import select
from test_integration import add_resource, prepare, setup_project

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_cancellation_stops_new_evaluator_scheduling(monkeypatch):
    import evaldock.execution as module
    from evaldock.contracts import ImportedOutput, Launch
    from evaldock.models import Version

    project, _, client = await setup_project()
    source, dataset, _, suite = await prepare(project)
    async with Session() as db:
        first_suite = await db.get(Version, suite.id)
        second = await add_resource(
            db, project.id, "evaluator", {"kind": "exact_match", "metric_key": "second"}
        )
        combined = await add_resource(
            db,
            project.id,
            "suite",
            {"evaluator_version_ids": [*first_suite.config["evaluator_version_ids"], second.id]},
        )
        exp = await module.launch(
            db,
            project.id,
            Launch(
                name="Cancel between evaluators",
                dataset_version_id=dataset.id,
                suite_version_id=combined.id,
                mode="imported",
                import_dataset_version_id=dataset.id,
                imports=[ImportedOutput(case_id="a", output={"value": 1})],
            ),
        )
        await db.commit()
    real_evaluate = module.evaluate
    calls = 0

    async def evaluator(*args, **kwargs):
        nonlocal calls
        calls += 1
        async with Session() as db:
            saved = await db.get(Experiment, exp.id)
            saved.cancel_requested = True
            await db.commit()
        return await real_evaluate(*args, **kwargs)

    monkeypatch.setattr(module, "evaluate", evaluator)
    await run_experiment(exp.id)
    result = (await client.get(f"/api/experiments/{exp.id}")).json()
    assert calls == 1 and result["status"] == "canceled"
    assert result["executions"][0]["results"][0]["status"] == "scored"
    await client.aclose()


async def test_persisted_output_survives_interrupted_evaluation(monkeypatch):
    import evaldock.execution as module

    project, _, client = await setup_project()
    experiment, _, _, _ = await prepare(project)
    async with Session() as db:
        execution = await db.scalar(
            select(Execution).where(Execution.experiment_id == experiment.id)
        )
        execution.output = {"value": 1}
        execution.output_present = True
        execution.status = "running"
        db.add(
            Attempt(
                execution_id=execution.id,
                phase="target",
                number=1,
                status="succeeded",
                finished_at=now(),
            )
        )
        await db.commit()

    async def forbidden(*args, **kwargs):
        raise AssertionError("Saved output must never call the target again")

    monkeypatch.setattr(module, "invoke", forbidden)
    await run_experiment(experiment.id)
    result = (await client.get(f"/api/experiments/{experiment.id}")).json()
    assert result["status"] == "completed"
    assert result["executions"][0]["results"][0]["passed"] is True
    await client.aclose()


async def test_attempt_bounds_survive_restarts_and_manual_retry(monkeypatch):
    import evaldock.execution as module

    project, _, client = await setup_project()
    experiment, _, _, _ = await prepare(project)
    async with Session() as db:
        execution = await db.scalar(
            select(Execution).where(Execution.experiment_id == experiment.id)
        )
        for number in [1, 2]:
            db.add(
                Attempt(
                    execution_id=execution.id,
                    phase="target",
                    number=number,
                    status="running" if number == 2 else "error",
                )
            )
        await db.commit()
    count = 0

    async def target(*args, **kwargs):
        nonlocal count
        count += 1
        return {"output": {"value": 1}, "trace": None, "metadata": {}, "target_latency_ms": 1}

    monkeypatch.setattr(module, "invoke", target)
    await run_experiment(experiment.id)
    result = (await client.get(f"/api/experiments/{experiment.id}")).json()
    assert result["status"] == "failed" and count == 0
    assert result["summary"]["target_errors"] == 1
    retried = await client.post(f"/api/experiments/{experiment.id}/retry")
    assert retried.status_code == 200
    await run_experiment(experiment.id)
    result = (await client.get(f"/api/experiments/{experiment.id}")).json()
    assert result["status"] == "completed" and count == 1
    await client.aclose()
