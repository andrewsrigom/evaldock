import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Case(Contract):
    case_id: str = Field(min_length=1, max_length=160, pattern=r"^[\w.:-]+$")
    input: Any
    expected: Any = None
    context: Any = None
    tags: list[str] = Field(default_factory=list)
    slices: dict[str, str] = Field(default_factory=dict)
    acceptance_criteria: str | None = None
    references: list[str] = Field(default_factory=list)


def parse_jsonl(content: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cases, errors, seen = [], [], set()
    for number, line in enumerate(content.splitlines(), 1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
            case = Case.model_validate(raw)
            if case.case_id in seen:
                raise ValueError(f"Duplicate case_id: {case.case_id}")
            seen.add(case.case_id)
            cases.append(case.model_dump(exclude_unset=True))
        except (ValueError, TypeError) as exc:
            errors.append({"line": number, "message": str(exc)[:500]})
    if not cases and not errors:
        errors.append({"line": 1, "message": "At least one case is required"})
    if len(cases) > 10000:
        errors.append({"line": 10001, "message": "Maximum 10,000 cases per version"})
    return cases, errors


class TargetConfig(Contract):
    kind: Literal["http", "openai"] = "http"
    endpoint: str = ""
    instructions: str = ""
    output_schema: dict[str, Any] = Field(default_factory=dict)
    max_output_tokens: int = Field(default=2000, ge=256, le=16000)
    reasoning_effort: Literal["none", "low", "medium", "high", "xhigh"] = "low"
    method: Literal["POST"] = "POST"
    request_mapping: dict[str, str] = Field(default_factory=dict)
    output_pointer: str = "/output"
    trace_pointer: str | None = "/trace"
    metadata_pointer: str | None = "/metadata"
    usage_pointer: str | None = "/usage"
    cost_pointer: str | None = "/cost"
    credential_id: str | None = None
    auth_header: Literal["Authorization", "X-API-Key"] = "Authorization"
    auth_prefix: str = "Bearer "
    timeout_seconds: float = Field(default=20, ge=0.1, le=120)
    concurrency: int = Field(default=4, ge=1, le=16)
    requests_per_second: float = Field(default=10, gt=0, le=100)
    max_attempts: int = Field(default=3, ge=1, le=5)
    idempotency_header: Literal["Idempotency-Key"] | None = "Idempotency-Key"
    revision: str | None = None
    prompt_version: str | None = None
    model: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    fixture: bool = False

    @model_validator(mode="after")
    def provider_fields(self) -> "TargetConfig":
        if self.kind == "openai":
            from .openai_target import ENDPOINT, validate_schema

            if self.endpoint and self.endpoint != ENDPOINT:
                raise ValueError("OpenAI targets use the official Responses API endpoint")
            self.endpoint = ENDPOINT
            if (
                not self.model
                or not self.model.strip()
                or not self.instructions.strip()
                or not self.credential_id
            ):
                raise ValueError("OpenAI targets require a model, instructions and credential slot")
            if self.fixture or self.parameters or self.request_mapping:
                raise ValueError(
                    "OpenAI targets use explicit generation settings and complete case input"
                )
            if self.auth_header != "Authorization" or self.auth_prefix != "Bearer ":
                raise ValueError("OpenAI targets require Bearer authentication")
            validate_schema(self.output_schema)
        elif not self.endpoint:
            raise ValueError("HTTP targets require an endpoint")
        return self

    @field_validator("request_mapping")
    @classmethod
    def mapping(cls, value: dict[str, str]) -> dict[str, str]:
        if any(not k or "/" in k or (v and not v.startswith("/")) for k, v in value.items()):
            raise ValueError("Map fixed top-level request fields to JSON Pointers into case input")
        return value

    @field_validator(
        "output_pointer", "trace_pointer", "metadata_pointer", "usage_pointer", "cost_pointer"
    )
    @classmethod
    def pointer(cls, value: str | None) -> str | None:
        if value and not value.startswith("/"):
            raise ValueError("Expected a JSON Pointer beginning with /, or an empty root pointer")
        return value


class MetricDefinition(Contract):
    value_type: Literal["number", "boolean", "category"] = "number"
    direction: Literal["higher", "lower", "none"] = "higher"
    threshold: float | None = None
    required_inputs: list[str] = Field(default_factory=list)
    aggregation: Literal["mean", "pass_rate", "classification"] = "mean"


class EvaluatorConfig(Contract):
    kind: Literal[
        "json_schema",
        "exact_match",
        "field_comparison",
        "numeric_tolerance",
        "classification",
        "tool_calls",
        "llm_judge",
    ]
    metric_key: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_.-]+$")
    definition: MetricDefinition = Field(default_factory=MetricDefinition)
    config: dict[str, Any] = Field(default_factory=dict)
    max_attempts: int = Field(default=2, ge=1, le=5)


class Result(Contract):
    metric_key: str
    status: Literal["scored", "not_applicable", "error"]
    score: float | None = None
    value: Any = None
    passed: bool | None = None
    explanation: str
    evidence: list[str] = Field(default_factory=list)
    evaluator_version: str
    details: dict[str, Any] = Field(default_factory=dict)


class EvaluationInput(Contract):
    case_input: Any
    reference: Any = None
    reference_present: bool = False
    context: Any = None
    actual: Any
    trace: Any = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Judgment(Contract):
    score: float = Field(ge=0, le=1)
    passed: bool
    justification: str = Field(min_length=1, max_length=1000)
    evidence: list[str] = Field(max_length=10)


class ToolCall(Contract):
    name: str = Field(min_length=1, max_length=160)
    arguments: dict[str, Any] = Field(default_factory=dict)
    output: Any = None


class ObservableTrace(Contract):
    tool_calls: list[ToolCall] = Field(max_length=1000)


class ImportedOutput(Contract):
    case_id: str
    replicate: int = Field(default=0, ge=0)
    output: Any
    trace: ObservableTrace | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Launch(Contract):
    name: str = Field(min_length=1, max_length=160)
    dataset_version_id: str
    target_version_id: str | None = None
    suite_version_id: str
    repetitions: int = Field(default=1, ge=1, le=20)
    concurrency: int = Field(default=2, ge=1, le=16)
    mode: Literal["http", "imported"] = "http"
    imports: list[ImportedOutput] = Field(default_factory=list)
    import_dataset_version_id: str | None = None
    baseline_name: str = "main"
    max_target_calls: int | None = Field(default=None, ge=1)
    warmup: Literal[0] = 0

    @model_validator(mode="after")
    def mode_fields(self) -> "Launch":
        if self.mode == "http" and (not self.target_version_id or self.imports):
            raise ValueError(
                "HTTP runs require a target version and cannot contain imported outputs"
            )
        if self.mode == "imported" and self.import_dataset_version_id != self.dataset_version_id:
            raise ValueError("Imports must declare the exact dataset version")
        return self


class GateConfig(Contract):
    min_accuracy: dict[str, float] = Field(default_factory=dict)
    max_regressions: int = Field(default=0, ge=0)
    critical_tag: str = "critical"
    max_target_error_rate: float = Field(default=0, ge=0, le=1)
    min_coverage: float = Field(default=1, ge=0, le=1)
    evaluator_errors: Literal["fail", "infrastructure_error"] = "fail"
    max_p95_latency_ms: float | None = Field(default=None, gt=0)

    @field_validator("min_accuracy")
    @classmethod
    def thresholds(cls, value: dict[str, float]) -> dict[str, float]:
        if any(not 0 <= v <= 1 for v in value.values()):
            raise ValueError("Accuracy thresholds must be between 0 and 1")
        return value
