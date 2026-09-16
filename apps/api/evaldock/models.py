from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class User(Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(Text)


class Workspace(Base):
    __tablename__ = "workspaces"
    name: Mapped[str] = mapped_column(String(120))


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id"),
        CheckConstraint("role in ('owner','editor','viewer')", name="role"),
    )
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String(10))


class SessionRecord(Base):
    __tablename__ = "sessions"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    digest: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ApiToken(Base):
    __tablename__ = "api_tokens"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"))
    digest: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    scopes: Mapped[list[str]] = mapped_column(JSONB)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("workspace_id", "name"),)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    fixture: Mapped[bool] = mapped_column(Boolean, default=False)


class Resource(Base):
    """Dataset, target, evaluator or suite identity; versions below are immutable."""

    __tablename__ = "resources"
    __table_args__ = (
        UniqueConstraint("project_id", "kind", "name"),
        CheckConstraint("kind in ('dataset','target','evaluator','suite')", name="kind"),
    )
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(120))


class Version(Base):
    __tablename__ = "versions"
    __table_args__ = (UniqueConstraint("resource_id", "number"),)
    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    fingerprint: Mapped[str] = mapped_column(String(64))


class TestCase(Base):
    __tablename__ = "test_cases"
    __table_args__ = (UniqueConstraint("version_id", "case_id"),)
    version_id: Mapped[str] = mapped_column(ForeignKey("versions.id"), index=True)
    case_id: Mapped[str] = mapped_column(String(160))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    fingerprint: Mapped[str] = mapped_column(String(64))


class Credential(Base):
    __tablename__ = "credentials"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    ciphertext: Mapped[str] = mapped_column(Text)


class Baseline(Base):
    __tablename__ = "baselines"
    __table_args__ = (UniqueConstraint("project_id", "name"),)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(String(120), default="main")
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiments.id"))


class Experiment(Base):
    __tablename__ = "experiments"
    __table_args__ = (
        CheckConstraint(
            "status in ('queued','running','completed','partially_failed','failed','canceled')",
            name="status",
        ),
    )
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    dataset_version_id: Mapped[str] = mapped_column(ForeignKey("versions.id"))
    target_version_id: Mapped[str | None] = mapped_column(ForeignKey("versions.id"))
    suite_version_id: Mapped[str] = mapped_column(ForeignKey("versions.id"))
    baseline_id: Mapped[str | None] = mapped_column(ForeignKey("experiments.id"))
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("experiments.id"))
    mode: Mapped[str] = mapped_column(String(20), default="http")
    status: Mapped[str] = mapped_column(String(30), default="queued")
    repetitions: Mapped[int] = mapped_column(Integer, default=1)
    concurrency: Mapped[int] = mapped_column(Integer, default=2)
    options: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    dispatch_pending: Mapped[bool] = mapped_column(Boolean, default=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Execution(Base):
    __tablename__ = "executions"
    __table_args__ = (UniqueConstraint("experiment_id", "case_id", "replicate"),)
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiments.id"), index=True)
    case_id: Mapped[str] = mapped_column(String(160))
    replicate: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="queued")
    output: Mapped[Any | None] = mapped_column(JSONB(none_as_null=True))
    output_present: Mapped[bool] = mapped_column(Boolean, default=False)
    trace: Mapped[Any | None] = mapped_column(JSONB(none_as_null=True))
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    target_latency_ms: Mapped[float | None] = mapped_column(Float)
    evaluation_latency_ms: Mapped[float | None] = mapped_column(Float)
    target_error: Mapped[str | None] = mapped_column(Text)
    late_completion: Mapped[bool] = mapped_column(Boolean, default=False)


class Attempt(Base):
    __tablename__ = "attempts"
    __table_args__ = (UniqueConstraint("execution_id", "phase", "evaluator_version_id", "number"),)
    execution_id: Mapped[str] = mapped_column(ForeignKey("executions.id"), index=True)
    phase: Mapped[str] = mapped_column(String(20))
    evaluator_version_id: Mapped[str] = mapped_column(String(36), default="target")
    number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="running")
    error: Mapped[str | None] = mapped_column(Text)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EvaluatorResult(Base):
    __tablename__ = "evaluator_results"
    __table_args__ = (UniqueConstraint("execution_id", "evaluator_version_id", "metric_key"),)
    execution_id: Mapped[str] = mapped_column(ForeignKey("executions.id"), index=True)
    evaluator_version_id: Mapped[str] = mapped_column(ForeignKey("versions.id"))
    metric_key: Mapped[str] = mapped_column(String(200))
    result: Mapped[dict[str, Any]] = mapped_column(JSONB)


class HumanReview(Base):
    __tablename__ = "human_reviews"
    execution_id: Mapped[str] = mapped_column(ForeignKey("executions.id"), index=True)
    reviewer_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    metric_key: Mapped[str] = mapped_column(String(200))
    passed: Mapped[bool] = mapped_column(Boolean)
    note: Mapped[str] = mapped_column(Text)


class Comparison(Base):
    __tablename__ = "comparisons"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    baseline_id: Mapped[str] = mapped_column(ForeignKey("experiments.id"))
    candidate_id: Mapped[str] = mapped_column(ForeignKey("experiments.id"))
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class Gate(Base):
    __tablename__ = "ci_gates"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), unique=True)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB)


class Artifact(Base):
    __tablename__ = "artifacts"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiments.id"))
    storage_key: Mapped[str] = mapped_column(String(120))
    media_type: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(160))


class AuditEvent(Base):
    __tablename__ = "audit_events"
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(100))
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class ProgressEvent(Base):
    __tablename__ = "progress_events"
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiments.id"), index=True)
    kind: Mapped[str] = mapped_column(String(50))
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class TargetThrottle(Base):
    __tablename__ = "target_throttles"
    version_id: Mapped[str] = mapped_column(ForeignKey("versions.id"), unique=True)
    next_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
