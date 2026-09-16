import asyncio
import time
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert

from .contracts import EvaluationInput, EvaluatorConfig, Launch, Result, TargetConfig
from .datasets import scoped_version
from .db import Session, now
from .evaluators import evaluate
from .models import (
    Attempt,
    Baseline,
    Credential,
    EvaluatorResult,
    Execution,
    Experiment,
    ProgressEvent,
    TargetThrottle,
    TestCase,
    Version,
)
from .security import credential_location, credential_secret
from .targets import invoke

TERMINAL = {"completed", "partially_failed", "failed", "canceled"}


async def launch(
    db: Any, project_id: str, payload: Launch, parent_id: str | None = None
) -> Experiment:
    await scoped_version(db, payload.dataset_version_id, project_id, "dataset")
    suite = await scoped_version(db, payload.suite_version_id, project_id, "suite")
    credentials = set()
    if payload.mode == "http":
        assert payload.target_version_id is not None
        target = await scoped_version(db, payload.target_version_id, project_id, "target")
        if target.config.get("credential_id"):
            credentials.add(target.config["credential_id"])
    for version_id in suite.config["evaluator_version_ids"]:
        evaluator = await scoped_version(db, version_id, project_id, "evaluator")
        cfg = evaluator.config.get("config", {})
        if evaluator.config["kind"] == "llm_judge" and cfg.get("mode") == "live":
            credentials.add(cfg.get("credential_id"))
    for credential_id in credentials:
        credential = await db.get(Credential, credential_id) if credential_id else None
        if (
            not credential
            or credential.project_id != project_id
            or not credential_secret(credential).strip()
        ):
            raise ValueError(
                f"Add the required API key in {credential_location(credential)} before launching"
            )
    cases = list(
        (
            await db.scalars(
                select(TestCase).where(TestCase.version_id == payload.dataset_version_id)
            )
        ).all()
    )
    imports = {(row.case_id, row.replicate): row for row in payload.imports}
    keys = {(case.case_id, rep) for case in cases for rep in range(payload.repetitions)}
    if len(imports) != len(payload.imports):
        raise ValueError("Duplicate imported case/replicate")
    if imports.keys() - keys:
        raise ValueError("Imported outputs contain unknown case IDs or replicate indices")
    baseline = await db.scalar(
        select(Baseline).where(
            Baseline.project_id == project_id, Baseline.name == payload.baseline_name
        )
    )
    parent = await db.get(Experiment, parent_id) if parent_id else None
    experiment = Experiment(
        project_id=project_id,
        name=payload.name,
        dataset_version_id=payload.dataset_version_id,
        target_version_id=payload.target_version_id if payload.mode == "http" else None,
        suite_version_id=payload.suite_version_id,
        baseline_id=baseline.experiment_id if baseline else None,
        parent_id=parent_id,
        mode=payload.mode,
        repetitions=payload.repetitions,
        concurrency=payload.concurrency,
        options={"max_target_calls": payload.max_target_calls, "warmup": payload.warmup},
    )
    db.add(experiment)
    if parent:
        experiment.baseline_id = parent.baseline_id
    await db.flush()
    for case_id, rep in sorted(keys):
        row = imports.get((case_id, rep))
        execution = Execution(experiment_id=experiment.id, case_id=case_id, replicate=rep)
        if payload.mode == "imported":
            if row:
                execution.output = row.output
                execution.output_present = True
                execution.trace = row.trace.model_dump(exclude_unset=True) if row.trace else None
                # Imported telemetry remains declared data, never invented measurements.
                execution.metadata_ = {
                    "imported_metadata": row.metadata,
                    "source": "imported",
                    "target_cost_provenance": "unavailable",
                }
            else:
                execution.status = "missing_output"
                execution.target_error = "Missing imported output"
        db.add(execution)
    db.add(ProgressEvent(experiment_id=experiment.id, kind="queued", data={"total": len(keys)}))
    await db.flush()
    return experiment


async def event(experiment_id: str, kind: str, data: dict[str, Any]) -> None:
    async with Session() as db:
        db.add(ProgressEvent(experiment_id=experiment_id, kind=kind, data=data))
        await db.commit()


async def canceled(experiment_id: str) -> bool:
    async with Session() as db:
        return bool(
            await db.scalar(
                select(Experiment.cancel_requested).where(Experiment.id == experiment_id)
            )
        )


async def stop_canceled_execution(execution_id: str, experiment_id: str) -> bool:
    if not await canceled(experiment_id):
        return False
    async with Session() as db:
        execution = await db.get(Execution, execution_id)
        assert execution
        execution.status = "canceled"
        await db.commit()
    return True


@asynccontextmanager
async def target_slot(version_id: str, config: TargetConfig):
    # Cross-process advisory semaphore: held on a dedicated connection throughout the call.
    from .db import lock_engine

    async with lock_engine.connect() as conn:
        acquired = None
        while acquired is None:
            for slot in range(config.concurrency):
                key = f"target:{version_id}:{slot}"
                if await conn.scalar(
                    text("SELECT pg_try_advisory_lock(hashtextextended(:key,0))"), {"key": key}
                ):
                    acquired = key
                    break
            if acquired is None:
                await asyncio.sleep(0.1)
        try:
            async with Session() as db:
                await db.execute(
                    insert(TargetThrottle)
                    .values(version_id=version_id, next_at=now())
                    .on_conflict_do_nothing(index_elements=["version_id"])
                )
                throttle = await db.scalar(
                    select(TargetThrottle)
                    .where(TargetThrottle.version_id == version_id)
                    .with_for_update()
                )
                assert throttle is not None
                scheduled = max(now(), throttle.next_at)
                throttle.next_at = scheduled + timedelta(seconds=1 / config.requests_per_second)
                await db.commit()
            await asyncio.sleep(max(0, (scheduled - now()).total_seconds()))
            yield
        finally:
            await conn.execute(
                text("SELECT pg_advisory_unlock(hashtextextended(:key,0))"), {"key": acquired}
            )


async def begin_attempt(execution_id: str, phase: str, evaluator_id: str = "target") -> Attempt:
    async with Session() as db:
        attempts = list(
            (
                await db.scalars(
                    select(Attempt)
                    .where(
                        Attempt.execution_id == execution_id,
                        Attempt.phase == phase,
                        Attempt.evaluator_version_id == evaluator_id,
                    )
                    .order_by(Attempt.number)
                )
            ).all()
        )
        for attempt in attempts:
            if attempt.status == "running":
                attempt.status, attempt.error, attempt.finished_at = (
                    "interrupted",
                    "Worker interrupted; external completion unknown",
                    now(),
                )
        attempt = Attempt(
            execution_id=execution_id,
            phase=phase,
            evaluator_version_id=evaluator_id,
            number=max((a.number for a in attempts), default=0) + 1,
        )
        db.add(attempt)
        await db.commit()
        return attempt


async def finish_attempt(
    attempt_id: str, status: str, error: str | None = None, data: dict[str, Any] | None = None
) -> None:
    async with Session() as db:
        attempt = await db.get(Attempt, attempt_id)
        assert attempt
        attempt.status, attempt.error, attempt.finished_at, attempt.data = (
            status,
            error,
            now(),
            data or {},
        )
        await db.commit()


async def evaluate_execution(execution_id: str) -> None:
    async with Session() as db:
        execution = await db.get(Execution, execution_id)
        assert execution
        experiment = await db.get(Experiment, execution.experiment_id)
        assert experiment
        case = await db.scalar(
            select(TestCase).where(
                TestCase.version_id == experiment.dataset_version_id,
                TestCase.case_id == execution.case_id,
            )
        )
        assert case
        suite = await db.get(Version, experiment.suite_version_id)
        assert suite
        if execution.status in {"completed", "missing_output", "canceled"}:
            return
        if experiment.cancel_requested:
            execution.status = "canceled"
            await db.commit()
            return
        execution.status = "running"
        await db.commit()
        target_version = (
            await db.get(Version, experiment.target_version_id)
            if experiment.target_version_id
            else None
        )
    if not execution.output_present and experiment.mode == "http":
        assert target_version
        config = TargetConfig.model_validate(target_version.config)
        async with Session() as db:
            credential = (
                await db.get(Credential, config.credential_id) if config.credential_id else None
            )
            secret = credential_secret(credential) if credential else None
        async with Session() as db:
            used = (
                await db.scalar(
                    select(func.count())
                    .select_from(Attempt)
                    .where(Attempt.execution_id == execution_id, Attempt.phase == "target")
                )
                or 0
            )
        offset = execution.metadata_.get("retry_offsets", {}).get("target", 0)
        remaining = max(0, config.max_attempts - (used - offset))
        if not remaining:
            execution.target_error = "Target attempt limit exhausted; manual retry is required"
        for retry in range(remaining):
            if await canceled(experiment.id):
                break
            # Reserve request budget transactionally before executing a side effect.
            async with Session() as db:
                exp = await db.scalar(
                    select(Experiment).where(Experiment.id == experiment.id).with_for_update()
                )
                assert exp
                options = dict(exp.options)
                calls = options.get("target_calls", 0)
                if (
                    options.get("max_target_calls") is not None
                    and calls >= options["max_target_calls"]
                ):
                    execution.target_error = "Target call budget exhausted"
                    break
                options["target_calls"] = calls + 1
                exp.options = options
                await db.commit()
            attempt = await begin_attempt(execution_id, "target")
            try:
                async with target_slot(target_version.id, config):
                    if await canceled(experiment.id):
                        await finish_attempt(attempt.id, "canceled")
                        break
                    response = await invoke(
                        config, case.payload["input"], f"evaldock:{execution_id}", secret
                    )
                late = await canceled(experiment.id)
                # Output and successful attempt become durable in the same transaction.
                async with Session() as db:
                    stored = await db.get(Execution, execution_id)
                    saved_attempt = await db.get(Attempt, attempt.id)
                    assert stored and saved_attempt
                    stored.output = response["output"]
                    stored.output_present = True
                    stored.trace = response["trace"]
                    stored.metadata_ = response["metadata"]
                    stored.target_latency_ms = response["target_latency_ms"]
                    stored.target_error = None
                    stored.late_completion = late
                    saved_attempt.status, saved_attempt.finished_at = "succeeded", now()
                    saved_attempt.data = response
                    await db.commit()
                    execution = stored
                break
            except Exception as exc:
                # Exception messages from external libraries may contain secrets or response data.
                error = (
                    str(exc)
                    if isinstance(exc, ValueError)
                    else f"Target transport failure ({type(exc).__name__})"
                )
                error = error.replace(secret, "[REDACTED]") if secret else error
                execution.target_error = error[:500]
                await finish_attempt(attempt.id, "error", execution.target_error)
                if retry + 1 < config.max_attempts:
                    await asyncio.sleep(min(2**retry, 8))
        if not execution.output_present:
            async with Session() as db:
                stored = await db.get(Execution, execution_id)
                assert stored
                stored.status = "canceled" if await canceled(experiment.id) else "target_error"
                stored.target_error = execution.target_error
                await db.commit()
            return
    if await canceled(experiment.id):
        async with Session() as db:
            stored = await db.get(Execution, execution_id)
            assert stored
            stored.status = "canceled"
            await db.commit()
        return
    started = time.perf_counter()
    had_error = False
    for evaluator_id in suite.config["evaluator_version_ids"]:
        if await stop_canceled_execution(execution_id, experiment.id):
            return
        async with Session() as db:
            previous = await db.scalar(
                select(EvaluatorResult).where(
                    EvaluatorResult.execution_id == execution_id,
                    EvaluatorResult.evaluator_version_id == evaluator_id,
                )
            )
            if previous and previous.result["status"] != "error":
                continue
            evaluator_version = await db.get(Version, evaluator_id)
            assert evaluator_version
            ev = EvaluatorConfig.model_validate(evaluator_version.config)
            credential = (
                await db.get(Credential, ev.config.get("credential_id"))
                if ev.config.get("credential_id")
                else None
            )
            secret = credential_secret(credential) if credential else None
        data = EvaluationInput(
            case_input=case.payload["input"],
            reference=case.payload.get("expected"),
            reference_present="expected" in case.payload,
            context=case.payload.get("context"),
            actual=execution.output,
            trace=execution.trace,
            metadata=execution.metadata_,
        )
        async with Session() as db:
            history = list(
                (
                    await db.scalars(
                        select(Attempt)
                        .where(
                            Attempt.execution_id == execution_id,
                            Attempt.phase == "evaluator",
                            Attempt.evaluator_version_id == evaluator_id,
                        )
                        .order_by(Attempt.number)
                    )
                ).all()
            )
        success = next(
            (a for a in history if a.status == "succeeded" and a.data.get("results")), None
        )
        offset = execution.metadata_.get("retry_offsets", {}).get(evaluator_id, 0)
        remaining = 0 if success else max(0, ev.max_attempts - (len(history) - offset))
        results = (
            [Result.model_validate(r) for r in success.data["results"]]
            if success
            else [
                Result(
                    metric_key=ev.metric_key,
                    status="error",
                    explanation="Evaluator attempt limit exhausted; manual retry is required",
                    evaluator_version=evaluator_id,
                )
            ]
        )
        for retry in range(remaining):
            if await stop_canceled_execution(execution_id, experiment.id):
                return
            attempt = await begin_attempt(execution_id, "evaluator", evaluator_id)
            try:
                results = await asyncio.wait_for(
                    evaluate(ev, evaluator_id, data, secret), timeout=70
                )
                await finish_attempt(
                    attempt.id, "succeeded", data={"results": [r.model_dump() for r in results]}
                )
                break
            except Exception as exc:
                error = f"Evaluator failure ({type(exc).__name__})"
                if isinstance(exc, ValueError) and ev.kind != "llm_judge":
                    error = str(exc)[:500]
                await finish_attempt(attempt.id, "error", error)
                results = [
                    Result(
                        metric_key=ev.metric_key,
                        status="error",
                        explanation=error,
                        evaluator_version=evaluator_id,
                    )
                ]
                if retry + 1 < ev.max_attempts:
                    await asyncio.sleep(min(2**retry, 8))
        async with Session() as db:
            for result in results:
                statement = insert(EvaluatorResult).values(
                    execution_id=execution_id,
                    evaluator_version_id=evaluator_id,
                    metric_key=result.metric_key,
                    result=result.model_dump(),
                )
                await db.execute(
                    statement.on_conflict_do_update(
                        index_elements=["execution_id", "evaluator_version_id", "metric_key"],
                        set_={"result": result.model_dump()},
                    )
                )
                had_error |= result.status == "error"
            await db.commit()
    async with Session() as db:
        stored = await db.get(Execution, execution_id)
        assert stored
        stored.status = (
            "canceled"
            if await canceled(experiment.id)
            else "evaluator_error"
            if had_error
            else "completed"
        )
        stored.evaluation_latency_ms = (stored.evaluation_latency_ms or 0) + (
            time.perf_counter() - started
        ) * 1000
        await db.commit()
    await event(
        experiment.id, "case_finished", {"execution_id": execution_id, "case_id": execution.case_id}
    )


async def run_experiment(experiment_id: str) -> None:
    async with Session() as db:
        experiment = await db.get(Experiment, experiment_id)
        if not experiment or experiment.status in TERMINAL:
            return
        experiment.status = "running"
        interrupted = list(
            (
                await db.scalars(
                    select(Attempt)
                    .join(Execution)
                    .where(Execution.experiment_id == experiment_id, Attempt.status == "running")
                )
            ).all()
        )
        for attempt in interrupted:
            attempt.status = "interrupted"
            attempt.error = "Worker interrupted; external completion unknown"
            attempt.finished_at = now()
        experiment.started_at = experiment.started_at or now()
        await db.commit()
        ids = list(
            (
                await db.scalars(
                    select(Execution.id)
                    .where(Execution.experiment_id == experiment_id)
                    .order_by(Execution.case_id, Execution.replicate)
                )
            ).all()
        )
    semaphore = asyncio.Semaphore(experiment.concurrency)

    async def work(execution_id: str) -> None:
        async with semaphore:
            await evaluate_execution(execution_id)

    await asyncio.gather(*(work(execution_id) for execution_id in ids))
    async with Session() as db:
        experiment = await db.get(Experiment, experiment_id)
        assert experiment
        states = list(
            (
                await db.scalars(
                    select(Execution.status).where(Execution.experiment_id == experiment_id)
                )
            ).all()
        )
        failures = sum(s != "completed" for s in states)
        experiment.status = (
            "canceled"
            if experiment.cancel_requested
            else "failed"
            if failures == len(states)
            else "partially_failed"
            if failures
            else "completed"
        )
        experiment.finished_at = now()
        db.add(
            ProgressEvent(
                experiment_id=experiment_id,
                kind=experiment.status,
                data={"finished": len(states), "failures": failures},
            )
        )
        await db.commit()
