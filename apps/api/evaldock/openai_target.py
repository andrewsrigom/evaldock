"""Native Responses API contract; generation receives case input only."""

import json
from typing import Any

from jsonschema import Draft202012Validator, SchemaError

ENDPOINT = "https://api.openai.com/v1/responses"


def validate_schema(schema: dict[str, Any]) -> None:
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise ValueError("Invalid output JSON schema") from exc
    if schema.get("type") != "object" or "anyOf" in schema:
        raise ValueError("OpenAI output schema must be an object")

    def visit(value: Any) -> None:
        if not isinstance(value, dict):
            return
        for key in ("$ref", "$dynamicRef"):
            if key in value and not str(value[key]).startswith("#"):
                raise ValueError("Schema references must be local fragments")
        unsupported = {
            "allOf",
            "not",
            "dependentRequired",
            "dependentSchemas",
            "if",
            "then",
            "else",
        }
        if unsupported.intersection(value):
            raise ValueError("Unsupported structured output schema keyword")
        types = value.get("type", [])
        if types == "object" or "object" in types or "properties" in value:
            if value.get("additionalProperties") is not False:
                raise ValueError("Each output object must set additionalProperties to false")
            if set(value.get("required", [])) != set(value.get("properties", {})):
                raise ValueError("All output properties must be required; use nullable fields")
        for keyword in ("properties", "$defs", "definitions", "patternProperties"):
            for child in value.get(keyword, {}).values():
                visit(child)
        for keyword in ("items", "contains", "additionalProperties", "propertyNames"):
            visit(value.get(keyword))
        for keyword in ("anyOf", "oneOf", "prefixItems"):
            for child in value.get(keyword, []):
                visit(child)

    visit(schema)


def request(config: Any, case_input: Any) -> dict[str, Any]:
    return {
        "model": config.model,
        "instructions": config.instructions,
        "input": [
            {
                "role": "user",
                "content": json.dumps(
                    {"untrusted_input": case_input}, ensure_ascii=False, allow_nan=False
                ),
            }
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "evaldock_output",
                "strict": True,
                "schema": config.output_schema,
            }
        },
        "reasoning": {"effort": config.reasoning_effort},
        "max_output_tokens": config.max_output_tokens,
        "store": False,
    }


def parse(payload: Any, schema: dict[str, Any]) -> Any:
    if not isinstance(payload, dict) or payload.get("status") != "completed":
        raise ValueError("OpenAI response did not complete")
    texts = []
    for item in payload.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "refusal":
                raise ValueError("OpenAI refused this input")
            if content.get("type") == "output_text":
                texts.append(content["text"])
    if len(texts) != 1:
        raise ValueError("OpenAI response must contain one structured output")

    def invalid_constant(value: str) -> None:
        raise ValueError("Non-finite JSON number")

    try:
        output = json.loads(texts[0], parse_constant=invalid_constant)
        # Reject numeric overflow (for example 1e999), as well as NaN/Infinity literals.
        json.dumps(output, allow_nan=False)
        Draft202012Validator(schema).validate(output)
    except Exception as exc:
        raise ValueError("OpenAI returned an invalid structured output") from exc
    return output
