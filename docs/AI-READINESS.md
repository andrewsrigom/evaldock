# AI setup

The catalog pilot supports OpenAI generation and source-support judging. The API key stays in the server environment and is shared only by the project's configured target and judge.

## Prepare the pilot

With the [seeded stack](../README.md#quick-start) running, execute from the repository root:

```bash
uv sync --frozen
uv run python scripts/load_public_catalog.py
uv run python scripts/configure_catalog_ai.py
```

Setup creates the target, judge and suite from [the preset](../examples/catalog_ai.json). It reuses matching versions and preserves existing `.env` secrets. Setup makes no model requests.

## Configure the key

Set `OPENAI_API_KEY` in the root `.env`. Keep the `OPENAI_CREDENTIAL_ID` written by the setup script; it binds the key to the prepared project credential.

```dotenv
OPENAI_API_KEY=your-key-here
```

Apply the environment to both server processes:

```bash
docker compose up -d --no-deps --force-recreate api worker
```

**Settings** shows whether the key is configured. The key is not copied into the credential database, frontend or sample targets. Other projects use their own saved credentials. `.env` is excluded from Git and Docker images.

## Run an experiment

Open **Catalog extraction · public-source pilot** and select **New experiment**. The defaults use eight calibration cases, six deterministic criteria and one source-support judge. One repetition makes up to eight generation and eight judge requests, billed by the provider. These presets have no automatic model retries.

Both roles use `gpt-5.4-mini-2026-03-17`, low reasoning effort and a 2,000-token output limit. Model, prompt and rubric changes create new resource versions. The target receives only case input; the judge receives the saved output and source context. Refused, incomplete or invalid responses remain errors.

The AI judge is advisory. The pilot's release gate uses deterministic criteria. See [calibration results and scope](AI-CALIBRATION.md) for the saved model runs.
