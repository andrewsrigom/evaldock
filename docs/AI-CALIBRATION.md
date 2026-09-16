# AI calibration

The catalog pilot uses `gpt-5.4-mini-2026-03-17` for structured extraction and source-support judgments. It evaluates the twelve cases in the [public-source pack](CATALOG-PILOT.md).

## Results

| Check | Recorded result |
| --- | --- |
| Correct judge controls | 8/8 accepted |
| Incorrect judge controls | 8/8 rejected |
| Judge control scores | Match the expected fraction |
| Calibration | 8/8 records pass all seven criteria |
| Calibration repeat | 8/8 records produce identical outputs |
| Validation | 4/4 records pass all seven criteria |
| Deterministic release gate | Passes with no regressions |

[Summary and usage](catalog-ai-v2/summary.json) · [Frozen plan](catalog-ai-v2/plan.json)

## Judge configuration

The [initial control run](catalog-ai-v1/controls.json) accepted two incorrect outputs and miscounted one score. The revised rubric checks each field against the source passage and defines the four possible scores.

The `context_only` input scope supplies the actual output and context, excluding the reference answer, original case input, trace and execution metadata. Control labels are not sent to the model. Earlier evaluator versions retain their original input contract.

Negative controls include incorrect assembly weight, lost material grade, body/accessory origin confusion, capacity interpreted as mass, unsupported country and invented material. Correct answers and mutations are recorded in the frozen plan.

## Result files

- [Judge controls](catalog-ai-v2/controls.json)
- [Calibration](catalog-ai-v2/calibration.json)
- [Repeatability](catalog-ai-v2/repeat.json)
- [Validation](catalog-ai-v2/validation.json)

Each file contains the saved outputs and decisions. Usage is recorded separately for targets and judges; no model calls were retried in these runs.

## Scope

This is a small, curated, non-blind pilot. Negative controls were reused during tuning, validation cases were visible during authoring, and references were not independently human-approved. The results do not establish performance on unseen catalogs. The AI judge is advisory; the release gate uses the six deterministic criteria.

## Resume without duplicate requests

With the local stack, pilot and credentials configured, check the saved configuration:

```bash
uv run python scripts/calibrate_catalog_ai.py preflight
```

Preflight makes no model calls. The `controls`, `calibration`, `repeat` and `validation` phases reuse named runs and stop on a changed plan or failed result. `summary` rebuilds the report. Live phases incur provider charges. Publish a new plan and resource versions for further tuning.

See [AI setup](AI-READINESS.md) for configuration and [Testing](TESTING.md) for application checks.
