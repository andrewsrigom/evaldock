# AI setup

Set `OPENAI_API_KEY` in the project root `.env`. The existing `OPENAI_CREDENTIAL_ID` binds that key to the prepared target and judge; keep it unchanged. The key stays in the server environment and is not copied into the database. `.env` is ignored by Git and excluded from images and source archives.

```dotenv
OPENAI_API_KEY=your-key-here
```

From the project directory, apply the changed environment to both processes:

```bash
docker compose up -d --no-deps --force-recreate api worker
```

Settings shows whether the key is configured. Other projects keep their own saved credentials. This local server key is not shared automatically with other projects, the sample targets or the frontend.

Then select **New experiment → Launch experiment**. Defaults select eight calibration cases, the saved extraction prompt and schema, six deterministic checks and one source-support AI review. One repetition makes up to eight generation requests and eight judge requests; provider usage is billed to your account. No automatic retries are configured for these presets.

Both roles use `gpt-5.4-mini-2026-03-17`, low reasoning effort and a 2,000-token output limit. The target sends only case input. The judge receives the saved output and evaluation evidence. Model settings, prompt and rubric are immutable versions editable through Targets and Evaluators. Incomplete, refused and invalid outputs remain errors; no reference-answer fallback exists.

No live model request was made during setup. Account access and actual model behavior still require the first run with your key. Review failures before tuning. The four existing validation cases were visible during authoring; independent human review and fresh cases are still needed for calibration. AI review is not included in the existing deterministic release gate.

Setup can be reproduced with `uv run python scripts/configure_catalog_ai.py` after loading the public-source pilot, then recreating the API and worker as above. Rerunning reuses matching versions and preserves existing `.env` secrets. Presets are in `examples/catalog_ai.json`.

API contract references: [GPT-5.4 mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini), [Structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs).
