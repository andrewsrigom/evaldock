import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

app = FastAPI(title="EvalDock deterministic fixture targets")
responses = json.loads((Path(__file__).parent / "responses.json").read_text())
call_count = 0


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
    identity: str | None = None
    passage: str | None = None
    text: str | None = None
    delay_ms: int = Field(default=0, ge=0, le=10000)


@app.get("/health")
async def health():
    return {"mode": "deterministic_fixture", "calls_since_process_start": call_count}


@app.post("/{application}/{variant}")
async def target(
    application: str, variant: str, body: Input, idempotency_key: str | None = Header(default=None)
) -> dict[str, Any]:
    global call_count
    if application not in {"catalog", "support"} or variant not in {"baseline", "candidate"}:
        raise HTTPException(404, "Unknown fixture target")
    call_count += 1
    await asyncio.sleep(body.delay_ms / 1000)
    key = body.identity if application == "catalog" else body.text
    output = responses.get(application, {}).get(variant, {}).get(key)
    if output is None:
        raise HTTPException(422, "Input is not in this deterministic demonstration fixture")
    return {
        "output": output,
        "metadata": {
            "fixture": True,
            "revision": f"{application}-{variant}-v1",
            "idempotency_key_received": idempotency_key is not None,
        },
    }
