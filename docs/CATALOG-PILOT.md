# Catalog extraction pilot

The pilot uses twelve product passages derived from TOAKS and Nalgene manufacturer pages. Each case includes a source URL, expected material, weight and country, and the rationale for those values. Eight cases form the calibration split; four form a separate validation split.

## Offline comparison

Two implementations in [catalog_rules.py](../examples/catalog_rules.py) read only the supplied passage. The baseline selects the first matching mention. The candidate distinguishes body material, assembly weight and manufacturing origin.

| Split | Baseline exact records | Candidate exact records | Regressions |
| --- | ---: | ---: | ---: |
| Calibration | 4/8 | 8/8 | 0 |
| Validation | 2/4 | 4/4 | 0 |

These are rule-based extraction results, not model scores. The [saved report](catalog-public-v1.json) contains outputs, metric decisions and run identifiers. The separate [AI calibration](AI-CALIBRATION.md) uses the same inputs with live generation and judging.

## Load the pilot

Start and seed the stack using the [quick start](../README.md#quick-start), then run:

```bash
uv sync --frozen
uv run python scripts/load_public_catalog.py
```

The loader checks file hashes, creates the project and reuses matching versions and runs. It stops if existing configuration differs. In **Catalog extraction · public-source pilot**, open **Compare** and select a baseline and candidate from the same split. Use **Exact record** to inspect changed decisions and **Release checks** to view the gate result.

To add the OpenAI target and judge, follow [AI setup](AI-READINESS.md).

## Evidence and scope

[Source records](../calibration/catalog-public-v1/sources.json) contain the observations and label rationale. The [rubric](../calibration/catalog-public-v1/RUBRIC.md) defines extraction rules; the [manifest](../calibration/catalog-public-v1/manifest.json) freezes the pack and records its provenance and review status.

The passages are curated paraphrases, not raw web pages. Both splits were visible during authoring. Results apply to these cases and do not measure performance on unseen catalogs. Changes to inputs, references or extraction rules require a new version.
