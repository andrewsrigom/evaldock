# Integration contracts

## Dataset JSONL

One JSON object per nonblank line:

```json
{"case_id":"case-001","input":{"question":"Where is the order?"},"expected":{"answer":"Shipped"},"context":{"reference":"Tracking record says shipped"},"tags":["critical"],"slices":{"region":"EU"},"acceptance_criteria":"Use only supplied order evidence","references":["order:101"]}
```

`case_id` is stable and unique within a version. Input may be any JSON value. Expected, context, tags, slices, criteria and references are optional. An omitted `expected` field means no reference exists; `"expected": null` is an explicit null reference. Import errors identify physical line numbers. Duplicate IDs fail validation. A version accepts 1–10,000 cases. JSON numeric NaN/Infinity is not supported. The JSON editor uses the same validated contracts as the API.

Changing any input, expected output, context, tag, slice or criterion changes the case fingerprint. Comparisons across dataset versions pair only equal-fingerprint shared case IDs and replicate indices. Added, removed and changed cases remain separately visible.

## HTTP target

Only synchronous JSON `POST` requests are supported. Streaming, HTTP 202 and redirects fail explicitly. For example:

```json
{
  "endpoint":"https://test.example.com/evaluate",
  "request_mapping":{"message":"/question"},
  "output_pointer":"/output",
  "trace_pointer":"/trace",
  "metadata_pointer":"/metadata",
  "usage_pointer":"/usage",
  "cost_pointer":"/cost",
  "timeout_seconds":20,
  "concurrency":4,
  "requests_per_second":5,
  "max_attempts":3,
  "idempotency_header":"Idempotency-Key",
  "credential_id":null,
  "auth_header":"Authorization",
  "auth_prefix":"Bearer ",
  "revision":"app-v4",
  "prompt_version":"prompt-v2",
  "model":null,
  "parameters":{},
  "fixture":false
}
```

An empty `request_mapping` sends the case input unchanged. Otherwise fixed top-level request keys map to JSON Pointers **inside case input**, never the full case envelope. There are no expressions or executable templates. Empty pointer means root; `~1` escapes `/`, and `~0` escapes `~`. Missing required output/input mappings fail; optional telemetry stays unavailable. An explicit null output is a present, valid output and can be scored.

Response example:

```json
{"output":{"answer":"Shipped"},"trace":{"tool_calls":[{"name":"lookup_order","arguments":{"order_id":"101"}}]},"metadata":{"revision":"abc123","model":"configured-model"},"usage":{"input_tokens":125,"output_tokens":12},"cost":0.001}
```

`cost` is an optional numeric USD amount reported by the provider/target. It is labeled `provider_reported`; EvalDock does not infer a price or treat omitted cost as zero. Target usage is separate from evaluator/judge usage. Application revision, model, prompt version and parameters are optional for non-model targets.

Secrets live in encrypted, project-scoped credential records and become headers only on the server. Authentication accepts either Authorization or X-API-Key. The administrator sets exact allowlisted origins for intentional local sample services. An allowlist does not permit link-local or metadata endpoints. Use endpoints designed for testing because calls may have side effects. Idempotency keys must be honored by the external application if duplicate effects matter.

## Imported outputs and traces

CLI bundle:

```json
{"dataset_version_id":"EXACT_VERSION_ID","outputs":[{"case_id":"case-001","replicate":0,"output":{"answer":"Shipped"},"trace":{"tool_calls":[{"name":"lookup_order","arguments":{"order_id":"101"}},{"name":"respond","arguments":{}}]},"metadata":{"source":"offline evaluation"}}]}
```

The experiment declares `mode: imported`, its dataset version, and matching `import_dataset_version_id`. Duplicate case/replicate pairs, unknown case IDs, out-of-range replicas and incompatible dataset versions fail. Missing outputs remain `missing_output` executions and reduce coverage. Imported metadata is preserved as declared metadata; no request latency, usage or cost is invented, and scoring imported outputs never invokes a target.

Observable traces contain `tool_calls`, an ordered list of `{name: string, arguments: object, output?: JSON}`. Extra trace fields are rejected; hidden reasoning does not belong in this contract. Tool evaluators support required names, forbidden names, argument JSON Schemas and an explicit optional order list. Missing trace means not applicable. The UI displays observable calls, not hidden chain-of-thought.

## Fixtures

`fixtures/catalog.jsonl` and `fixtures/support.jsonl` contain 24 manually labeled cases each. `examples/responses.json` contains independent static response tables read only by the sample HTTP services. The core runner contains no catalog/classification application logic. `scripts/author_fixtures.py` is reproducible fixture authoring, not runtime target logic. Agent examples are in `agent-cases.jsonl` and `agent-outputs.json`.
