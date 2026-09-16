# Catalog extraction decisions

The public-source pilot defines which facts belong to a product record when a passage mentions materials, weights or countries with different scopes.

| Ambiguity | Rule |
| --- | --- |
| Body and coating materials | Extract the primary body material; preserve an explicit grade or trade name |
| Bare and assembled weight | Use the assembly with its functional lid when stated; exclude storage sacks and shipping packaging |
| Grams and rounded ounces | Preserve the explicit metric value |
| Product and accessory origin | Extract the primary body's manufacturing country |
| Design or brand location | Do not treat it as manufacturing origin |
| Missing or conflicting evidence | Return null within the supplied evidence scope |

The [public-source rubric](../calibration/catalog-public-v1/RUBRIC.md) specifies the vocabulary and exact comparison rules. The [synthetic rubric](../calibration/catalog-v2/RUBRIC.md) also covers invalid types, unit conversions, conflicting evidence and instructions embedded in source text.

References are evaluated against the supplied passage. Review provenance is recorded with each pack; automated checks do not establish independent human agreement. The [pilot guide](CATALOG-PILOT.md) covers loading and comparing the examples.
