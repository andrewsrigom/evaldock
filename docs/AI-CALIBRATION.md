# AI calibration

Completed on 2026-09-16 for the public-source catalog pilot. Model: `gpt-5.4-mini-2026-03-17` for extraction and evidence review. The extraction prompt and the twelve published cases were unchanged.

| Check | Result |
| --- | --- |
| Correct judge controls | 8/8 accepted |
| Incorrect judge controls | 8/8 rejected |
| Judge control scores | All match the expected fraction |
| Calibration | 8/8 records, all seven criteria passed |
| Calibration repeat | 8/8 records, identical outputs |
| Separate validation | 4/4 records, all seven criteria passed |
| Deterministic release checks | Passed, no regressions |

## Correction found during calibration

The initial judge accepted two deliberately incorrect outputs and miscounted one score. That attempt is preserved in [the original results](catalog-ai-v1/controls.json).

The revised, explicitly versioned `context_only` input excludes the reference answer, original case input, trace and execution metadata. The judge receives the actual output and context. Its rubric now compares each actual field with the source passage and defines the four possible scores. Older evaluator versions retain their existing input contract.

The revised controls include wrong assembly weight, lost material grade, design/body/accessory origin confusion, capacity or ounces used as grams, unsupported country, and invented material. Correct answers and mutations are frozen in [the execution plan](catalog-ai-v2/plan.json); control labels are not sent to the model.

## Saved runs

- [Judge controls](http://localhost:5188/experiments/7be2e3dc-5b0a-483c-bb86-5882c4a3448d)
- [Calibration](http://localhost:5188/experiments/f4dce92b-5d2d-4602-b753-5f48f303b2ab)
- [Calibration repeat](http://localhost:5188/experiments/9927f8c6-85ce-41d8-ba22-470cc7d116cf)
- [Validation](http://localhost:5188/experiments/200694b1-c14f-47fd-8b32-6c8aea346d4e)

The API and worker performed 72 live requests in this calibration: 20 generations and 52 judgments, including the failed initial control round. Provider-reported usage totals 46,654 input and 9,775 output tokens. No dollar cost is claimed. No model calls were retried. Detailed results and usage are in [summary.json](catalog-ai-v2/summary.json).

## Verification and scope

78 backend tests, the AI setup browser journey, Python type checking and lint passed. The key remains in the server environment, scoped to the prepared project credential. The credential database entry is empty; the key was absent from the checked logs and reports, and `.env` was absent from the runtime images. See [verification.json](catalog-ai-v2/verification.json).

This is an initial calibration on a small, curated pilot. The negative controls were reused when tuning the judge, the separate validation split was visible during authoring, and references have not received independent human approval. Results do not establish performance on unseen catalogs. The AI judge remains advisory; the release gate still uses the six deterministic criteria.

## Resume without duplicate requests

Run `uv run python scripts/calibrate_catalog_ai.py preflight` from the repository root. The `controls`, `calibration`, `repeat`, and `validation` phases reuse their named runs and stop on a changed plan or failed result; they do not automatically retry calls. `summary` rebuilds the report. Publish new versions and a new plan for further tuning.
