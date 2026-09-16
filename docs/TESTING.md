# Testing

See [Contributing](../CONTRIBUTING.md#checks) for the standard lint, type-checking, build and test commands. [CI](../.github/workflows/ci.yml) runs backend, frontend and browser checks.

## Coverage

| Area | Checks |
| --- | --- |
| Data and access | Immutable versions, workspace isolation, roles, scoped tokens, sessions and CSRF |
| Evaluation | Schema validation, missing versus null, metric arithmetic, coverage and paired comparisons |
| Execution | Independent retries, cancellation, saved-output recovery and duplicate delivery |
| Integrations | Destination validation, response limits, structured output and credential isolation |
| Interface | Editors, imports, comparison filters, human review, release checks and responsive navigation |

Backend integration tests use PostgreSQL. `scripts/test_backend.py` creates and migrates the separate `evaldock_test` database and clears provider credentials for the test process. Provider responses are mocked in automated tests; live calibration is separate.

## Browser tests

Use a disposable local stack for the full suite: some tests create projects, experiments, reviews and tokens. The CI workflow contains the setup sequence. From the repository root:

```bash
cd apps/web
npx playwright install chromium
npm run e2e
```

Pilot-specific tests require the datasets and saved reports created by the setup scripts. Tests that depend on missing pilot evidence are skipped.

### Focused checks

On a prepared local pilot, these tests inspect reports, comparison, release checks, editors and mobile navigation without launching model calls:

```bash
cd apps/web
npm run e2e -- e2e/user-journey.spec.ts e2e/public-catalog.spec.ts e2e/ai-setup.spec.ts
npm run e2e -- e2e/ux.spec.ts --grep 'invalid JSON|responsive navigation'
```

These tests write screenshots under `docs/` and Playwright artifacts under `apps/web/`. Review generated changes before committing.

## Fixture workflow

With the seeded stack running:

```bash
uv run python scripts/demo_verify.py
```

The script exercises the HTTP API and worker, including imports, rescoring, human assessments, report export and CLI exit codes. It creates evaluation records and writes [fixture results](verification.json). Run it on disposable data when you need to repeat the complete workflow.

Fixture tests check application behavior. [AI calibration](AI-CALIBRATION.md) records live-model results and their evaluation scope.
