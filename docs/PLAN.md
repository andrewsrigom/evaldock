# EvalDock implementation plan

1. Infrastructure, authentication, workspace authorization, immutable version registry and JSONL datasets.
2. Safe JSON HTTP adapter, independent typed evaluators, PostgreSQL durable worker and attempt history.
3. Paired comparisons, explicit coverage and CI policies, complete Vue workbench.
4. Imported outputs, linked rescoring, human calibration and OpenAI structured judge integration.
5. Two 24-case deterministic sample applications, PostgreSQL tests, browser journeys, recovery checks and documentation.

## Decisions

- Modular monolith, PostgreSQL JSONB for payloads, relational ownership and version relationships.
- A typed resource/version registry represents datasets, targets, evaluators and suites; version kinds and project relationships are checked at creation and execution. Dataset cases are relational children of immutable versions.
- Procrastinate provides PostgreSQL jobs, job locks and stalled-worker recovery. A transactional outbox flag and reconciliation close dispatch gaps. Execution writes are idempotent; external calls remain at least once.
- Only the first successful target attempt is scored. Failed evaluator work retries against that saved output. Manual retry never repeats successful target calls or valid failing evaluations.
- No universal quality score. Metrics retain denominators, coverage, errors, missing data and direction. Comparisons operate on case/replicate and metric.
- HTTP egress resolves and validates every destination; connections pin the validated IP, preserve TLS hostname, reject redirects and bound body/time. Admin allowlists are exact origins.
- Server-side sessions, Argon2 passwords, hashed scoped API tokens and Fernet-encrypted credentials. Expected answers and evaluator context never enter request mappings.
- Vue 3, strict TypeScript, Vue Router and TanStack Query. Polling uses authenticated endpoints and persisted events. No client state store unless needed.
- Local artifact store implements an interface and authorizes artifact access through the associated project.
- Fixture targets and fixture judging are explicitly labeled; no-key tests make no claims about real-model quality.

## Official references checked

- https://procrastinate.readthedocs.io/en/stable/quickstart.html
- https://procrastinate.readthedocs.io/en/stable/howto/production/retry_stalled_jobs.html
- https://procrastinate.readthedocs.io/en/stable/howto/advanced/retry.html
- https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- https://vuejs.org/guide/typescript/overview
- https://www.shadcn-vue.com/docs/installation/vite
- https://github.com/openai/openai-python/blob/main/examples/responses/structured_outputs.py

Exact installed versions are recorded in uv.lock and package-lock.json; builds and type checks validate the resolved combination.
