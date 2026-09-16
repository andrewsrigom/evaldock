# Measurement, comparisons and CI

There is no universal quality score. Each suite declares independent metric definitions with value type, direction, required inputs, threshold and aggregation. Evaluator functions receive input, optional reference/context, actual output, observable trace and execution metadata. They return typed scored/not-applicable/error results, optional score/decision, concise explanation and supporting paths.

## Built-in semantics

| Evaluator | Semantics |
|---|---|
| JSON Schema | Draft 2020-12 schema validation. Invalid output is a valid failing score. User schemas are validated before saving. Only local schema references are accepted. |
| Exact match | Strict JSON value equality by default. Booleans are distinct from numeric 0/1. Optional string trim/casefold is explicit. Missing reference is N/A; explicit null can match. |
| Field comparison | Mean correctness across configured JSON Pointers. Per-field evidence distinguishes matched null, missing actual, missing reference and mismatch. Missing values never silently match. |
| Numeric tolerance | `abs(actual-reference) <= max(absolute, relative*abs(reference))`. At reference zero only absolute tolerance contributes. Missing/non-numeric reference is N/A; invalid actual is a valid failure. Booleans are not numeric measurements. |
| Classification | Per-case correctness with fixed labels. Unknown predictions fail. Confusion matrix includes unknown predictions. Per-label precision/recall/F1 and macro/micro values are separate; zero divisions resolve to 0 and supports are shown. |
| Tool calls | Required/forbidden tools and schema-constrained arguments. Ordering checked only when requested. Missing trace is N/A. Invalid trace shape is evaluator error. |
| LLM judge | Explicit live or fixture mode, versioned rubric and schema-valid score/decision/justification/evidence. Correctness and context support are separate templates. Judge scores are fallible assessments. |

Default decisions use exact validity/equality where appropriate. A metric threshold overrides its numeric score decision: score >= threshold for higher-is-better, score <= threshold for lower-is-better. Different threshold versions are different evaluator versions.

## Coverage and denominators

Each metric reports total planned case/replicate executions, scored count, scored/total coverage, not-applicable count, evaluator-error count and missing-result count. A target error or missing import stays in the denominator. Mean is over scored numeric results only; pass rate is over scored results with a pass/fail decision. Reports expose both, so consumers must select the metric's declared aggregation and inspect coverage. The UI never replaces missing cost/latency with zero.

Repetitions are distinct observations indexed from zero. Paired comparisons use case ID plus replicate. Improved/regressed means a decision changed from fail→pass or pass→fail for the selected criterion; unchanged pass and unchanged fail remain separate. Score deltas are also shown even if the threshold decision stayed unchanged. Unscored or execution-error pairs form a separate bucket.

Different dataset versions generate a warning and separate lists of added, removed and changed cases. Only unchanged shared cases pair. Tag and `slice=value` filters are available. Population standard deviation and sample count describe variability; no confidence intervals or statistical significance are claimed.

## Timing, cost and attempts

Target latency measures the HTTP request/response wall time, excluding the queue and throttle wait. Evaluation latency is recorded separately. P95 uses nearest rank: sort n observations ascending, select `ceil(0.95*n)-1`. Sample count is always included. Comparison labels latency comparable only for the same dataset, HTTP mode, concurrency, warm-up setting and target limits. This does not control network noise or hardware variation.

Warm-up is explicitly 0 in this MVP. Target and judge usage/cost are separate. Costs without provider-supplied values are unavailable. There is no price estimator or inferred zero spend. Optional execution budget is a maximum target-call reservation count, not a dollar estimate.

Target transport/protocol failures retry with bounded exponential backoff. Valid outputs with low scores are never retried. The first successfully persisted target output contributes to metrics. Independent evaluator errors retry against this same output. Every attempt remains inspectable; no best-score selection occurs. Manual retry applies only to failed work. Rescoring always creates a separate linked experiment with preserved raw outputs and an explicitly selected suite.

## Gates

The selected baseline experiment ID is captured when a run starts. Gates use this fixed ID, not a moving latest result. Rules include minimum per-metric mean field accuracy, maximum regression count, no failing/unscored critical cases, maximum target-error rate, minimum coverage and an optional P95 limit when measurements are comparable. All suite metrics are included in coverage/error checks. Added/removed/changed baseline coverage fails the gate.

Evaluator errors explicitly either fail quality or produce an infrastructure error. Missing baseline, unknown configured metric, nonterminal/unusable experiment or requested but incomparable latency produces exit 2. Gate quality failures produce exit 1. A completed experiment can still fail quality. JSON and JUnit export include the gate decision and per-case failures/errors. JUnit XML is generated with an XML library so text is escaped.
