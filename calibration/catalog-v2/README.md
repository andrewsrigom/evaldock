# Catalog calibration pack v2 — English

40 English synthetic cases with assistant-proposed references awaiting human approval. These are not real CatalogForge data or model outputs. The pack makes the extraction contract explicit and checks known failures before introducing AI.

## Files

| File | Purpose |
|---|---|
| `calibration.jsonl` | 30 development cases, three per scenario |
| `validation.jsonl` | Ten separate cases, one per scenario, marked as held-out |
| `*-reference-outputs.json` | Authored positive controls matching the references |
| `*-challenge-outputs.json` | Correct outputs mixed with deliberately injected faults |
| `RUBRIC.md` | Output contract, decisions and review instructions |
| `evaluators.json` | Six deterministic evaluators with threshold 1 |
| `gate.json` | Strict policy for these synthetic controls |
| `expected-decisions.json` | Expected metric outcomes for every challenge output |
| `human-review.csv` | Reference approval/correction worksheet; all entries pending |
| `manifest.json` | Provenance, counts and SHA-256 checksums |

All passages, expected material values, rationales, tags, labels and documentation use English. The output has three required keys: `material`, `weight_g` and `country`. Missing information uses explicit null; weight is numeric grams; country is the manufacturing country code. String matching is strict, so define and version any synonym normalization before evaluating real outputs.

## Scenarios and expected results

Explicit fields; missing information; kilograms to grams; conflicting sources; net versus shipping weight; single items versus sets; manufacture versus other country references; material inferred from appearance; instructions embedded in source text; zero and JSON types.

Each scenario has three calibration cases and one validation case. Twenty calibration outputs and five validation outputs have deliberate faults. All 40 positive controls must pass; all 25 faulty complete records must fail. A field comparison alone allows extra keys, so schema and whole-record checks are also required.

The separate cases were fixed before execution. They verify the configuration with known controls, not model quality or a blind real-world estimate. Reserve fresh real cases for final validation after repeated tuning.

## Reproduce

From the EvalDock root, with the local stack and demo workspace available:

```bash
uv run python scripts/prepare_catalog_calibration.py
uv run python scripts/load_catalog_calibration.py
cd apps/web
npm run e2e -- e2e/calibration.spec.ts
```

The authoring command regenerates the pack from explicit source labels. To change labels or preserve worksheet approvals, create a new pack revision instead of overwriting reviewed files. The loader uses the public API, creates a dedicated project and reuses matching resources/runs; it stops on divergent configuration or reviewed control data. It never deletes data, calls targets/models or records assistant decisions as human reviews. Credentials remain in the ignored local `.env`. The browser journey does not save data.

Results: `docs/catalog-calibration-v2.json` and `docs/catalog-calibration-v2.md`. Baselines are separate: `main` for calibration, `validation-v2` for validation. A reference control already contains the answers and cannot measure model quality.

## Language correction

v2 supersedes the Portuguese v1 created in local commit `7c4feea`. Current source files and generated assets are English. The original Portuguese files remain in Git history; immutable v1 cases, outputs and evaluations remain in the local database. New IDs and new executions preserve that history. Repository instructions now explicitly require English for product text, fixtures and documentation.
