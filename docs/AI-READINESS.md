# AI setup

In the **Catalog extraction · public-source pilot** project, open **Settings → OpenAI API key**, paste your key and select **Save API key**. The key is encrypted on the server and never returned. Saving does not call OpenAI or verify account access.

Then select **New experiment → Launch experiment**. Defaults select eight calibration cases, the saved extraction prompt and schema, six deterministic checks and one source-support AI review. One repetition makes up to eight generation requests and eight judge requests; provider usage is billed to your account. No automatic retries are configured for these presets.

Both roles use `gpt-5.4-mini-2026-03-17`, low reasoning effort and a 2,000-token output limit. The target sends only case input. The judge receives the saved output and evaluation evidence. Model settings, prompt and rubric are immutable versions editable through Targets and Evaluators. Incomplete, refused and invalid outputs remain errors; no reference-answer fallback exists.

No live model request was made during setup. Account access and actual model behavior still require the first run with your key. Review failures before tuning. The four existing validation cases were visible during authoring; independent human review and fresh cases are still needed for calibration. AI review is not included in the existing deterministic release gate.

Setup can be reproduced with `uv run python scripts/configure_catalog_ai.py` after loading the public-source pilot. Rerunning reuses matching versions and preserves any saved key. Presets are in `examples/catalog_ai.json`.

API contract references: [GPT-5.4 mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini), [Structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs).
