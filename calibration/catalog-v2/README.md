# Synthetic catalog controls

Forty English cases for checking structured extraction and evaluator behavior. The pack contains supplied references, matching outputs and deliberate faults; it does not contain live model outputs.

## Files

| File | Purpose |
| --- | --- |
| `calibration.jsonl` | Thirty calibration cases across ten scenarios |
| `validation.jsonl` | Ten separate validation cases |
| `*-reference-outputs.json` | Positive controls matching the references |
| `*-challenge-outputs.json` | Correct outputs mixed with injected faults |
| `RUBRIC.md` | Output contract and extraction rules |
| `evaluators.json` | Deterministic criteria |
| `gate.json` | Release policy for the controls |
| `expected-decisions.json` | Expected outcomes for each challenge |
| `human-review.csv` | Reference review worksheet |
| `manifest.json` | Provenance and file hashes |

## Scenarios

The cases cover explicit facts, missing information, unit conversion, conflicting sources, packaging, sets, manufacturing origin, appearance, embedded instructions and JSON types.

The output requires `material`, `weight_g` and `country`. Missing facts use explicit null. Weight is numeric grams; country identifies manufacture. Matching is strict, so any synonym normalization must be defined before evaluation.

All positive controls should pass. The challenge contains twenty faulty calibration outputs and five faulty validation outputs. Schema and whole-record checks catch extra keys that field comparisons alone allow. See [results and interpretation](../../docs/catalog-calibration-v2.md).

## Reproduce

From the repository root, with the seeded local stack running:

```bash
uv sync --frozen
uv run python scripts/load_catalog_calibration.py
```

The loader validates file hashes and reuses matching resources and runs. It stops on divergent configuration and does not call targets or models.

The authoring script, `scripts/prepare_catalog_calibration.py`, regenerates the pack and its review worksheet. Use a new pack version for label or rubric changes rather than overwriting published evidence.

The validation split is separate but synthetic and visible during authoring. Review status is recorded in the worksheet; control scores do not measure model quality.
