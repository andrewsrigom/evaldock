"""Wait for local API readiness without shell-dependent polling."""

import time

import httpx

deadline = time.monotonic() + 90
while time.monotonic() < deadline:
    try:
        response = httpx.get("http://localhost:5188/api/health", timeout=3)
        if response.status_code == 200:
            print("EvalDock API ready")
            break
    except httpx.HTTPError:
        pass
    time.sleep(1)
else:
    raise SystemExit("API did not become ready within 90 seconds")
