# Final UX review

2026-09-16 · Local demo and portfolio presentation.

The workbench retains CatalogForge's white navigation, blue actions and restrained slate/neutral surfaces. Application copy is English. No blocking usability issue was found in the flows checked below.

## Final changes

- Comparison opens with a baseline from the candidate's dataset and offers criteria present in both runs. A direct link from a report preserves the selected candidate.
- Reports distinguish completed executions, passing criteria and evaluation coverage. Product names replace opaque identifiers when available. Successful case results use one compact summary; failures and unscored criteria remain explicit.
- The selected comparison criterion has primary evidence. Other findings, references, traces, telemetry and secondary actions remain accessible on demand.
- **Release checks** shows the result before policy editing. Passing, failing and incomplete checks have distinct messages; changing the run refreshes the result. Thresholds retain their original machine-readable keys.
- Source passages are readable text. Draft protection, keyboard filters, focus restoration and mobile navigation remain intact. Mobile case headers and run selectors no longer clip their content.

## Verification for this revision

- 13 frontend unit tests passed.
- TypeScript checking and the production build passed; the local web container serves the updated build.
- Six browser journeys passed: the report/comparison/release-check journey; six mobile routes; the public-source pilot; configured/missing-key behavior; invalid JSON and discard guards; responsive navigation and keyboard filters.
- Browser inspection covered desktop and 390 × 844 mobile views. No JavaScript console errors were observed. Tests check both page overflow and clipping inside the comparison header.
- No model requests, persisted evaluation changes or new verification accounts/projects were made. The main review journey blocks unexpected API writes after sign-in.

Backend scoring was unchanged. The 78-test backend verification belongs to the preceding calibration revision. The full mutation-heavy browser suite was not rerun against the local pilot.

## Portfolio walkthrough

Use the **Catalog extraction · public-source pilot** project:

1. Open **Compare**: the validation baseline and AI candidate share four cases. Select **Exact record**, then **Improvements**.
2. Inspect a changed field and its source; open the case for complete evidence.
3. Return to the experiment, then **Release checks**, to explain how results inform a release decision.

The [calibration report](AI-CALIBRATION.md) documents the limited pilot evidence. Results remain preliminary: the validation set is curated, not blind, and independent human approval is pending.

Screenshots: [comparison](portfolio/comparison-desktop.png), [results](portfolio/results-desktop.png), [release checks](portfolio/release-checks-desktop.png), [overview](portfolio/overview-desktop.png), [mobile overview](portfolio/overview-mobile.png), [mobile checks](portfolio/release-checks-mobile.png).

## Re-run the focused checks

```bash
cd apps/web
npm test
npm run build
npm run e2e -- e2e/portfolio.spec.ts e2e/public-catalog.spec.ts e2e/ai-setup.spec.ts
npm run e2e -- e2e/ux.spec.ts --grep 'invalid JSON|responsive navigation'
```

These browser checks require the prepared local pilot and generated `.env`. Run the complete browser suite against a disposable database because its other journeys create records.
