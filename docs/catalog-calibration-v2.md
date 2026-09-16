# Catalog calibration v2 — English revision

[Open project](http://localhost:5188/projects/93549e1a-fd0f-41cc-9d54-d91159125a6b/overview) · [Compare controls](http://localhost:5188/projects/93549e1a-fd0f-41cc-9d54-d91159125a6b/compare) · [Human review queue](http://localhost:5188/projects/93549e1a-fd0f-41cc-9d54-d91159125a6b/reviews)

## Scope and provenance

**Catalog calibration · synthetic v2** has 40 English cases, two immutable datasets (30 calibration and ten validation cases), six deterministic evaluators, one suite and four completed imported-output experiments. All references were proposed by the assistant and still require independent human approval. No live model was called.

The first pack accidentally introduced Portuguese into tracked fixtures, scripts, documentation and local database records in commit `7c4feea`. The application interface itself remained English. No Git remote was configured and no push occurred. This revision corrects current source files and creates English evaluation evidence without rewriting historical results. The old v1 records remain in the local database, so old experiment links still show their original Portuguese content.

The output contract requires exactly `material`, `weight_g` and `country`, including explicit null when appropriate. Scenarios cover missing information, conflicting sources, units, packaging, sets, manufacturing origin, appearance, embedded malicious instructions and zero/types.

## Verified results

| Result | Calibration | Validation |
|---|---:|---:|
| Distinct cases | 30 | 10 |
| Positive controls passing all six criteria | 30/30 | 10/10 |
| Deliberately faulty records detected | 20/20 | 5/5 |
| Correct records in the mixed challenge | 10/30 | 5/10 |
| Coverage for all six metrics | 100% | 100% |
| Execution/evaluator errors | 0 | 0 |
| Challenge gate | Fails as expected | Fails as expected |

All **480 decisions** (80 executions × six metrics) matched the expected-decision manifest. These are authored control outcomes, not model-performance measurements. Both challenge reports were persisted as artifacts. No target or model calls were made, and no human approvals were fabricated.

## Review workflow

1. In **Compare**, choose `record_exact`. The default 30-case comparison has 20 regressions and ten unchanged passes. `field_accuracy` has 18 regressions because two outputs have correct fields plus a forbidden extra key.
2. Inspect `catalog-v2-02-01` (omitted key versus null), `catalog-v2-03-01` (kilograms versus grams), `catalog-v2-07-01` (design versus manufacture) and `catalog-v2-09-01` (embedded instruction).
3. Approve or correct each reference in `human-review.csv`, recording reviewer and evidence. All 40 statuses start as `pending`. Corrections require a new dataset version.
4. In **Human review**, search `negative control · 30 calibration` to narrow the 80-execution queue to 30 outputs. Review `record_exact` using source evidence. An output assessment does not replace reference approval or the automated result.
5. After human approval of the references and rubric, import real extractor outputs. Introduce a source-support judge separately and compare it with independently approved labels before relying on it for release gates.

The ten validation cases already verified the frozen configuration. They remain separate but visible and synthetic, so reserve fresh real examples when repeated prompt tuning begins.

## Fixed experiment references

- Calibration: [positive control](http://localhost:5188/experiments/280aedc9-d687-4b5a-a5aa-75061ee6b2aa) and [injected faults](http://localhost:5188/experiments/b0b32c98-a415-426d-a419-126eba712312); baseline `main`.
- Validation: [positive control](http://localhost:5188/experiments/646e75d1-a06f-416d-8c3b-7df428e81a44) and [injected faults](http://localhost:5188/experiments/5d0fbf01-a8e0-421b-a9c4-8e3d0c6ab691); baseline `validation-v2`.

Pack: `calibration/catalog-v2/`. Machine-readable results: `docs/catalog-calibration-v2.json`. The original Catalog extraction and Support triage projects are unchanged.

## Delivery checks

All 480 API/worker decisions passed, and the browser journey passed for both splits, comparison filters, imported-output launching and the human-review queue. Visual inspection showed English experiment and project labels and no browser errors. All 40 cases declare en-US and their passages, material values and rationales passed the language consistency check. Script lint and formatting passed. No application runtime code changed, so the previous production build was retained. The legacy project was relabeled in English as historical; its 40 cases and four runs were preserved.
