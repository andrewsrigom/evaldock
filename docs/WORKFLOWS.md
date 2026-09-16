# Workflow guide

Detailed setup and usage for [EvalDock](../README.md). Run commands from the repository root unless stated otherwise.

## Start locally

Requires Docker Compose. Python and uv are needed only for local development and the CLI.

```bash
cd evaldock
python3 scripts/configure.py
docker compose up -d --build
docker compose exec -T api uv run python -m evaldock.seed
```

Open **http://localhost:5188**. Sign in as `demo@evaldock.local`. `scripts/configure.py` generates a random local password and encryption key in the ignored, mode-0600 `.env`. Retrieve your local password with `grep '^DEMO_PASSWORD=' .env`. The seed is idempotent and retains existing data and passwords.

On this WSL machine, Docker's inherited Windows credential helper could not execute. The working project-specific alternative is:

```bash
mkdir -p work/docker-config
printf '{}' > work/docker-config/config.json
DOCKER_CONFIG="$PWD/work/docker-config" docker compose up -d --build
```

This uses public images and does not modify your global Docker configuration. The project runs on the Linux filesystem at `/home/andrews/projects/evaldock`, not under `/mnt/c`.

| Service | Local address |
|---|---|
| Web and proxied API | http://localhost:5188 |
| FastAPI / OpenAPI | http://localhost:8088/docs |
| Sample targets | http://localhost:8099 |
| PostgreSQL | 127.0.0.1:5492 |

The Compose project is named `evaldock`. Database and artifact volumes persist across restarts. `docker compose down` stops services without deleting data. Do not add `-v` unless you intend to delete the local database and artifacts.

## Complete walkthrough

1. In **Datasets**, inspect the 24-case held-out dataset. Each case has JSON input, optional expected output/context, tags, slices and labeling notes. Use the guided case editor to add, duplicate and edit cases. Enable “Reference output provided” to distinguish an explicit null from a missing reference. Saving creates a new immutable version. Upload or paste JSONL, validate it, then apply the preview to the draft. Export any version through its download action.
2. In **Targets**, use the guided connection form to inspect the baseline and candidate HTTP adapters, credentials, mappings and request limits. The sample services are explicitly administrator-allowlisted. Use **Test** with a dataset case's input only. Target requests never include the reference or evaluator context.
3. In **Evaluators**, configure criteria through the guided forms, then choose named evaluator versions in **New suite**. The support project also computes classification confusion matrices and micro/macro metrics. A separate fixture judge suite supports calibration without a provider key.
4. Launch **Baseline · release v1** with the original dataset, baseline target, Release criteria suite, two repetitions and concurrency two. Wait for completion. Open its result, expand **Run details & actions**, and select **Pin baseline**.
5. Launch **Candidate · release v2** with the same dataset/suite and candidate target. The baseline ID is copied at launch; later baseline changes do not move this comparison reference.
6. Open **Compare**. Select the two runs and **Field accuracy**. Filter regressions, errors or tags. Inspect baseline and candidate side by side, expected output/context, field differences, evaluator explanations and trace data. A score improvement in the aggregate can coexist with critical case regressions.
7. Save a human assessment on a regression. Automated results remain intact. The experiment calibration section reports human agreement and disagreements, using the latest assessment per reviewer/case/metric.
8. Open candidate results, expand **Run details & actions**, choose the fixture judge suite and **Rescore outputs**. The new record links to the source experiment and reuses its outputs. It makes no target calls and reports no new target latency.
9. In **Release checks**, select the candidate to evaluate the saved policy. Expand **Edit release policy** to change thresholds. The deliberately regressed candidates fail. Download JSON/JUnit or persist a report artifact.
10. Switch to **Support triage** and repeat the same workflow with no engine changes.

For an automated demonstration using the real HTTP API and worker:

```bash
uv sync --frozen
uv run python scripts/demo_verify.py
```

This creates new runs, verifies both applications, imports observable agent traces, saves a human disagreement, asserts zero target calls during rescoring and verifies the CLI exit code. It writes `docs/verification.json` and example reports. It does not call a live model.

See [the UX revision and acceptance report](UX-REVIEW.md) for guided editors, keyboard/mobile behavior and the verified local workflows. Advanced JSON remains available for complex configuration.

## First local calibration pack

The [catalog-v2 pack](../calibration/catalog-v2/README.md) contains 40 explicitly synthetic English cases, proposed references pending human approval, six deterministic criteria and positive/negative imported-output controls. It exercises the local workflow before real-model calibration. See the [executed results and review guide](catalog-calibration-v2.md).

```bash
uv run python scripts/prepare_catalog_calibration.py
uv run python scripts/load_catalog_calibration.py
```

This creates a dedicated project through the API, preserves the original examples and never calls targets/models or records assistant decisions as human reviews. In projects without an HTTP target, the launcher defaults to imported outputs.

## Ready-to-use AI pilot

Set `OPENAI_API_KEY` in the project root `.env`, then run `docker compose up -d --no-deps --force-recreate api worker`. In **Catalog extraction · public-source pilot**, choose **New experiment → Launch experiment**. The model, extraction prompt, structured output schema and evaluation suite are already prepared.

To prepare the same pilot in a new installation:

```bash
uv run python scripts/load_public_catalog.py
uv run python scripts/configure_catalog_ai.py
docker compose up -d --no-deps --force-recreate api worker
```

The default run uses eight calibration inputs and up to eight AI reviews. Usage is billed by OpenAI. See [AI setup](AI-READINESS.md) for settings and verification limits. No API key is included in this repository.

## CLI and CI

Create a token in Settings. Tokens are hashed in the database, restricted to one workspace and a set of `read`/`write` scopes, and expire. The plaintext is shown once.

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

Exit **0** means the gate passed, **1** means a quality-gate failure, and **2** means infrastructure/configuration failure. A missing pinned baseline, unknown metric, unfinished experiment or incomparable requested latency measurement is a configuration failure. Coverage and evaluator errors have explicit policy. See `infra/evaluation-ci.yml` for an example.

## Real LLM judge

The backend integrates the OpenAI Responses API through the official async Python SDK and schema-validated Pydantic responses. No LangChain or LangGraph is required. Create an encrypted credential in Settings and use its ID in a new evaluator:

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

The other template is `context_support`: it checks support by supplied context, **not real-world truth**. Fixture mode must be selected explicitly. Live errors, schema failures and refusals never fall back to fixtures. Judge instructions occupy a separate system message; evaluated content is untrusted data. No tools are provided to the judge. This separation reduces injection risk but is not a proof that models resist every attack. Human calibration remains necessary.

Provider token usage is recorded separately from target usage. Costs remain unavailable unless supplied by a target/provider; there is no bundled price table. No live provider evaluation was performed without a user-provided credential.
