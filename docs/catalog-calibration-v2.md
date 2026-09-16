# Synthetic catalog controls

The [catalog-v2 pack](../calibration/catalog-v2/README.md) contains forty synthetic cases: thirty for calibration and ten for validation. Imported positive controls match the references; challenge outputs introduce known faults. These tests exercise evaluator behavior without target or model calls.

## Expected decisions

| Result | Calibration | Validation |
| --- | ---: | ---: |
| Positive controls passing all six criteria | 30/30 | 10/10 |
| Faulty records detected | 20/20 | 5/5 |
| Correct records in the mixed challenge | 10/30 | 5/10 |
| Metric coverage | 100% | 100% |
| Challenge gate | Fails | Fails |

The [saved results](catalog-calibration-v2.json) record the decisions. The [expected-decision manifest](../calibration/catalog-v2/expected-decisions.json) defines the outcome for each challenge. This is control evidence, not a model-quality measurement.

## Inspect a comparison

Load the pack using its [setup commands](../calibration/catalog-v2/README.md#reproduce), then open **Compare** in **Catalog calibration · synthetic v2**.

- Select **Exact record** to detect incorrect values, missing fields and extra keys.
- Select **Field accuracy** to inspect individual values. This criterion alone does not reject extra keys.
- Open a case to compare the passage, reference and output. Human assessments remain separate from automated scores.

The cases include missing versus null, unit conversion, packaging and set weights, manufacturing origin, conflicting evidence and embedded instructions. The [rubric](../calibration/catalog-v2/RUBRIC.md) defines the exact rules.

Reference review is recorded in [human-review.csv](../calibration/catalog-v2/human-review.csv). Corrections require a new dataset version. The validation split is separate but visible and synthetic; it is not a blind estimate of real-world accuracy.
