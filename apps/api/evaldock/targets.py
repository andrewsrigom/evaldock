import asyncio
import ipaddress
import socket
import time
from typing import Any
from urllib.parse import urlsplit

import aiohttp
from aiohttp.abc import AbstractResolver

from . import openai_target
from .config import settings
from .contracts import ObservableTrace, TargetConfig

MISSING = object()


def pointer(value: Any, path: str, default: Any = MISSING) -> Any:
    if path == "":
        return value
    if not path.startswith("/"):
        raise ValueError("Invalid JSON Pointer")
    for token in path[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(value, dict) and token in value:
            value = value[token]
        elif (
            isinstance(value, list)
            and token.isdigit()
            and (token == "0" or not token.startswith("0"))
            and int(token) < len(value)
        ):
            value = value[int(token)]
        else:
            return default
    return value


def request_body(case_input: Any, mapping: dict[str, str]) -> Any:
    if not mapping:
        return case_input
    body = {}
    for key, path in mapping.items():
        value = pointer(case_input, path)
        if value is MISSING:
            raise ValueError(f"Input mapping path missing: {path}")
        body[key] = value
    return body


async def validate_destination(url: str) -> list[str]:
    parts = urlsplit(url)
    if (
        parts.scheme not in {"http", "https"}
        or not parts.hostname
        or parts.username
        or parts.password
        or parts.fragment
    ):
        raise ValueError("Only HTTP(S) endpoints without credentials or fragments are supported")
    # Query strings can carry secrets: require credentials in the server-side credential store.
    if parts.query:
        raise ValueError("Query strings are not supported; use JSON inputs and credential headers")
    host = parts.hostname.lower().rstrip(".")
    if host in {"metadata.google.internal", "metadata", "instance-data"}:
        raise ValueError("Metadata destinations are blocked")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    origin = f"{parts.scheme}://{parts.netloc}"
    allowed = origin in {
        x.strip() for x in settings().allowed_target_origins.split(",") if x.strip()
    }
    try:
        infos = await asyncio.wait_for(
            asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM), timeout=5
        )
    except (OSError, TimeoutError) as exc:
        raise ValueError("Endpoint DNS resolution failed") from exc
    addresses = sorted({str(info[4][0]) for info in infos})
    if not addresses:
        raise ValueError("Endpoint DNS has no addresses")
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        if (
            ip.is_link_local
            or ip.is_multicast
            or ip.is_unspecified
            or str(ip) in {"100.100.100.200", "169.254.169.254"}
        ):
            raise ValueError("Metadata/link-local destinations are blocked")
        if not ip.is_global and not allowed:
            raise ValueError("Private/local destinations require an administrator allowlist entry")
    return addresses


class PinnedResolver(AbstractResolver):
    def __init__(self, addresses: list[str]):
        self.addresses = addresses

    async def resolve(self, host: str, port: int = 0, family: int = socket.AF_INET) -> list[Any]:
        return [
            {
                "hostname": host,
                "host": ip,
                "port": port,
                "family": socket.AF_INET6 if ":" in ip else socket.AF_INET,
                "proto": 0,
                "flags": socket.AI_NUMERICHOST,
            }
            for ip in self.addresses
        ]

    async def close(self) -> None:
        return None


async def invoke(
    config: TargetConfig, case_input: Any, idempotency_key: str, secret: str | None = None
) -> dict[str, Any]:
    if config.kind == "openai" and not secret:
        raise ValueError("OpenAI API key is not configured")
    addresses = await validate_destination(config.endpoint)
    headers = {"Accept": "application/json"}
    if config.idempotency_header:
        headers[config.idempotency_header] = idempotency_key
    if secret:
        headers[config.auth_header] = config.auth_prefix + secret
    connector = aiohttp.TCPConnector(
        resolver=PinnedResolver(addresses), use_dns_cache=False, limit=1
    )
    started = time.perf_counter()
    timeout = aiohttp.ClientTimeout(total=config.timeout_seconds)
    async with aiohttp.ClientSession(
        connector=connector, timeout=timeout, trust_env=False
    ) as client:
        async with client.post(
            config.endpoint,
            json=openai_target.request(config, case_input)
            if config.kind == "openai"
            else request_body(case_input, config.request_mapping),
            headers=headers,
            allow_redirects=False,
        ) as response:
            if response.status == 202 or 300 <= response.status < 400:
                raise ValueError("Asynchronous responses and redirects are unsupported")
            if response.status >= 400:
                raise ValueError(f"Target HTTP {response.status}")
            if response.content_type != "application/json":
                raise ValueError("Only non-streaming JSON responses are supported")
            chunks, length = [], 0
            async for chunk in response.content.iter_chunked(65536):
                length += len(chunk)
                if length > settings().max_response_bytes:
                    raise ValueError("Target response exceeds configured size limit")
                chunks.append(chunk)
            import json

            payload = json.loads(b"".join(chunks))
    latency = (time.perf_counter() - started) * 1000
    if config.kind == "openai":
        return {
            "output": openai_target.parse(payload, config.output_schema),
            "trace": None,
            "target_latency_ms": latency,
            "metadata": {
                "provider": "openai",
                "model": payload.get("model", config.model),
                "requested_model": config.model,
                "response_id": payload.get("id"),
                "prompt_version": config.prompt_version,
                "revision": config.revision,
                "parameters": {
                    "reasoning_effort": config.reasoning_effort,
                    "max_output_tokens": config.max_output_tokens,
                },
                "fixture": False,
                "target_usage": payload.get("usage"),
                "target_cost": None,
                "target_cost_provenance": "unavailable",
            },
        }
    output = pointer(payload, config.output_pointer)
    if output is MISSING:
        raise ValueError("Response output mapping is missing")
    metadata: dict[str, Any] = {
        "revision": config.revision,
        "prompt_version": config.prompt_version,
        "model": config.model,
        "parameters": config.parameters,
        "fixture": config.fixture,
    }
    for key, path in [
        ("model_metadata", config.metadata_pointer),
        ("target_usage", config.usage_pointer),
        ("target_cost", config.cost_pointer),
    ]:
        if path is not None:
            value = pointer(payload, path)
            if value is not MISSING:
                metadata[key] = value
                if key == "target_cost":
                    metadata["target_cost_provenance"] = "provider_reported"
    raw_trace = (
        pointer(payload, config.trace_pointer, None) if config.trace_pointer is not None else None
    )
    trace = (
        ObservableTrace.model_validate(raw_trace).model_dump(exclude_unset=True)
        if raw_trace is not None
        else None
    )
    return {"output": output, "trace": trace, "metadata": metadata, "target_latency_ms": latency}
