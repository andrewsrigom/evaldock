import json
from datetime import timedelta
from typing import Any, Literal

from argon2.exceptions import VerificationError
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from pydantic import Field
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .contracts import Contract, GateConfig, ImportedOutput, Launch, TargetConfig, parse_jsonl
from .datasets import create_version, scoped_version
from .db import get_db, now, uid
from .execution import TERMINAL, launch
from .measurement import evaluate_gate, junit, pair_comparison
from .models import (
    ApiToken,
    Artifact,
    Attempt,
    AuditEvent,
    Baseline,
    Comparison,
    Credential,
    EvaluatorResult,
    Execution,
    Experiment,
    Gate,
    HumanReview,
    Membership,
    ProgressEvent,
    Project,
    Resource,
    SessionRecord,
    TestCase,
    User,
    Version,
    Workspace,
)
from .reports import json_bytes, record, report, store
from .security import (
    Principal,
    credential_location,
    credential_secret,
    credential_source,
    digest,
    encrypt,
    passwords,
    principal,
    project_access,
    token_value,
    workspace_access,
)
from .targets import invoke

app = FastAPI(title="EvalDock API", version="0.1.0")


@app.middleware("http")
async def security_headers(request: Request, call_next: Any) -> Response:
    if int(request.headers.get("content-length", "0")) > 10_000_000:
        return Response("Request too large", 413)
    if request.method in {"POST", "PUT", "PATCH"}:
        # Read once with a hard bound, including chunked requests.
        size = 0
        chunks = []
        async for chunk in request.stream():
            size += len(chunk)
            if size > 10_000_000:
                return Response("Request too large", 413)
            chunks.append(chunk)
        request._body = b"".join(chunks)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(ValueError)
async def invalid_value(request: Request, exc: ValueError) -> Response:
    return Response(
        json.dumps({"detail": str(exc)[:1000]}), status_code=422, media_type="application/json"
    )


@app.exception_handler(IntegrityError)
async def conflict(request: Request, exc: IntegrityError) -> Response:
    return Response(
        json.dumps({"detail": "Record conflicts with an existing identity or immutable version"}),
        status_code=409,
        media_type="application/json",
    )


def audit(
    db: AsyncSession, who: Principal, project: Project, action: str, detail: dict[str, Any]
) -> None:
    db.add(
        AuditEvent(
            workspace_id=project.workspace_id,
            project_id=project.id,
            actor_id=who.user.id,
            action=action,
            detail=detail,
        )
    )


@app.get("/api/health")
async def health(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    from sqlalchemy import text

    await db.execute(text("SELECT 1"))
    return {"status": "ok", "version": "0.1.0"}


class Login(Contract):
    email: str = Field(max_length=255)
    password: str = Field(max_length=256)


@app.post("/api/auth/login")
async def login(
    body: Login, request: Request, response: Response, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    if request.headers.get("origin") and request.headers["origin"] != settings().public_origin:
        raise HTTPException(403, "Invalid origin")
    user = await db.scalar(select(User).where(User.email == body.email.lower()))
    try:
        if not user or not passwords.verify(user.password_hash, body.password):
            raise HTTPException(401, "Invalid email or password")
    except VerificationError:
        raise HTTPException(401, "Invalid email or password") from None
    raw = token_value()
    db.add(
        SessionRecord(
            user_id=user.id,
            digest=digest(raw),
            expires_at=now() + timedelta(hours=settings().session_hours),
        )
    )
    await db.commit()
    response.set_cookie(
        "evaldock_session",
        raw,
        httponly=True,
        secure=settings().cookie_secure,
        samesite="strict",
        max_age=settings().session_hours * 3600,
        path="/",
    )
    return {"id": user.id, "name": user.name, "email": user.email}


@app.post("/api/auth/logout")
async def logout(
    request: Request,
    response: Response,
    who: Principal = Depends(principal),
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    await db.execute(
        delete(SessionRecord).where(
            SessionRecord.digest == digest(request.cookies.get("evaldock_session", ""))
        )
    )
    await db.commit()
    response.delete_cookie("evaldock_session", path="/")
    return {"ok": True}


@app.get("/api/auth/me")
async def me(
    who: Principal = Depends(principal), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    memberships = list(
        (await db.scalars(select(Membership).where(Membership.user_id == who.user.id))).all()
    )
    if who.token:
        memberships = [m for m in memberships if m.workspace_id == who.token.workspace_id]
    workspaces = []
    for membership in memberships:
        workspace = await db.get(Workspace, membership.workspace_id)
        assert workspace
        workspaces.append({"id": workspace.id, "name": workspace.name, "role": membership.role})
    return {
        "id": who.user.id,
        "name": who.user.name,
        "email": who.user.email,
        "workspaces": workspaces,
    }


class TokenCreate(Contract):
    workspace_id: str
    name: str = Field(min_length=1, max_length=120)
    scopes: list[Literal["read", "write"]] = Field(default=["read"])
    days: int = Field(default=30, ge=1, le=365)


@app.post("/api/tokens")
async def create_token(
    body: TokenCreate, who: Principal = Depends(principal), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    membership = await workspace_access(db, who, body.workspace_id)
    if who.token or ("write" in body.scopes and membership.role == "viewer"):
        raise HTTPException(403, "Use an authorized browser session to issue tokens")
    raw = "ed_" + token_value()
    token = ApiToken(
        user_id=who.user.id,
        workspace_id=body.workspace_id,
        name=body.name,
        digest=digest(raw),
        scopes=body.scopes,
        expires_at=now() + timedelta(days=body.days),
    )
    db.add(token)
    await db.commit()
    return {"id": token.id, "token": raw, "expires_at": token.expires_at, "scopes": token.scopes}


@app.get("/api/tokens")
async def tokens(
    who: Principal = Depends(principal), db: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    rows = (await db.scalars(select(ApiToken).where(ApiToken.user_id == who.user.id))).all()
    return [
        {k: v for k, v in record(row).items() if k != "digest"}
        for row in rows
        if not who.token or row.workspace_id == who.token.workspace_id
    ]


@app.delete("/api/tokens/{token_id}")
async def revoke_token(
    token_id: str, who: Principal = Depends(principal), db: AsyncSession = Depends(get_db)
) -> dict[str, bool]:
    token = await db.get(ApiToken, token_id)
    if not token or token.user_id != who.user.id:
        raise HTTPException(404, "Token not found")
    token.revoked = True
    await db.commit()
    return {"ok": True}


class ProjectCreate(Contract):
    workspace_id: str
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=3000)


@app.get("/api/projects")
async def projects(
    who: Principal = Depends(principal), db: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    query = (
        select(Project)
        .join(Membership, Project.workspace_id == Membership.workspace_id)
        .where(Membership.user_id == who.user.id)
        .order_by(Project.created_at)
    )
    if who.token:
        if "read" not in who.token.scopes:
            raise HTTPException(403, "Read scope required")
        query = query.where(Project.workspace_id == who.token.workspace_id)
    return [record(p) for p in (await db.scalars(query)).all()]


@app.post("/api/projects")
async def new_project(
    body: ProjectCreate, who: Principal = Depends(principal), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    await workspace_access(db, who, body.workspace_id, write=True)
    project = Project(**body.model_dump())
    db.add(project)
    await db.flush()
    audit(db, who, project, "project.created", {})
    await db.commit()
    return record(project)


@app.get("/api/projects/{project_id}")
async def project_detail(
    project_id: str, who: Principal = Depends(principal), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    project = await project_access(db, who, project_id)
    resources = list(
        (
            await db.scalars(
                select(Resource)
                .where(Resource.project_id == project_id)
                .order_by(Resource.created_at)
            )
        ).all()
    )
    versions = list(
        (
            await db.scalars(
                select(Version)
                .join(Resource)
                .where(Resource.project_id == project_id)
                .order_by(Version.number.desc())
            )
        ).all()
    )
    experiments = list(
        (
            await db.scalars(
                select(Experiment)
                .where(Experiment.project_id == project_id)
                .order_by(Experiment.created_at.desc())
                .limit(100)
            )
        ).all()
    )
    baselines = list(
        (await db.scalars(select(Baseline).where(Baseline.project_id == project_id))).all()
    )
    return {
        **record(project),
        "resources": [
            {**record(r), "versions": [record(v) for v in versions if v.resource_id == r.id]}
            for r in resources
        ],
        "experiments": [record(e) for e in experiments],
        "baselines": [record(b) for b in baselines],
    }


class ResourceCreate(Contract):
    kind: Literal["dataset", "target", "evaluator", "suite"]
    name: str = Field(min_length=1, max_length=120)
    config: dict[str, Any] = Field(default_factory=dict)
    cases: list[dict[str, Any]] | None = None


class VersionCreate(Contract):
    config: dict[str, Any] = Field(default_factory=dict)
    cases: list[dict[str, Any]] | None = None


@app.post("/api/projects/{project_id}/resources")
async def new_resource(
    project_id: str,
    body: ResourceCreate,
    who: Principal = Depends(principal),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    project = await project_access(db, who, project_id, write=True)
    resource = Resource(project_id=project_id, kind=body.kind, name=body.name)
    db.add(resource)
    await db.flush()
    version = await create_version(db, resource, body.config, body.cases)
    audit(
        db,
        who,
        project,
        f"{body.kind}.created",
        {"resource_id": resource.id, "version_id": version.id},
    )
    await db.commit()
    return {**record(resource), "version": record(version)}


@app.post("/api/resources/{resource_id}/versions")
async def new_version(
    resource_id: str,
    body: VersionCreate,
    who: Principal = Depends(principal),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    resource = await db.get(Resource, resource_id)
    if not resource:
        raise HTTPException(404, "Resource not found")
    project = await project_access(db, who, resource.project_id, write=True)
    version = await create_version(db, resource, body.config, body.cases)
    audit(
        db, who, project, "version.created", {"resource_id": resource_id, "version_id": version.id}
    )
    await db.commit()
    return record(version)


@app.get("/api/versions/{version_id}")
async def version_detail(
    version_id: str, who: Principal = Depends(principal), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    version = await db.get(Version, version_id)
    if not version:
        raise HTTPException(404, "Version not found")
    resource = await db.get(Resource, version.resource_id)
    assert resource
    await project_access(db, who, resource.project_id)
    cases = list(
        (
            await db.scalars(
                select(TestCase).where(TestCase.version_id == version_id).order_by(TestCase.case_id)
            )
        ).all()
    )
    return {
        **record(version),
        "resource": record(resource),
        "cases": [case.payload for case in cases],
    }


class JsonlImport(Contract):
    content: str = Field(max_length=9_000_000)


@app.post("/api/datasets/preview")
async def preview_jsonl(body: JsonlImport, who: Principal = Depends(principal)) -> dict[str, Any]:
    cases, errors = parse_jsonl(body.content)
    return {
        "valid": not errors,
        "count": len(cases),
        "preview": cases[:20],
        "cases": cases if not errors else [],
        "errors": errors,
    }


@app.get("/api/versions/{version_id}/jsonl")
async def export_jsonl(
    version_id: str, who: Principal = Depends(principal), db: AsyncSession = Depends(get_db)
) -> Response:
    detail = await version_detail(version_id, who, db)
    return Response(
        "\n".join(json.dumps(c, ensure_ascii=False) for c in detail["cases"]) + "\n",
        media_type="application/x-ndjson",
        headers={"Content-Disposition": "attachment; filename=dataset.jsonl"},
    )


class SecretValue(Contract):
    value: str = Field(min_length=1, max_length=8192)


class SecretSlot(Contract):
    name: str = Field(min_length=1, max_length=120)


def credential_status(credential: Credential) -> dict[str, Any]:
    configured = bool(credential_secret(credential).strip())
    return {
        "id": credential.id,
        "name": credential.name,
        "value": "••••••••" if configured else "",
        "configured": configured,
        "source": credential_source(credential),
    }


@app.post("/api/projects/{project_id}/credentials/slot")
async def reserve_credential(
    project_id: str,
    body: SecretSlot,
    who: Principal = Depends(principal),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    project = await project_access(db, who, project_id, write=True)
    await db.execute(select(Project).where(Project.id == project_id).with_for_update())
    rows = (
        await db.scalars(
            select(Credential).where(
                Credential.project_id == project_id, Credential.name == body.name
            )
        )
    ).all()
    if len(rows) > 1:
        raise ValueError("Multiple credentials have this name; select an existing credential")
    if rows:
        return credential_status(rows[0])
    credential = Credential(project_id=project_id, name=body.name, ciphertext=encrypt(""))
    db.add(credential)
    await db.flush()
    audit(db, who, project, "credential.reserved", {"credential_id": credential.id})
    await db.commit()
    return credential_status(credential)


@app.put("/api/projects/{project_id}/credentials/{credential_id}")
async def update_credential(
    project_id: str,
    credential_id: str,
    body: SecretValue,
    who: Principal = Depends(principal),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    project = await project_access(db, who, project_id, write=True)
    credential = await db.get(Credential, credential_id)
    if not credential or credential.project_id != project_id:
        raise HTTPException(404, "Credential not found")
    if credential_source(credential) == "environment":
        raise ValueError("This key is managed through OPENAI_API_KEY in the server .env")
    if not body.value.strip():
        raise ValueError("Enter a nonempty API key")
    credential.ciphertext = encrypt(body.value.strip())
    audit(db, who, project, "credential.updated", {"credential_id": credential.id})
    await db.commit()
    return credential_status(credential)


class SecretCreate(Contract):
    name: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=8192)


@app.get("/api/projects/{project_id}/credentials")
async def credentials(
    project_id: str, who: Principal = Depends(principal), db: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    await project_access(db, who, project_id)
    rows = (await db.scalars(select(Credential).where(Credential.project_id == project_id))).all()
    return [credential_status(c) for c in rows]


@app.post("/api/projects/{project_id}/credentials")
async def save_credential(
    project_id: str,
    body: SecretCreate,
    who: Principal = Depends(principal),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    project = await project_access(db, who, project_id, write=True)
    credential = Credential(project_id=project_id, name=body.name, ciphertext=encrypt(body.value))
    db.add(credential)
    await db.flush()
    audit(db, who, project, "credential.created", {"credential_id": credential.id})
    await db.commit()
    return {"id": credential.id, "name": credential.name, "value": "••••••••"}


class ConnectionTest(Contract):
    input: Any


@app.post("/api/targets/{version_id}/test")
async def test_target(
    version_id: str,
    body: ConnectionTest,
    who: Principal = Depends(principal),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    detail = await version_detail(version_id, who, db)
    project = await project_access(db, who, detail["resource"]["project_id"], write=True)
    await scoped_version(db, version_id, project.id, "target")
    config = TargetConfig.model_validate(detail["config"])
    credential = await db.get(Credential, config.credential_id) if config.credential_id else None
    if config.credential_id and (
        not credential
        or credential.project_id != project.id
        or not credential_secret(credential).strip()
    ):
        raise ValueError(
            f"Add the target API key in {credential_location(credential)} before testing"
        )
    from .execution import target_slot

    try:
        async with target_slot(version_id, config):
            result = await invoke(
                config,
                body.input,
                "evaldock:test:" + uid(),
                credential_secret(credential) if credential else None,
            )
    except Exception as exc:
        raise HTTPException(
            422, f"Connection test failed ({type(exc).__name__}); check endpoint and mappings"
        ) from None
    audit(db, who, project, "target.connection_test", {"version_id": version_id})
    await db.commit()
    return result


@app.post("/api/projects/{project_id}/experiments")
async def new_experiment(
    project_id: str,
    body: Launch,
    who: Principal = Depends(principal),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    project = await project_access(db, who, project_id, write=True)
    experiment = await launch(db, project_id, body)
    audit(db, who, project, "experiment.created", {"experiment_id": experiment.id})
    await db.commit()
    return record(experiment)


async def authorized_experiment(
    db: AsyncSession, who: Principal, experiment_id: str, write: bool = False
) -> Experiment:
    experiment = await db.get(Experiment, experiment_id)
    if not experiment:
        raise HTTPException(404, "Experiment not found")
    await project_access(db, who, experiment.project_id, write)
    return experiment


@app.get("/api/experiments/{experiment_id}")
async def experiment_detail(
    experiment_id: str, who: Principal = Depends(principal), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    return await report(db, await authorized_experiment(db, who, experiment_id))


@app.get("/api/experiments/{experiment_id}/events")
async def events(
    experiment_id: str,
    after: str | None = None,
    who: Principal = Depends(principal),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    await authorized_experiment(db, who, experiment_id)
    query = (
        select(ProgressEvent)
        .where(ProgressEvent.experiment_id == experiment_id)
        .order_by(ProgressEvent.created_at, ProgressEvent.id)
        .limit(200)
    )
    if after:
        previous = await db.get(ProgressEvent, after)
        if not previous or previous.experiment_id != experiment_id:
            raise HTTPException(404, "Event cursor not found")
        from sqlalchemy import tuple_

        query = query.where(
            tuple_(ProgressEvent.created_at, ProgressEvent.id) > (previous.created_at, previous.id)
        )
    return [record(e) for e in (await db.scalars(query)).all()]


@app.post("/api/experiments/{experiment_id}/cancel")
async def cancel_experiment(
    experiment_id: str, who: Principal = Depends(principal), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    experiment = await authorized_experiment(db, who, experiment_id, write=True)
    if experiment.status not in TERMINAL:
        experiment.cancel_requested = True
        db.add(ProgressEvent(experiment_id=experiment_id, kind="cancel_requested", data={}))
        await db.commit()
    return record(experiment)


@app.post("/api/experiments/{experiment_id}/retry")
async def retry_experiment(
    experiment_id: str, who: Principal = Depends(principal), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    experiment = await authorized_experiment(db, who, experiment_id, write=True)
    if experiment.status not in {"failed", "partially_failed"}:
        raise HTTPException(409, "Only failed work can be retried; rescore valid outputs instead")
    executions = (
        await db.scalars(
            select(Execution).where(
                Execution.experiment_id == experiment_id,
                Execution.status.in_(["target_error", "evaluator_error"]),
            )
        )
    ).all()
    if not executions:
        raise HTTPException(409, "No retryable work; missing imports require a new import")
    for execution in executions:
        execution.status = "queued"
        attempts = list(
            (await db.scalars(select(Attempt).where(Attempt.execution_id == execution.id))).all()
        )
        offsets: dict[str, int] = {}
        for attempt in attempts:
            offsets[attempt.evaluator_version_id] = max(
                offsets.get(attempt.evaluator_version_id, 0), attempt.number
            )
        execution.metadata_ = {**execution.metadata_, "retry_offsets": offsets}
    experiment.status, experiment.dispatch_pending, experiment.finished_at = "queued", True, None
    await db.commit()
    return record(experiment)


class Rescore(Contract):
    suite_version_id: str
    name: str = "Rescored outputs"


@app.post("/api/experiments/{experiment_id}/rescore")
async def rescore(
    experiment_id: str,
    body: Rescore,
    who: Principal = Depends(principal),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    source = await authorized_experiment(db, who, experiment_id, write=True)
    if source.status not in TERMINAL:
        raise HTTPException(409, "Wait for experiment completion before rescoring")
    executions = (
        await db.scalars(select(Execution).where(Execution.experiment_id == experiment_id))
    ).all()
    imports = [
        ImportedOutput(
            case_id=e.case_id,
            replicate=e.replicate,
            output=e.output,
            trace=e.trace,
            metadata={"source_execution_id": e.id, "original_metadata": e.metadata_},
        )
        for e in executions
        if e.output_present
    ]
    payload = Launch(
        name=body.name,
        dataset_version_id=source.dataset_version_id,
        suite_version_id=body.suite_version_id,
        repetitions=source.repetitions,
        concurrency=source.concurrency,
        mode="imported",
        import_dataset_version_id=source.dataset_version_id,
        imports=imports,
    )
    experiment = await launch(db, source.project_id, payload, parent_id=source.id)
    await db.commit()
    return record(experiment)


class PinBaseline(Contract):
    experiment_id: str
    name: str = Field(default="main", min_length=1, max_length=120)


@app.post("/api/projects/{project_id}/baselines")
async def pin_baseline(
    project_id: str,
    body: PinBaseline,
    who: Principal = Depends(principal),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    project = await project_access(db, who, project_id, write=True)
    experiment = await authorized_experiment(db, who, body.experiment_id)
    if experiment.project_id != project_id or experiment.status != "completed":
        raise HTTPException(422, "Baseline must be a completed experiment in this project")
    baseline = await db.scalar(
        select(Baseline).where(Baseline.project_id == project_id, Baseline.name == body.name)
    )
    if baseline:
        baseline.experiment_id = experiment.id
    else:
        baseline = Baseline(project_id=project_id, name=body.name, experiment_id=experiment.id)
        db.add(baseline)
    audit(db, who, project, "baseline.pinned", {"experiment_id": experiment.id, "name": body.name})
    await db.commit()
    return record(baseline)


@app.get("/api/compare")
async def compare(
    baseline: str,
    candidate: str,
    metric: str,
    tag: str | None = None,
    slice: str | None = None,
    who: Principal = Depends(principal),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    left, right = (
        await authorized_experiment(db, who, baseline),
        await authorized_experiment(db, who, candidate),
    )
    if left.project_id != right.project_id:
        raise HTTPException(422, "Experiments must belong to the same project")
    return pair_comparison(await report(db, left), await report(db, right), metric, tag, slice)


class SaveComparison(Contract):
    baseline_id: str
    candidate_id: str
    metric: str


@app.post("/api/comparisons")
async def save_comparison(
    body: SaveComparison, who: Principal = Depends(principal), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    left = await authorized_experiment(db, who, body.baseline_id, write=True)
    right = await authorized_experiment(db, who, body.candidate_id)
    if left.project_id != right.project_id:
        raise HTTPException(422, "Experiments must belong to the same project")
    value = Comparison(
        project_id=left.project_id,
        baseline_id=left.id,
        candidate_id=right.id,
        config={"metric": body.metric},
    )
    db.add(value)
    await db.commit()
    return record(value)


async def authorized_execution(
    db: AsyncSession, who: Principal, execution_id: str, write: bool = False
) -> tuple[Execution, Experiment]:
    execution = await db.get(Execution, execution_id)
    if not execution:
        raise HTTPException(404, "Execution not found")
    experiment = await authorized_experiment(db, who, execution.experiment_id, write)
    return execution, experiment


@app.get("/api/executions/{execution_id}")
async def execution_detail(
    execution_id: str, who: Principal = Depends(principal), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    _, experiment = await authorized_execution(db, who, execution_id)
    experiment_report = await report(db, experiment)
    row = next(r for r in experiment_report["executions"] if r["id"] == execution_id)
    row["project_id"] = experiment.project_id
    row["attempts"] = [
        record(a)
        for a in (
            await db.scalars(
                select(Attempt)
                .where(Attempt.execution_id == execution_id)
                .order_by(Attempt.created_at)
            )
        ).all()
    ]
    return row


class ReviewCreate(Contract):
    metric_key: str
    passed: bool
    note: str = Field(min_length=1, max_length=3000)


@app.post("/api/executions/{execution_id}/reviews")
async def review(
    execution_id: str,
    body: ReviewCreate,
    who: Principal = Depends(principal),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    _, experiment = await authorized_execution(db, who, execution_id, write=True)
    result = await db.scalar(
        select(EvaluatorResult).where(
            EvaluatorResult.execution_id == execution_id,
            EvaluatorResult.metric_key == body.metric_key,
        )
    )
    if not result:
        raise HTTPException(422, "Metric result not found")
    assessment = HumanReview(
        execution_id=execution_id, reviewer_id=who.user.id, **body.model_dump()
    )
    db.add(assessment)
    project = await db.get(Project, experiment.project_id)
    assert project
    audit(
        db,
        who,
        project,
        "review.created",
        {"execution_id": execution_id, "metric_key": body.metric_key},
    )
    await db.commit()
    return record(assessment)


@app.get("/api/projects/{project_id}/reviews")
async def review_queue(
    project_id: str, who: Principal = Depends(principal), db: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    await project_access(db, who, project_id)
    experiments = (
        await db.scalars(
            select(Experiment)
            .where(Experiment.project_id == project_id, Experiment.status.in_(TERMINAL))
            .order_by(Experiment.created_at.desc())
            .limit(10)
        )
    ).all()
    rows: list[dict[str, Any]] = []
    for experiment in experiments:
        result = await report(db, experiment)
        rows.extend(
            {**row, "experiment_name": experiment.name}
            for row in result["executions"]
            if row["results"]
        )
    return rows


@app.get("/api/projects/{project_id}/gate")
async def gate_config(
    project_id: str, who: Principal = Depends(principal), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    await project_access(db, who, project_id)
    gate = await db.scalar(select(Gate).where(Gate.project_id == project_id))
    return gate.config if gate else GateConfig().model_dump()


@app.put("/api/projects/{project_id}/gate")
async def update_gate(
    project_id: str,
    body: GateConfig,
    who: Principal = Depends(principal),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    project = await project_access(db, who, project_id, write=True)
    gate = await db.scalar(select(Gate).where(Gate.project_id == project_id))
    if gate:
        gate.config = body.model_dump()
    else:
        db.add(Gate(project_id=project_id, config=body.model_dump()))
    audit(db, who, project, "gate.updated", {})
    await db.commit()
    return body.model_dump()


async def gate_result(
    db: AsyncSession, experiment: Experiment, metric: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    result = await report(db, experiment)
    gate = await db.scalar(select(Gate).where(Gate.project_id == experiment.project_id))
    baseline = await db.get(Experiment, experiment.baseline_id) if experiment.baseline_id else None
    comparison = pair_comparison(await report(db, baseline), result, metric) if baseline else None
    return result, evaluate_gate(
        result, comparison, GateConfig.model_validate(gate.config if gate else {})
    )


@app.get("/api/experiments/{experiment_id}/gate")
async def run_gate(
    experiment_id: str,
    metric: str,
    who: Principal = Depends(principal),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    experiment = await authorized_experiment(db, who, experiment_id)
    _, result = await gate_result(db, experiment, metric)
    return result


@app.get("/api/experiments/{experiment_id}/report")
async def export_report(
    experiment_id: str,
    metric: str,
    format: Literal["json", "junit"] = "json",
    who: Principal = Depends(principal),
    db: AsyncSession = Depends(get_db),
) -> Response:
    experiment = await authorized_experiment(db, who, experiment_id)
    data, gate = await gate_result(db, experiment, metric)
    content = json_bytes({**data, "gate": gate}) if format == "json" else junit(data, gate).encode()
    media_type = "application/json" if format == "json" else "application/xml"
    return Response(
        content,
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename=evaldock-{experiment_id}.{format if format == 'json' else 'xml'}"
        },
    )


@app.post("/api/experiments/{experiment_id}/artifacts")
async def save_report(
    experiment_id: str,
    metric: str,
    who: Principal = Depends(principal),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    experiment = await authorized_experiment(db, who, experiment_id, write=True)
    data, gate = await gate_result(db, experiment, metric)
    artifact = Artifact(
        project_id=experiment.project_id,
        experiment_id=experiment_id,
        storage_key=uid() + ".json",
        name=experiment.name + ".json",
        media_type="application/json",
    )
    store().put(artifact.storage_key, json_bytes({**data, "gate": gate}))
    db.add(artifact)
    await db.commit()
    return record(artifact)


@app.get("/api/artifacts/{artifact_id}")
async def download_artifact(
    artifact_id: str, who: Principal = Depends(principal), db: AsyncSession = Depends(get_db)
) -> Response:
    artifact = await db.get(Artifact, artifact_id)
    if not artifact:
        raise HTTPException(404, "Artifact not found")
    await project_access(db, who, artifact.project_id)
    return Response(store().get(artifact.storage_key), media_type=artifact.media_type)


@app.get("/api/projects/{project_id}/audit")
async def audit_log(
    project_id: str, who: Principal = Depends(principal), db: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    await project_access(db, who, project_id)
    return [
        record(row)
        for row in (
            await db.scalars(
                select(AuditEvent)
                .where(AuditEvent.project_id == project_id)
                .order_by(AuditEvent.created_at.desc())
                .limit(100)
            )
        ).all()
    ]


class MemberCreate(Contract):
    email: str = Field(min_length=3, max_length=255)
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=12, max_length=256)
    role: Literal["owner", "editor", "viewer"]


@app.get("/api/workspaces/{workspace_id}/members")
async def members(
    workspace_id: str, who: Principal = Depends(principal), db: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    await workspace_access(db, who, workspace_id)
    rows = (
        await db.execute(
            select(Membership, User).join(User).where(Membership.workspace_id == workspace_id)
        )
    ).all()
    return [{"id": m.id, "name": u.name, "email": u.email, "role": m.role} for m, u in rows]


@app.post("/api/workspaces/{workspace_id}/members")
async def add_member(
    workspace_id: str,
    body: MemberCreate,
    who: Principal = Depends(principal),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    await workspace_access(db, who, workspace_id, write=True, owner=True)
    user = await db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None:
        user = User(
            email=body.email.lower(), name=body.name, password_hash=passwords.hash(body.password)
        )
        db.add(user)
        await db.flush()
    membership = Membership(workspace_id=workspace_id, user_id=user.id, role=body.role)
    db.add(membership)
    db.add(
        AuditEvent(
            workspace_id=workspace_id,
            actor_id=who.user.id,
            action="membership.created",
            detail={"user_id": user.id, "role": body.role},
        )
    )
    await db.commit()
    return {"id": membership.id, "email": user.email, "role": membership.role}


if __name__ == "__main__":
    print(json.dumps(jsonable_encoder(app.openapi()), indent=2))
