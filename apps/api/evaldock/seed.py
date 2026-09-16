import asyncio
from pathlib import Path

from sqlalchemy import select

from .config import settings
from .contracts import GateConfig, parse_jsonl
from .datasets import create_version
from .db import Session
from .models import Gate, Membership, Project, Resource, User, Workspace
from .security import passwords

ROOT = Path(__file__).resolve().parents[3]


async def seed():
    if len(settings().demo_password) < 12:
        raise ValueError("Set DEMO_PASSWORD (at least 12 characters) before seeding")
    async with Session() as db:
        existing = await db.scalar(select(User).where(User.email == "demo@evaldock.local"))
        if existing:
            print("Demo already seeded; existing workspace retained")
            return
        user = User(
            email="demo@evaldock.local",
            name="Alex Morgan",
            password_hash=passwords.hash(settings().demo_password),
        )
        workspace = Workspace(name="Development workspace")
        db.add_all([user, workspace])
        await db.flush()
        db.add(Membership(user_id=user.id, workspace_id=workspace.id, role="owner"))
        for kind, name, description in [
            (
                "catalog",
                "Catalog extraction",
                "Structured attributes grounded in product documentation.",
            ),
            (
                "support",
                "Support triage",
                "Ticket category and urgency across four support labels.",
            ),
        ]:
            project = Project(
                workspace_id=workspace.id, name=name, description=description, fixture=True
            )
            db.add(project)
            await db.flush()

            async def resource(resource_kind, resource_name, config, cases=None):
                value = Resource(project_id=project.id, kind=resource_kind, name=resource_name)
                db.add(value)
                await db.flush()
                return await create_version(db, value, config, cases)

            cases, errors = parse_jsonl((ROOT / "fixtures" / f"{kind}.jsonl").read_text())
            assert not errors
            dataset = await resource(
                "dataset",
                "Product evidence" if kind == "catalog" else "Support ticket gold set",
                {
                    "held_out": True,
                    "description": "24 manually labeled deterministic demo cases; includes ambiguous and adversarial inputs.",
                },
                cases,
            )
            for variant in ["baseline", "candidate"]:
                await resource(
                    "target",
                    f"{kind.title()} · {variant}",
                    {
                        "endpoint": f"{settings().sample_origin}/{kind}/{variant}",
                        "fixture": True,
                        "revision": f"{kind}-{variant}-v1",
                        "concurrency": 4,
                        "requests_per_second": 20,
                    },
                )
            schema = (
                {
                    "type": "object",
                    "required": ["material", "weight_g", "country"],
                    "additionalProperties": False,
                    "properties": {
                        "material": {"type": ["string", "null"]},
                        "weight_g": {"type": ["number", "null"]},
                        "country": {"type": ["string", "null"]},
                    },
                }
                if kind == "catalog"
                else {
                    "type": "object",
                    "required": ["category", "urgency"],
                    "properties": {
                        "category": {"enum": ["billing", "technical", "account", "feature"]},
                        "urgency": {"enum": ["normal", "urgent"]},
                    },
                    "additionalProperties": False,
                }
            )
            fields = (
                ["/material", "/weight_g", "/country"]
                if kind == "catalog"
                else ["/category", "/urgency"]
            )
            evaluators = [
                await resource(
                    "evaluator",
                    "Schema validity",
                    {
                        "kind": "json_schema",
                        "metric_key": "schema_valid",
                        "config": {"schema": schema},
                        "definition": {"aggregation": "pass_rate", "required_inputs": ["actual"]},
                    },
                ),
                await resource(
                    "evaluator",
                    "Field accuracy",
                    {
                        "kind": "field_comparison",
                        "metric_key": "field_accuracy",
                        "config": {"paths": fields},
                        "definition": {"required_inputs": ["actual", "reference"], "threshold": 1},
                    },
                ),
            ]
            if kind == "support":
                evaluators.append(
                    await resource(
                        "evaluator",
                        "Category correctness",
                        {
                            "kind": "classification",
                            "metric_key": "category_accuracy",
                            "config": {
                                "path": "/category",
                                "labels": ["billing", "technical", "account", "feature"],
                            },
                            "definition": {
                                "aggregation": "classification",
                                "required_inputs": ["actual", "reference"],
                            },
                        },
                    )
                )
            suite = await resource(
                "suite", "Release criteria", {"evaluator_version_ids": [e.id for e in evaluators]}
            )
            judge = await resource(
                "evaluator",
                "Correctness judge · fixture",
                {
                    "kind": "llm_judge",
                    "metric_key": "judge_correctness",
                    "config": {
                        "mode": "fixture",
                        "template": "correctness",
                        "rubric": "Output must match the provided reference and preserve abstentions.",
                        "rubric_version": "correctness-v1",
                    },
                },
            )
            await resource(
                "suite",
                "Judge calibration · fixture",
                {"evaluator_version_ids": [evaluators[1].id, judge.id]},
            )
            db.add(
                Gate(
                    project_id=project.id,
                    config=GateConfig(min_accuracy={"field_accuracy": 0.9}).model_dump(),
                )
            )
            print(f"Seeded {kind}: {len(cases)} cases, dataset {dataset.id}, suite {suite.id}")
        await db.commit()


if __name__ == "__main__":
    asyncio.run(seed())
