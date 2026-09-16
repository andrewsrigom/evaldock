import pytest
from evaldock.contracts import EvaluatorConfig, GateConfig
from evaldock.evaluators import validate_evaluator
from evaldock.measurement import aggregate, evaluate_gate
from test_evaluators import row


@pytest.mark.parametrize(
    "kind,config",
    [
        ("json_schema", {"schema": {"$ref": "http://169.254.169.254/secrets"}}),
        ("tool_calls", {"arguments": {"lookup": {"$ref": "https://example.com/schema"}}}),
        ("field_comparison", {"paths": ["/a", "/a"]}),
        ("numeric_tolerance", {"absolute": "almost"}),
        ("classification", {"labels": [1, 2]}),
    ],
)
def test_invalid_evaluator_configuration(kind, config):
    with pytest.raises(ValueError):
        validate_evaluator(EvaluatorConfig(kind=kind, metric_key="m", config=config))


def test_unknown_comparison_metric_cannot_pass_gate():
    executions = [row()]
    report = {
        "status": "completed",
        "baseline_id": "fixed",
        "executions": executions,
        "summary": aggregate(executions, {"m": {}}),
    }
    comparison = {
        "metric_key": "typo",
        "paired_count": 1,
        "changed": [],
        "added": [],
        "removed": [],
        "counts": {"unscored_or_error": 1},
        "latency_comparable": True,
    }
    decision = evaluate_gate(report, comparison, GateConfig())
    assert decision["exit_code"] == 2 and decision["passed"] is False
