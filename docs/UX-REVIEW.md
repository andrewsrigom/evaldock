# UX revision — ready for local calibration setup

Date: 2026-09-16. Scope: finish the local workbench experience before integrating another application or using a live judge.

## Visual direction

The local CatalogForge stylesheet was inspected as the reference. EvalDock now shares its white navigation, `#215acb` blue actions, slate typography, pale neutral surfaces, compact tables, subtle borders and rounded panels. CatalogForge itself was not modified or integrated. Success, failure and warning colors retain their semantic meaning.

## Completed flows

- **Dataset editor:** searchable case list, add/duplicate/remove, stable identifiers, separate JSON input/reference/context, explicit missing versus null, tags, slices, acceptance criteria and reference IDs. JSONL file upload or paste has line-specific errors and an explicit apply step. Saved versions remain immutable.
- **Target editor:** URL, credential selection, authentication, stable request-mapping rows, response pointers, rate/concurrency/time limits, retry policy and revision metadata.
- **Evaluator editor:** guided controls for all seven evaluator kinds, normalization, paths, labels, tolerances, tool assertions, schema and versioned judge rubrics. Fixture and live modes are explicit. Saving a configuration does not call a target or AI provider.
- **Suite editor:** select criteria by name and pin versions. Empty suites and duplicate metric keys are rejected before saving.
- **Gate editor:** editable thresholds, coverage, regression limits, critical tags, evaluator error policy and optional latency ceiling. JSON remains available as an advanced mode.
- **Experiment launcher:** planned case/replicate count, pinned-baseline context, dependency hints and imported-output file/paste validation. Missing outputs remain visible in coverage; imports never call targets.
- **Comparison:** keyboard-operated result filters, tag/slice selectors, clear filters, per-side coverage, both baseline and candidate explanations and a bounded case list. Candidate scores are no longer unconditionally colored as an improvement.
- **Navigation and review:** searchable histories/resources/review cases, contextual page descriptions, back links, real setup progress and metric selection based on each project. Completed runs stop polling.
- **Access and feedback:** viewer-aware controls, selectable token scopes/expiry, copy/hide/revoke flows, readable server validation messages, modal focus trap and restoration, inert background, responsive navigation and warnings before discarding drafts or leaving an edited policy.

Arbitrary JSON inputs, outputs, JSON Schemas and tool argument schemas still use a JSON field because their shape is project-specific. The field validates syntax, retains invalid drafts, formats valid JSON and prevents saving an invalid value.

## Verified

- 9 Vitest tests passed, including missing/null integrity, duplicate IDs/metrics, invalid JSON preservation and live-judge configuration requirements.
- 8 complete Playwright journeys passed together: both sample domains; JSONL validation; versioned dataset/suite/imported run; invalid drafts and discard guards; all evaluator types and target mappings without calls; persisted gate policy/navigation guards; desktop/mobile layout and keyboard filters.
- One additional Playwright journey passed with a real temporary viewer: read-only inspection, read-scoped expiring token creation/revocation and backend rejection of an edit.
- Strict TypeScript and the production Vite build passed. Screenshots were inspected at 1500×1000 and 390×844.
- Browser checks caught and fixed same-route discard-guard bypass and request-pointer loss while renaming a mapping field.
- Existing backend/scoring code was not changed. Its earlier 45-test PostgreSQL verification remains documented separately; it was not rerun for this frontend revision.
- No external application integration and no live-model calls were performed. Local deterministic fixtures and imported outputs supplied the verification data.

After explicit user authorization, the ten temporary UX verification projects and the temporary viewer account were removed. Both original sample projects and their results were preserved.

## What remains for the next phase

1. Choose a real evaluation dataset and rubric for the first AI calibration.
2. Add the provider credential and select a supported model in the guided judge editor.
3. Review a labeled subset and investigate disagreements before using judge decisions as release gates.

Local deployment/security boundaries remain in SECURITY.md. This revision does not add internet hosting, SSO, automated backups/retention, bulk review assignment or live-model quality claims.

## Re-run

```bash
cd apps/web
npm run test
npm run build
npm run e2e
```

Browser journeys require the running local stack and its generated `.env`. They create persisted verification data; use a disposable workspace/database for repeated CI runs. Traces and authentication artifacts remain ignored by Git.

## Simplicity pass, 2026-09-16

Removed promotional panels, repeated header/footer copy and completed setup steps. Overview prioritizes results, baseline and recent runs. Settings keep credentials and active tokens visible; members, activity, notes and revoked tokens expand on demand. Evidence, coverage and actionable errors remain accessible. English copy remains the project default.

Validation: 9 frontend tests, strict typing, production build and 2 read-only browser journeys. The journeys cover imports, comparison, source evidence, mobile layout and expanding workspace members. No new verification projects or accounts were created.
