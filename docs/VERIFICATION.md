# Executed verification

Verified locally in Ubuntu-20.04 under WSL with real PostgreSQL 17, Docker Compose, Chromium and the separate Procrastinate worker. Dates: September 15–16, 2026. This is product verification against deterministic fixtures, not a real-model evaluation.

## Confirmed workflows

| Workflow | Observed result |
|---|---|
| Catalog baseline vs candidate, 24 cases × 2 replicates | 14 improved pairs, 6 regressed, 26 unchanged pass, 2 unchanged fail |
| Support baseline vs candidate, 24 cases × 2 replicates | 16 improved pairs, 8 regressed, 24 unchanged pass |
| Failed-case inspection | Saved output, reference, evaluator evidence and attempt history available |
| Human disagreement | Separate human assessment persisted while automated failure stayed unchanged |
| Rescoring with fixture judge suite | Linked evaluation completed with zero additional target calls; no invented latency |
| Python CLI gate | Exit 1 for both deliberately regressed candidates |
| JSON and JUnit export | Files produced through the installed CLI |
| Imported agent traces | 3 planned outputs, 2 provided, 2/3 scoring coverage; missing output explicitly retained |
| Worker SIGKILL recovery | 10-case run completed after interruption; 2 completed cases retained, 2 interrupted attempts visible; approximately 29 seconds to recovery in this run |
| Duplicate queue delivery | Already completed experiment produced zero extra target calls |
| Browser journeys | Catalog and support comparison → diff → review → case → rescore → gate → launch passed; JSONL editor validation journey passed |
| Browser console | No page errors in those completed journeys |

Machine-readable run IDs and counts are in `verification.json`. The test environment intentionally contains verification experiments and datasets in addition to the original seed. Screenshots: `catalog-comparison.png`, `support-comparison.png`, `overview.png`, `login.png`.

## Automated checks

Final result: **45 pytest tests, 2 Vitest tests and 3 Playwright journeys passed**. Ruff, mypy, strict Vue/TypeScript checking and Vite production build passed. `npm audit` reported 0 vulnerabilities for the resolved final lockfile.

Backend checks include real-PostgreSQL version immutability, workspace isolation, scoped roles, secret encryption/redaction, line-specific import validation, missing-vs-null, evaluator math, classification reports, coverage denominators, compatible pairing, gates, independent retries, cancellation with late output, saved-output recovery, persisted retry limits, duplicate execution delivery, human disagreement, schema-invalid judging and separation of adversarial judge data. HTTP adapter tests use an actual local HTTP service for destination pinning, response bounds and unsupported protocols.

Frontend checks include strict Vue/TypeScript compilation, Vite production build, Vitest evidence formatting and Playwright complete journeys. Dependency lockfiles are present. Final command results and versions are recorded in the delivery report.

## Not claimed

- No live OpenAI request or model-quality benchmark was run; no provider credential was supplied.
- No load test, statistical significance, production security audit or internet deployment is claimed.
- GitHub Actions configuration was authored and local equivalent checks were run; a remote GitHub Actions run was not triggered.

See SECURITY.md for limits, including at-least-once external calls, local authentication, JSON editors, loopback deployment and unavailable cost estimation.
