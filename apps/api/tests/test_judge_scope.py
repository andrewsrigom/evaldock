import json
from types import SimpleNamespace

import pytest
from evaldock import evaluators
from evaldock.contracts import EvaluationInput, EvaluatorConfig, Judgment


@pytest.mark.parametrize("scope", [None, "evaluation", "context_only"])
async def test_evidence_only_judge_excludes_reference_and_unrelated_data(monkeypatch, scope):
    captured = {}

    class Client:
        def __init__(self, **kwargs):
            assert kwargs["max_retries"] == 0
            self.responses = self

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def parse(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                output_parsed=Judgment(
                    score=2 / 3,
                    passed=False,
                    justification="The supplied weight does not match the passage.",
                    evidence=["Weight: 177.25 g"],
                ),
                usage=None,
            )

    monkeypatch.setattr(evaluators, "AsyncOpenAI", Client)
    config = {
        "mode": "live",
        "template": "context_support",
        "model": "test-model",
        "credential_id": "test-slot",
        "rubric": "Check actual against context",
        "rubric_version": "test-v2",
    }
    if scope:
        config["input_scope"] = scope
    ev = EvaluatorConfig(kind="llm_judge", metric_key="support", config=config)
    evaluators.validate_evaluator(ev)
    data = EvaluationInput(
        case_input="PRIVATE_INPUT",
        actual={"weight_g": 32},
        reference={"weight_g": 177.25},
        reference_present=True,
        context={"reference_passage": "Weight: 177.25 g"},
        trace={"private": "PRIVATE_TRACE"},
        metadata={"private": "PRIVATE_METADATA"},
    )
    result = (await evaluators.evaluate(ev, "test-version", data, "test-key"))[0]
    sent = json.loads(captured["input"][1]["content"])["untrusted_evaluation_data"]
    if scope == "context_only":
        assert sent == {"actual": {"weight_g": 32}, "context": data.context}
        assert "PRIVATE_" not in captured["input"][1]["content"]
        assert "reference_present" not in sent and "reference" not in sent
    else:
        assert sent == data.model_dump()
    assert captured["store"] is False
    assert result.passed is False and result.score == pytest.approx(2 / 3)
    assert result.details["judge_input_scope"] == (scope or "evaluation")


@pytest.mark.parametrize(
    "template,scope", [("correctness", "context_only"), ("context_support", "invalid")]
)
def test_invalid_judge_scope_is_rejected(template, scope):
    ev = EvaluatorConfig(
        kind="llm_judge",
        metric_key="support",
        config={
            "mode": "live",
            "template": template,
            "input_scope": scope,
            "model": "test-model",
            "credential_id": "test-slot",
            "rubric": "Check evidence",
            "rubric_version": "test-v2",
        },
    )
    with pytest.raises(ValueError):
        evaluators.validate_evaluator(ev)
