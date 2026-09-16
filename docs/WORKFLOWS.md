# Workflow guide

Run commands from the repository root unless stated otherwise.

## Start locally

Use Docker Compose v2 and Python 3.12+. Install uv if you also need the CLI or calibration scripts.

```bash
python3 scripts/configure.py
docker compose up -d --build
docker compose exec -T api uv run python -m evaldock.seed
```

Open [EvalDock](http://localhost:5188) and sign in as `demo@evaldock.local` using `DEMO_PASSWORD` from the root `.env`. Configuration generates local secrets with file mode 0600 and preserves an existing environment file. Seeding retains an existing workspace and password.

| Service | Local address |
| --- | --- |
| Web and proxied API | http://localhost:5188 |
| API documentation | http://localhost:8088/docs |
| Sample targets | http://localhost:8099 |
| PostgreSQL | 127.0.0.1:5492 |

Database and artifact volumes persist across restarts. `docker compose down` stops services; adding `-v` also deletes their volumes.

### Docker credential helper on WSL

If Docker cannot execute an inherited Windows credential helper, use a project-local configuration for the public images:

```bash
mkdir -p work/docker-config
printf '{}' > work/docker-config/config.json
DOCKER_CONFIG="$PWD/work/docker-config" docker compose up -d --build
```

This leaves the global Docker configuration unchanged. Keep the checkout in the WSL Linux filesystem for local development.

## Evaluate a change

1. In **Datasets**, inspect or import cases. JSONL validation identifies line errors and duplicate IDs. Enable **Reference output provided** to distinguish an explicit null from a missing reference. Saving creates a new version.
2. In **Targets**, configure the application endpoint, input mapping, credentials and request limits. **Test** sends only the selected case input. The reference and evaluator context stay out of target requests.
3. In **Evaluators**, configure criteria and group their versions into a suite. The sample projects include release suites and an offline fixture judge.
4. Launch a baseline using the selected dataset, target and suite. In the completed report, expand **Run details & actions** and select **Pin baseline**.
5. Launch a candidate with the same dataset and suite, then open **Compare**. Select a criterion and filter improvements, regressions or errors. The comparison retains the baseline selected at launch.
6. Open a case to inspect its output, source and evaluator evidence. Add a human assessment when needed; it does not replace the automated decision.
7. In **Release checks**, select the candidate and inspect the saved policy's result. Expand **Edit release policy** to change thresholds. Export JSON/JUnit or save a report artifact.

A completed run can fail a release gate. Aggregate improvement can also hide individual regressions, so inspect affected cases and coverage before accepting a change. [Metrics and policies](METRICS.md) defines the decisions and denominators.

To evaluate the same outputs with another suite, use **Rescore outputs** under **Run details & actions**. This creates a linked experiment without new target calls. Live AI evaluators can still incur provider charges.

The editors warn before discarding unsaved changes. Keyboard filters and mobile navigation support the same workflow. Drafts are not saved across browser crashes.

Screenshots: [comparison](screenshots/comparison-desktop.png), [case results](screenshots/results-desktop.png), [release checks](screenshots/release-checks-desktop.png).

## Example datasets

- [Synthetic controls](catalog-calibration-v2.md) exercise schema, field and whole-record decisions with known faults.
- [Catalog pilot](CATALOG-PILOT.md) compares rule-based extraction on sourced product passages.
- [AI setup](AI-READINESS.md) adds live structured generation and source-support judging to the catalog pilot.

Use [the test guide](TESTING.md) to run the fixture workflow and browser checks.

## CLI and CI

Install the CLI with `uv sync --frozen`. Create a workspace token in **Settings** and use its read/write scopes for the commands you need. Tokens expire and the plaintext is shown once.

```bash
export EVALDOCK_URL=http://localhost:5188
export EVALDOCK_TOKEN='your-scoped-token'
uv run evaldock projects
uv run evaldock upload PROJECT_ID 'My dataset' fixtures/catalog.jsonl
# For a subsequent version:
uv run evaldock upload PROJECT_ID 'My dataset' fixtures/catalog.jsonl --resource-id RESOURCE_ID
RUN_ID=$(uv run evaldock start PROJECT_ID DATASET_VERSION_ID SUITE_VERSION_ID 'CI candidate' --target TARGET_VERSION_ID --baseline main)
uv run evaldock wait "$RUN_ID" --timeout 600
uv run evaldock compare "$RUN_ID" --metric field_accuracy
uv run evaldock export "$RUN_ID" report.json --format json
uv run evaldock export "$RUN_ID" junit.xml --format junit
uv run evaldock gate "$RUN_ID" --metric field_accuracy
```

Exit **0** means the gate passed, **1** means a quality failure, and **2** means an infrastructure or configuration failure. Missing baselines, unknown metrics, unfinished experiments and incomparable requested latency measurements return exit 2. See [the CI example](../infra/evaluation-ci.yml).

## LLM judges

Judges use the OpenAI Responses API with Pydantic-validated responses. For a custom judge, save a credential in **Settings** and reference it in the evaluator:

```json
{
  "kind": "llm_judge",
  "metric_key": "answer_correctness",
  "max_attempts": 2,
  "config": {
    "mode": "live",
    "template": "correctness",
    "rubric": "The answer must be correct relative to the supplied reference. Unsupported claims fail; appropriate abstention passes.",
    "rubric_version": "correctness-v1",
    "model": "YOUR_SUPPORTED_STRUCTURED_OUTPUT_MODEL",
    "credential_id": "CREDENTIAL_ID",
    "parameters": {}
  }
}
```

The `correctness` template evaluates against a reference; `context_support` evaluates support in the supplied context. Judge instructions are separate from evaluated content, which is treated as untrusted data. Judges have no tools. Structured responses constrain the output format but do not guarantee sound judgments.

Fixture mode must be selected explicitly. Refusals, invalid responses and live errors never fall back to fixtures. Judge token usage is recorded separately from target usage; costs remain unavailable unless reported by a target or provider.
