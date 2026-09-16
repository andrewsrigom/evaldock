# EvalDock local delivery

Local workbench complete. English interface, concise overview, editors, imports, comparisons and reports are ready. Secondary administration and history are available on demand.

[Open EvalDock](http://localhost:5188/projects/862802ec-280d-4e46-8a75-031b0eceb944/overview)

## Public-source pilot

Twelve real products, represented by curated manufacturer facts with source URLs. Two local rule-based extractors produced the saved outputs.

| Split | Baseline correct | Candidate correct | Regressions |
|---|---:|---:|---:|
| Calibration | 4/8 | 8/8 | 0 |
| Separate validation | 2/4 | 4/4 | 0 |

Both candidate gates passed. All 24 executions and 144 metric decisions were checked. Repeating the loader reused the same records.

## Checks

- 53 backend tests, 9 frontend tests and 2 browser journeys passed.
- Type checking, static analysis and production build passed.
- Desktop and mobile views inspected; no page errors in the browser journeys.
- Thirty synthetic calibration references reviewed by the assistant; historical evidence preserved.

This small, visible dataset is not a blind benchmark. No live AI calls, independent human approvals or other project integrations are claimed.

For reproduction, see `calibration/catalog-public-v1/README.md`. Source evidence and rubric are in the same pack. `docs/AI-READINESS.md` covers the first model run once the model and credential are configured.
