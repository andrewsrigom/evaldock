import asyncio
import logging

import procrastinate
from sqlalchemy import select, text

from .config import settings
from .db import Session, now
from .execution import run_experiment
from .models import Execution, Experiment, ProgressEvent

queue = procrastinate.App(connector=procrastinate.PsycopgConnector(conninfo=settings().queue_url))
logger = logging.getLogger("evaldock.worker")


@queue.task(
    name="evaldock.experiment",
    retry=procrastinate.RetryStrategy(max_attempts=5, exponential_wait=2),
)
async def experiment_job(experiment_id: str) -> None:
    await run_experiment(experiment_id)


async def reconcile() -> None:
    async with Session() as db:
        pending = list(
            (
                await db.scalars(
                    select(Experiment)
                    .where(Experiment.dispatch_pending.is_(True))
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        for experiment in pending:
            # Dispatch crash gaps can duplicate queue delivery; the execution lock and stored
            # completion state make duplicate delivery harmless to completed work.
            await experiment_job.configure(lock=f"experiment:{experiment.id}").defer_async(
                experiment_id=experiment.id
            )
            experiment.dispatch_pending = False
        await db.commit()
    for job in await queue.job_manager.get_stalled_jobs(seconds_since_heartbeat=30):
        await queue.job_manager.retry_job(job)
    async with Session() as db:
        failed = (
            (
                await db.execute(
                    text(
                        "SELECT DISTINCT args->>'experiment_id' FROM procrastinate_jobs WHERE task_name='evaldock.experiment' AND status='failed'"
                    )
                )
            )
            .scalars()
            .all()
        )
        for experiment_id in failed:
            failed_experiment = await db.get(Experiment, experiment_id)
            if (
                failed_experiment
                and failed_experiment.status == "running"
                and not failed_experiment.dispatch_pending
            ):
                active = await db.scalar(
                    text(
                        "SELECT count(*) FROM procrastinate_jobs WHERE args->>'experiment_id'=:id AND status IN ('todo','doing')"
                    ),
                    {"id": experiment_id},
                )
                if active:
                    continue
                failed_experiment.status, failed_experiment.finished_at = "failed", now()
                for execution in (
                    await db.scalars(
                        select(Execution).where(
                            Execution.experiment_id == experiment_id,
                            Execution.status.in_(["queued", "running"]),
                        )
                    )
                ).all():
                    execution.status = (
                        "evaluator_error" if execution.output_present else "target_error"
                    )
                    if not execution.output_present:
                        execution.target_error = (
                            "Worker delivery exhausted after infrastructure failure"
                        )
                db.add(
                    ProgressEvent(
                        experiment_id=experiment_id,
                        kind="failed",
                        data={"reason": "worker_delivery_exhausted"},
                    )
                )
        await db.commit()


async def reconciliation_loop() -> None:
    while True:
        try:
            await reconcile()
        except Exception:
            logger.error("Queue reconciliation failed; will retry")
        await asyncio.sleep(3)


async def main() -> None:
    async with queue.open_async():
        reconciler = asyncio.create_task(reconciliation_loop())
        try:
            await queue.run_worker_async(concurrency=2)
        finally:
            reconciler.cancel()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
