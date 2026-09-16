import asyncio

import pytest
from aiohttp import web
from evaldock.config import settings
from evaldock.contracts import ImportedOutput, TargetConfig
from evaldock.targets import invoke


async def test_real_http_boundaries_mapping_and_no_leakage(monkeypatch):
    captured = []

    async def handler(request):
        captured.append(await request.json())
        kind = request.match_info["kind"]
        if kind == "redirect":
            raise web.HTTPFound("http://169.254.169.254/latest/meta-data")
        if kind == "async":
            return web.json_response({"output": 1}, status=202)
        if kind == "stream":
            return web.Response(text="data: hello", content_type="text/event-stream")
        if kind == "large":
            return web.json_response({"output": "x" * 1000})
        if kind == "slow":
            await asyncio.sleep(0.3)
        if kind == "hidden":
            return web.json_response(
                {
                    "output": 1,
                    "trace": {"tool_calls": [], "hidden_chain_of_thought": "must not be exposed"},
                }
            )
        assert request.headers["Idempotency-Key"] == "stable-key"
        assert request.headers["Authorization"] == "Bearer test-secret"
        return web.json_response({"output": None, "usage": {"input_tokens": 5}})

    app = web.Application()
    app.router.add_post("/{kind}", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    origin = f"http://localhost:{port}"
    monkeypatch.setattr(settings(), "allowed_target_origins", origin)
    monkeypatch.setattr(settings(), "max_response_bytes", 200)
    try:
        loop = asyncio.get_running_loop()
        original = loop.getaddrinfo
        resolutions = []

        async def resolve(host, *args, **kwargs):
            resolutions.append(host)
            return await original("127.0.0.1", *args, **kwargs)

        monkeypatch.setattr(loop, "getaddrinfo", resolve)
        result = await invoke(
            TargetConfig(endpoint=origin + "/ok", request_mapping={"text": "/text"}),
            {"text": "public"},
            "stable-key",
            "test-secret",
        )
        assert result["output"] is None
        assert result["target_latency_ms"] >= 0
        assert result["metadata"]["target_usage"] == {"input_tokens": 5}
        assert "target_cost" not in result["metadata"]
        assert captured == [{"text": "public"}]
        assert resolutions == ["localhost"], "Connection must reuse validated DNS addresses"
        for kind in ["redirect", "async", "stream", "large", "hidden"]:
            with pytest.raises(ValueError):
                await invoke(
                    TargetConfig(endpoint=origin + "/" + kind), {}, "stable-key", "test-secret"
                )
        with pytest.raises(TimeoutError):
            await invoke(
                TargetConfig(endpoint=origin + "/slow", timeout_seconds=0.1),
                {},
                "stable-key",
                "test-secret",
            )
    finally:
        await runner.cleanup()


def test_import_trace_rejects_unobservable_fields():
    with pytest.raises(ValueError):
        ImportedOutput(
            case_id="a", output={}, trace={"tool_calls": [], "chain_of_thought": "private"}
        )
