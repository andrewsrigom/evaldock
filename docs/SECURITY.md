# Security boundaries and current limitations

## Implemented boundaries

- Argon2 password hashing; random server-side sessions expire and use HttpOnly, SameSite=Strict cookies. Non-GET cookie-authenticated operations require the configured Origin and a CSRF header. Local HTTP defaults `COOKIE_SECURE=false`; use HTTPS and `true` beyond local development.
- Hashed expiring API tokens scoped to one workspace and read/write capabilities. Owner/editor/viewer authorization is enforced at project, version, experiment, execution, artifact, credential and event endpoints. Owners add workspace members. Viewers cannot modify project data.
- Credentials are Fernet-encrypted with an externally supplied APP_KEY, absent from Git and masked in responses. External-library errors are sanitized. No real provider keys are seeded. Key rotation/re-encryption and a managed secret backend are not implemented.
- Egress validates protocol, credentials, query strings, DNS and all resolved addresses; pins validated addresses for the request; retains the original TLS hostname; ignores ambient HTTP proxies; rejects redirects, metadata/link-local/unspecified destinations and unallowlisted private addresses. Exact-origin admin allowlists support local sample services. Timeout, response-size, target concurrency and request-rate limits are explicit.
- Schema evaluation uses standards-based JSON Schema; schema references must be local fragments to avoid remote schema fetches. Mapping uses fixed fields and JSON Pointer; no arbitrary Python/JavaScript or expression templates are executed.
- Dataset/reference data never enters target requests. Judge input is untrusted and separated from system grading instructions, without tools. Human review remains separate from original judgments. This is not a guarantee that every model will resist prompt injection.
- Immutable version/case data is protected at API and PostgreSQL trigger layers. Project/version kinds are checked relationally. Report downloads authorize the owning project before accessing the local storage key.
- Services bind to loopback host ports in Compose. The web server sets CSP, nosniff and frame-ancestor restrictions. Passwords and keys are generated locally, never hard-coded.

## MVP limitations

- This is a local/team evaluation workbench, not an internet-hardened multi-tenant SaaS. No enterprise SSO, password reset/email delivery, account lockout, billing, automatic data retention, backup orchestration or advanced per-project ACLs. All workspace members inherit access to its projects according to their role.
- Raw outputs/traces remain in bounded JSONB; the working storage abstraction currently persists report artifacts. A remote object store, retention policy and offloading of very large traces are follow-up work.
- Target calls are at least once. The worker can recover interrupted delivery, but a remote call completed before a database commit may execute again. Use test endpoints and target-supported idempotency. Cancellation cannot retract a side effect that already occurred.
- Target concurrency is enforced per immutable target version. Different versions pointing at the same endpoint have separate limits. Size/time limits do not make pathological user-supplied regex schemas safe; authorized editors should use bounded practical schemas.
- HTTP integrations support synchronous JSON POST only. No streaming, asynchronous job protocols, arbitrary headers or executable mappings. Query-string endpoints are deliberately unsupported; use JSON input and credential headers.
- No configured price-estimation table or dollar budget. Costs without provider reporting stay unavailable. Request-count budgets are conservative reservations and can count a call canceled before transmission.
- Structured live OpenAI judging is implemented, but no live-model evaluation is claimed without credentials. Deterministic fixture tests demonstrate product behavior only. No statistical significance or benchmark claims.
- Configuration uses JSON editors with validation and version selectors. There is no visual schema/rubric builder, bulk review assignment or customizable chart dashboard.
- Authenticated polling is used instead of SSE. Experiment lists currently show the latest 100 runs and the review queue includes the latest 10 terminal experiments.
- Local Compose images include development tooling for reproducibility; a hardened production image and deployment design remain future work.
