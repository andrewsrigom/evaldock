# Contributing to EvalDock

Keep changes focused on a concrete workflow or defect. Application copy, code comments, fixtures and documentation use English.

## Development setup

Use Python 3.12+, uv, Node.js 24 with npm, and Docker Compose v2. Follow the [quick start](README.md#quick-start) to configure and run the local stack, then install development dependencies:

```bash
uv sync --frozen
cd apps/web
npm ci
```

To run the frontend development server, start from the repository root and stop the Compose web service to free port 5188. Keep the API and other services running:

```bash
docker compose stop web
cd apps/web
npm run dev
```

Restore the bundled web service afterward with `docker compose up -d --no-deps --build web` from the repository root.

## Checks

From the repository root:

```bash
uv run ruff check apps/api packages/cli scripts
uv run ruff format --check apps/api packages/cli scripts
uv run mypy
uv run python scripts/test_backend.py
cd apps/web
npm run typecheck
npm test
npm run build
```

The backend helper migrates and uses the isolated `evaldock_test` PostgreSQL database. Use a disposable local stack for the complete browser suite: it creates projects, runs, reviews and tokens. Preparation steps are in [the CI workflow](.github/workflows/ci.yml).

From the repository root:

```bash
cd apps/web
npx playwright install chromium
npm run e2e
```

Pilot browser journeys also need prepared datasets and saved reports; tests skip unavailable pilot evidence. The [UX review](docs/UX-REVIEW.md#re-run-the-focused-checks) lists focused checks for the prepared local pilot.

When the API schema changes, regenerate request types from the repository root:

```bash
uv run python -m evaldock.api > apps/web/openapi.json
cd apps/web
npm run api:types
```

## Conventions

- Publish new resource versions instead of rewriting saved evaluation evidence.
- Keep reference/context data out of target requests and human assessments separate from automated judgments.
- Keep secrets, local environment files and browser authentication artifacts out of commits.
- Preserve lockfiles; add focused tests for behavioral changes and update documentation when commands or contracts change.
- Do not describe deterministic fixtures as model-quality evidence or invoke a live provider in routine tests.

## Pull requests

Describe the problem, resulting behavior and relevant verification. Include screenshots for visible UI changes and identify migrations or compatibility changes. Submit through the repository's hosting platform when available; no remote is configured in this checkout yet.

## Reporting bugs

Include the affected workflow, reproduction steps, expected versus actual behavior, environment and sanitized error output. Attach a minimal fixture or screenshot when useful. Share the report with the maintainer; this checkout does not yet have a public issue tracker.

For suspected vulnerabilities, use the private reporting guidance in [SECURITY.md](docs/SECURITY.md).
