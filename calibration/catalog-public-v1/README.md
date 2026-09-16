# Public-source catalog pilot v1

Twelve real product records from official TOAKS and Nalgene pages, represented by concise English factual paraphrases. Eight calibration cases and four separate, visible validation cases. References were reviewed by the assistant; no independent human approval or AI calls are claimed.

`sources.json` contains the source URLs, observation date, selected evidence, expected values and rationale. `RUBRIC.md` defines the extraction decisions. The two JSONL files can be imported directly in EvalDock. Output files are produced by executing `examples/catalog_rules.py` using only the passage, never expected values. `manifest.json` freezes every file and the implementation with SHA-256 hashes.

From the repository root, with local services running:

```bash
uv run python scripts/prepare_public_catalog.py
uv run python scripts/load_public_catalog.py
uv run pytest -q apps/api/tests/test_catalog_pilot.py
```

Loading is idempotent: matching resources and runs are reused. A diverging existing project stops loading. Do not rewrite the pack after publishing results; create a new pack version instead. A later source-page change does not silently modify this recorded evidence.

The baseline is a naive first-mention parser. The candidate uses labeled material, assembly weight and explicit body origin. These are small local examples to exercise real comparison and reporting, not production extractors or model benchmarks. Separate validation is not blind: all cases were visible during authoring.
