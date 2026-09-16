# EvalDock local completion report

Date: 2026-09-16. Environment: Ubuntu-20.04 on WSL, local Docker services.

The local application and public-source pilot are complete for the agreed phase before external project integration and live AI calibration. The CatalogForge-inspired visual system, English interface, editors, imports, experiments, comparisons, review queue and CI reports remain available.

## Open the completed pilot

[Project overview](http://localhost:5188/projects/862802ec-280d-4e46-8a75-031b0eceb944/overview) · [Comparison](http://localhost:5188/projects/862802ec-280d-4e46-8a75-031b0eceb944/compare) · [Calibration candidate](http://localhost:5188/experiments/473022c0-8125-4a94-9966-be23a87a277b)

Twelve real product records from official TOAKS and Nalgene pages are represented by short factual paraphrases. Every case records its URL, observation date, evidence scope and reference rationale. This is a curated extraction pilot, not full-page scraping or a representative production benchmark. See the frozen source ledger and rubric in `calibration/catalog-public-v1`.

| Split | Cases | Naive records correct | Scoped records correct | Improvements | Regressions | Candidate gate |
|---|---:|---:|---:|---:|---:|---|
| Calibration | 8 | 4/8 | 8/8 | 4 | 0 | Passed |
| Separate visible validation | 4 | 2/4 | 4/4 | 2 | 0 | Passed |

These are actual outputs from two small local rule-based implementations, both run with passage input only. They are not model answers or injected faults. All 24 executions and 144 metric decisions were verified through the API. Both candidates have full scoring coverage and no evaluator errors. The loader was run twice and reused the same versions, runs and report artifacts without duplicating them.

The same author saw both splits while constructing the rubric. Validation is separate but not blind. A perfect result on these twelve curated inputs does not establish generalization, production readiness of the example parser or live AI quality.

## Critical review and verification

- Reviewed all 30 synthetic v2 calibration references. Their labels match their stated synthetic evidence; the per-case assistant ledger is in `docs/catalog-v2-assistant-review.csv`.
- Published a separate rubric clarifying assembled mass, metric precedence, primary-body origin, missing facts and canonical material names. Historical datasets and runs were preserved.
- Backend: 53 tests passed against the isolated PostgreSQL test database, including eight new pilot checks. Ruff passed; mypy reported no issues in 18 source files.
- Browser: the new read-only public-source journey passed. It covers imported launch defaults, paired improvements, source evidence, both dataset splits, the 24-execution review queue and a 390px mobile layout without page overflow. No browser page errors were captured. Desktop and mobile screenshots were inspected.
- Additional browser inspection confirmed the visible candidate release gate passed with exit code 0 and the correct pinned baseline.
- Existing application verification and UX results remain documented in `docs/VERIFICATION.md` and `docs/UX-REVIEW.md`; they are not represented as newly rerun browser suites here.
- Credentials, model calls, human approvals and target latency were not invented. This pilot made zero live model requests and zero sample-target calls, and created no human review records.

## Reproduce

```bash
cd /home/andrews/projects/evaldock
uv run python scripts/prepare_public_catalog.py
uv run python scripts/load_public_catalog.py
uv run python scripts/test_backend.py
cd apps/web
npm run e2e -- public-catalog.spec.ts
```

The generator uses only saved evidence and local Python code, with no network fetching. Published pack files and the implementation are pinned by SHA-256 in the manifest. Create a new pack version for any changed facts, rubric, normalization or extraction algorithm; the loader stops on divergence.

## Boundary of completion

Local product and pilot: complete. Live AI calibration: not performed. No provider credential/model was configured for this phase, and no other project was integrated. `docs/AI-READINESS.md` contains the first-run procedure and starter extraction instruction. Independent human labels and fresh unseen validation data are needed before making calibrated model-quality claims.
