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

- 73 backend tests, 9 frontend tests and 3 browser journeys passed.
- Type checking, static analysis and production build passed.
- Desktop and mobile views inspected; no page errors in the browser journeys.
- Thirty synthetic calibration references reviewed by the assistant; historical evidence preserved.

This small, visible dataset is not a blind benchmark. No live AI calls, independent human approvals or other project integrations are claimed.

For reproduction, see `calibration/catalog-public-v1/README.md`. Source evidence and rubric are in the same pack. `docs/AI-READINESS.md` covers the first model run. The OpenAI target and judge are configured; only the API key remains to be supplied.

## OpenAI setup

Set `OPENAI_API_KEY` in the project root `.env`, then run `docker compose up -d --no-deps --force-recreate api worker` from that directory. New experiments default to eight calibration cases, native structured generation and six deterministic criteria plus one source-support AI review.

The protocol and worker flow were verified with a simulated provider, including environment-backed keys, project isolation, absent keys, key rotation, permissions, invalid responses and saved results. Browser checks verified environment configuration status, launch gating, preset editor and mobile layout. No live provider request was made. Account access and model quality require the first keyed run.
