import json
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy import select

from .config import settings
from .measurement import aggregate
from .models import EvaluatorResult, Execution, Experiment, HumanReview, TestCase, Version


class ArtifactStore(Protocol):
    def put(self, key: str, content: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...


class LocalArtifactStore:
    def __init__(self, root: str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if path.parent != self.root:
            raise ValueError("Invalid artifact key")
        return path

    def put(self, key: str, content: bytes) -> None:
        target = self.path(key)
        temporary = target.with_suffix(".tmp")
        temporary.write_bytes(content)
        temporary.replace(target)

    def get(self, key: str) -> bytes:
        return self.path(key).read_bytes()


def store() -> ArtifactStore:
    return LocalArtifactStore(settings().artifact_dir)


def record(value: Any) -> dict[str, Any]:
    return {
        column.key: getattr(value, "metadata_" if column.key == "metadata" else column.key)
        for column in value.__table__.columns
    }


async def report(db: Any, experiment: Experiment) -> dict[str, Any]:
    suite = await db.get(Version, experiment.suite_version_id)
    versions = list(
        (
            await db.scalars(
                select(Version).where(Version.id.in_(suite.config["evaluator_version_ids"]))
            )
        ).all()
    )
    definitions = {v.config["metric_key"]: v.config["definition"] for v in versions}
    cases = {
        c.case_id: c
        for c in (
            await db.scalars(
                select(TestCase).where(TestCase.version_id == experiment.dataset_version_id)
            )
        ).all()
    }
    executions = list(
        (
            await db.scalars(
                select(Execution)
                .where(Execution.experiment_id == experiment.id)
                .order_by(Execution.case_id, Execution.replicate)
            )
        ).all()
    )
    results = list(
        (
            await db.scalars(
                select(EvaluatorResult)
                .join(Execution)
                .where(Execution.experiment_id == experiment.id)
            )
        ).all()
    )
    reviews = list(
        (
            await db.scalars(
                select(HumanReview)
                .join(Execution)
                .where(Execution.experiment_id == experiment.id)
                .order_by(HumanReview.created_at)
            )
        ).all()
    )
    rows = []
    for execution in executions:
        row = record(execution)
        row["case"] = cases[execution.case_id].payload
        row["case_fingerprint"] = cases[execution.case_id].fingerprint
        row["results"] = [r.result for r in results if r.execution_id == execution.id]
        row["reviews"] = [record(r) for r in reviews if r.execution_id == execution.id]
        rows.append(row)
    value = record(experiment)
    target = (
        await db.get(Version, experiment.target_version_id)
        if experiment.target_version_id
        else None
    )
    value["target_limits"] = (
        {k: target.config.get(k) for k in ["concurrency", "requests_per_second", "timeout_seconds"]}
        if target
        else None
    )
    value["executions"], value["summary"] = rows, aggregate(rows, definitions)
    latest = {(r.execution_id, r.reviewer_id, r.metric_key): r for r in reviews}
    calibration = []
    for review in latest.values():
        result = next(
            (
                r.result
                for r in results
                if r.execution_id == review.execution_id and r.metric_key == review.metric_key
            ),
            None,
        )
        if result and result["status"] == "scored" and result.get("passed") is not None:
            calibration.append(
                {
                    "execution_id": review.execution_id,
                    "metric_key": review.metric_key,
                    "human": review.passed,
                    "automated": result["passed"],
                    "agrees": review.passed == result["passed"],
                    "reviewer_id": review.reviewer_id,
                }
            )
    value["calibration"] = {
        "reviewed_decisions": len(calibration),
        "agreement": sum(r["agrees"] for r in calibration) / len(calibration)
        if calibration
        else None,
        "disagreements": [r for r in calibration if not r["agrees"]],
        "policy": "Latest assessment per reviewer, execution and metric; automated judgments preserved",
    }
    return value


def json_bytes(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str, allow_nan=False).encode()
