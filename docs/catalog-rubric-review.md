# Catalog rubric review

Reviewed on 2026-09-16 by the assistant under delegated implementation authority.

All thirty synthetic v2 calibration passages and references were read against the v2 rubric. Their labels are internally consistent: explicit facts, unknown values, kilogram conversion, equally authoritative conflicts, net versus packaging mass, single-item versus set mass, manufacturing versus brand/design country, appearance versus material, hostile embedded instructions and numeric zero. The per-case ledger is `catalog-v2-assistant-review.csv`. No reference or historical result was rewritten. The ten visible validation examples remain control evidence, not a blind assessment.

## Findings resolved for public-source v1

| Gap in applying v2 to real products | Decision in the separate public-source rubric |
|---|---|
| Functional lid versus packaging | Use assembly weight when explicitly distinguished; exclude shipping packaging and storage sacks |
| Rounded ounces alongside metric grams | Preserve the manufacturer's explicit grams; do not silently recompute them |
| Body and accessory have different origins | Define country for the primary body and preserve accessory evidence in context |
| Grade, trade name and spelling variants | Version a small canonical vocabulary; retain grade 1 and Tritan Renew; map polyethylene wording to HDPE |
| Country absent in selected specification | Return null within the supplied evidence; do not assert that no origin exists elsewhere on the site |
| Authored labels mistaken for human approval | Mark assistant review explicitly and keep independent human approval pending |
| Passing controls mistaken for production quality | Separate controls, real factual paraphrases and actual model results; qualify every result by its input scope |

These decisions apply only to the new pack. The synthetic controls remain useful for evaluator behavior, including adversarial instructions and invalid types, but cannot validate a live model. The local example parser is deliberately narrower than the full synthetic rubric and is not claimed to handle arbitrary text, web scraping or all materials/countries.

## Completion decision

The local workbench and the first public-source pilot are ready for use. The two offline implementations, preserved outputs, versioned criteria, paired comparison, gates and persisted reports are reproducible. No additional UI redesign or new project integration is required to begin the AI phase.

Independent label review, a fresh validation sample, a selected provider/model and a configured credential remain necessary before claiming calibrated AI quality. These are separate evidence requirements; the application itself is not blocked by the absence of a live model run.
