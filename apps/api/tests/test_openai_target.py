import json

import pytest
from evaldock import targets
from evaldock.contracts import TargetConfig
from evaldock.openai_target import ENDPOINT, parse

SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": ["string", "null"]}},
    "required": ["answer"],
    "additionalProperties": False,
}


def config(**overrides):
    return TargetConfig.model_validate(
        {
            "kind": "openai",
            "model": "test-model",
            "instructions": "Extract from input only",
            "output_schema": SCHEMA,
            "credential_id": "test-slot",
            **overrides,
        }
    )


def payload(actual=None, **overrides):
    return {
        "id": "resp_test",
        "model": "actual-model",
        "status": "completed",
        "usage": {"input_tokens": 40, "output_tokens": 8},
        "output": [
            {"type": "reasoning", "summary": []},
            {
                "type": "message",
                "content": [
                    {"type": "output_text", "text": json.dumps(actual or {"answer": "observed"})}
                ],
            },
        ],
        **overrides,
    }


def mock_transport(monkeypatch, response_payload=None, status=200):
    captured = []

    async def dns(url):
        assert url == ENDPOINT
        return ["8.8.8.8"]

    class Response:
        content_type = "application/json"

        def __init__(self):
            self.status = status
            self.content = self

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def iter_chunked(self, size):
            yield json.dumps(response_payload or payload()).encode()

    class Client:
        def __init__(self, **kwargs):
            self.connector = kwargs["connector"]
            assert kwargs["trust_env"] is False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            await self.connector.close()

        def post(self, url, **kwargs):
            captured.append({"url": url, **kwargs})
            return Response()

    monkeypatch.setattr(targets, "validate_destination", dns)
    monkeypatch.setattr(targets.aiohttp, "ClientSession", Client)
    return captured


async def test_native_wire_contract_metadata_and_input_isolation(monkeypatch):
    captured = mock_transport(monkeypatch)
    result = await targets.invoke(
        config(), {"passage": "untrusted product facts"}, "stable-key", "test-secret"
    )
    sent = captured[0]
    assert sent["url"] == ENDPOINT and sent["allow_redirects"] is False
    assert sent["headers"]["Authorization"] == "Bearer test-secret"
    assert sent["headers"]["Idempotency-Key"] == "stable-key"
    body = sent["json"]
    assert json.loads(body["input"][0]["content"]) == {
        "untrusted_input": {"passage": "untrusted product facts"}
    }
    assert body["store"] is False and body["text"]["format"]["strict"] is True
    assert body["reasoning"] == {"effort": "low"} and body["max_output_tokens"] == 2000
    assert result["output"] == {"answer": "observed"}
    assert result["trace"] is None and result["target_latency_ms"] >= 0
    assert result["metadata"]["model"] == "actual-model"
    assert result["metadata"]["target_usage"]["input_tokens"] == 40
    assert result["metadata"]["target_cost"] is None
    assert "test-secret" not in json.dumps(result)


async def test_no_key_never_resolves_or_calls_provider(monkeypatch):
    async def forbidden(*args):
        pytest.fail("Missing key must be rejected before network access")

    monkeypatch.setattr(targets, "validate_destination", forbidden)
    with pytest.raises(ValueError, match="API key"):
        await targets.invoke(config(), {}, "key")


@pytest.mark.parametrize(
    "response",
    [
        payload(status="incomplete"),
        payload(
            output=[{"type": "message", "content": [{"type": "refusal", "refusal": "Unavailable"}]}]
        ),
        payload({"answer": 123}),
        payload(output=[]),
        payload(
            output=[
                {"type": "message", "content": [{"type": "output_text", "text": '{"answer": NaN}'}]}
            ]
        ),
    ],
)
def test_invalid_refused_or_incomplete_outputs_are_errors(response):
    with pytest.raises(ValueError):
        parse(response, SCHEMA)


@pytest.mark.parametrize(
    "overrides",
    [
        {"endpoint": "https://attacker.example/responses"},
        {"instructions": " "},
        {"model": ""},
        {"credential_id": None},
        {"output_schema": {"type": "object", "properties": {"a": {"$ref": "https://example.com"}}}},
        {
            "output_schema": {
                "type": "object",
                "properties": {"a": {"type": "string"}},
                "additionalProperties": False,
            }
        },
    ],
)
def test_invalid_target_contract(overrides):
    with pytest.raises(ValueError):
        config(**overrides)


async def test_provider_http_failure_is_not_a_result(monkeypatch):
    mock_transport(monkeypatch, status=401)
    with pytest.raises(ValueError, match="Target HTTP 401"):
        await targets.invoke(config(), {}, "key", "test-secret")
