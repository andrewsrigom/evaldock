import hashlib
import json
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .contracts import Case, EvaluatorConfig, TargetConfig
from .models import Credential, Resource, TestCase, Version


def fingerprint(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


async def scoped_version(db: AsyncSession, version_id: str, project_id: str, kind: str) -> Version:
    version = await db.scalar(
        select(Version)
        .join(Resource)
        .where(Version.id == version_id, Resource.project_id == project_id, Resource.kind == kind)
    )
    if not version:
        raise HTTPException(404, f"{kind} version not found in this project")
    return version


async def create_version(
    db: AsyncSession,
    resource: Resource,
    config: dict[str, Any],
    cases: list[dict[str, Any]] | None = None,
) -> Version:
    # Serialize version allocation by locking the stable identity.
    await db.execute(select(Resource).where(Resource.id == resource.id).with_for_update())
    normalized = []
    if resource.kind == "dataset":
        if not cases or len(cases) > 10000:
            raise ValueError("Dataset requires 1–10,000 cases")
        normalized = [Case.model_validate(c).model_dump(exclude_unset=True) for c in cases]
        if len({c["case_id"] for c in normalized}) != len(normalized):
            raise ValueError("Duplicate case IDs")
        config = {
            "held_out": bool(config.get("held_out", False)),
            "description": str(config.get("description", "")),
        }
    if resource.kind == "target":
        from .targets import validate_destination

        target = TargetConfig.model_validate(config)
        await validate_destination(target.endpoint)
        config = target.model_dump()
    if resource.kind == "evaluator":
        from .evaluators import validate_evaluator

        evaluator = EvaluatorConfig.model_validate(config)
        validate_evaluator(evaluator)
        config = evaluator.model_dump()
    credential_id = config.get("credential_id") or config.get("config", {}).get("credential_id")
    if credential_id:
        credential = await db.get(Credential, credential_id)
        if not credential or credential.project_id != resource.project_id:
            raise ValueError("Credential does not belong to this project")
    if resource.kind == "suite":
        ids = config.get("evaluator_version_ids", [])
        if (
            not isinstance(ids, list)
            or not ids
            or len(ids) > 20
            or any(not isinstance(value, str) for value in ids)
            or len(ids) != len(set(ids))
        ):
            raise ValueError("Suite requires 1–20 distinct evaluator versions")
        metric_keys = []
        for version_id in ids:
            ev = await scoped_version(db, version_id, resource.project_id, "evaluator")
            metric_keys.append(ev.config["metric_key"])
        if len(metric_keys) != len(set(metric_keys)):
            raise ValueError("Metric keys must be unique within a suite")
        config = {"evaluator_version_ids": ids, "description": str(config.get("description", ""))}
    number = (
        await db.scalar(select(func.max(Version.number)).where(Version.resource_id == resource.id))
        or 0
    ) + 1
    version = Version(
        resource_id=resource.id,
        number=number,
        config=config,
        fingerprint=fingerprint({"config": config, "cases": normalized}),
    )
    db.add(version)
    await db.flush()
    for case in normalized:
        db.add(
            TestCase(
                version_id=version.id,
                case_id=case["case_id"],
                payload=case,
                fingerprint=fingerprint(case),
            )
        )
    await db.flush()
    return version
