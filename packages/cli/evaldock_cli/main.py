import json
import os
import time
from pathlib import Path
from typing import Any

import httpx
import typer

app = typer.Typer(
    pretty_exceptions_show_locals=False,
    help="EvalDock CI client. Exit codes: 0 pass; 1 quality gate; 2 infrastructure/configuration.",
)


def request(method: str, path: str, **kwargs: Any) -> Any:
    token = os.environ.get("EVALDOCK_TOKEN")
    if not token:
        typer.echo("Infrastructure error: EVALDOCK_TOKEN is required", err=True)
        raise typer.Exit(2)
    url = os.environ.get("EVALDOCK_URL", "http://localhost:5188").rstrip("/") + path
    try:
        with httpx.Client(timeout=130, headers={"Authorization": f"Bearer {token}"}) as client:
            response = client.request(method, url, **kwargs)
            response.raise_for_status()
            return (
                response.json()
                if "json" in response.headers.get("content-type", "")
                else response.text
            )
    except (httpx.HTTPError, ValueError) as exc:
        status = getattr(getattr(exc, "response", None), "status_code", "transport")
        typer.echo(f"Infrastructure/configuration error: request failed ({status})", err=True)
        raise typer.Exit(2) from None


@app.command()
def projects():
    typer.echo(json.dumps(request("GET", "/api/projects"), indent=2))


@app.command()
def upload(
    project: str, name: str, file: Path, resource_id: str | None = None, held_out: bool = True
):
    if not file.is_file():
        typer.echo("Dataset file not found", err=True)
        raise typer.Exit(2)
    preview = request("POST", "/api/datasets/preview", json={"content": file.read_text()})
    if preview["errors"]:
        typer.echo(json.dumps(preview["errors"], indent=2), err=True)
        raise typer.Exit(2)
    data = {"config": {"held_out": held_out}, "cases": preview["cases"]}
    if resource_id:
        result = request("POST", f"/api/resources/{resource_id}/versions", json=data)
    else:
        result = request(
            "POST",
            f"/api/projects/{project}/resources",
            json={**data, "kind": "dataset", "name": name},
        )
    typer.echo(json.dumps(result, indent=2))


@app.command()
def start(
    project: str,
    dataset: str,
    suite: str,
    name: str,
    target: str | None = None,
    imports: Path | None = None,
    repetitions: int = 1,
    concurrency: int = 2,
    baseline: str = "main",
):
    data: dict[str, Any] = {
        "name": name,
        "dataset_version_id": dataset,
        "suite_version_id": suite,
        "target_version_id": target,
        "repetitions": repetitions,
        "concurrency": concurrency,
        "baseline_name": baseline,
    }
    if imports:
        try:
            bundle = json.loads(imports.read_text())
            data.update(
                mode="imported",
                imports=bundle["outputs"],
                import_dataset_version_id=bundle["dataset_version_id"],
            )
        except (OSError, ValueError, KeyError):
            typer.echo("Invalid import bundle", err=True)
            raise typer.Exit(2) from None
    result = request("POST", f"/api/projects/{project}/experiments", json=data)
    typer.echo(result["id"])


@app.command()
def wait(experiment: str, timeout: int = 600):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = request("GET", f"/api/experiments/{experiment}")
        if result["status"] not in {"queued", "running"}:
            typer.echo(
                json.dumps(
                    {"id": experiment, "status": result["status"], "summary": result["summary"]},
                    indent=2,
                )
            )
            if result["status"] not in {"completed", "partially_failed"}:
                raise typer.Exit(2)
            return
        time.sleep(2)
    typer.echo("Infrastructure error: timed out waiting for experiment", err=True)
    raise typer.Exit(2)


@app.command()
def compare(experiment: str, metric: str = "field_accuracy"):
    result = request("GET", f"/api/experiments/{experiment}")
    if not result["baseline_id"]:
        typer.echo("No baseline was pinned at evaluation start", err=True)
        raise typer.Exit(2)
    result = request(
        "GET",
        "/api/compare",
        params={"baseline": result["baseline_id"], "candidate": experiment, "metric": metric},
    )
    typer.echo(json.dumps(result, indent=2))


@app.command()
def gate(experiment: str, metric: str = "field_accuracy"):
    result = request("GET", f"/api/experiments/{experiment}/gate", params={"metric": metric})
    typer.echo(json.dumps(result, indent=2))
    raise typer.Exit(result["exit_code"])


@app.command()
def export(experiment: str, output: Path, format: str = "json", metric: str = "field_accuracy"):
    if format not in {"json", "junit"}:
        raise typer.BadParameter("format must be json or junit")
    result = request(
        "GET", f"/api/experiments/{experiment}/report", params={"metric": metric, "format": format}
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) if isinstance(result, dict) else result)
    typer.echo(str(output))


if __name__ == "__main__":
    app()
