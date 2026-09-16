import type { Obj, Project } from '@/api/client'

export const evaluatorKinds = [
  { value: 'exact_match', label: 'Exact match', hint: 'Compare the entire output with its reference.' },
  { value: 'field_comparison', label: 'Field comparison', hint: 'Score specific fields using JSON Pointer paths.' },
  { value: 'json_schema', label: 'JSON Schema', hint: 'Validate the shape and types of the output.' },
  { value: 'numeric_tolerance', label: 'Numeric tolerance', hint: 'Allow an explicit absolute or relative difference.' },
  { value: 'classification', label: 'Classification', hint: 'Compare a label and report precision, recall and F1.' },
  { value: 'tool_calls', label: 'Tool-call assertions', hint: 'Check observable tool names, arguments and ordering.' },
  { value: 'llm_judge', label: 'LLM judge', hint: 'Apply a versioned rubric. Fixture mode makes no AI calls.' },
]
export function evaluatorDefaults(kind: string): Obj {
  return ({ exact_match: { trim: false, casefold: false }, field_comparison: { paths: ['/answer'], trim: false, casefold: false }, json_schema: { schema: { type: 'object' } }, numeric_tolerance: { path: '', absolute: 0, relative: 0 }, classification: { path: '/category', labels: ['positive', 'negative'] }, tool_calls: { required: [], forbidden: [], order: [], arguments: {} }, llm_judge: { mode: 'fixture', template: 'correctness', rubric: 'The answer matches the reference and follows the acceptance criteria.', rubric_version: 'v1', model: '', credential_id: null, parameters: {} } } as Obj)[kind]
}
export function defaults(kind: string): Obj {
  if (kind === 'dataset') return { config: { held_out: true }, cases: [{ case_id: 'case-001', input: {}, tags: [], slices: {} }] }
  if (kind === 'target') return { endpoint: '', request_mapping: {}, output_pointer: '/output', trace_pointer: '/trace', metadata_pointer: '/metadata', usage_pointer: '/usage', cost_pointer: '/cost', credential_id: null, auth_header: 'Authorization', auth_prefix: 'Bearer ', timeout_seconds: 20, concurrency: 4, requests_per_second: 5, max_attempts: 3, fixture: false }
  if (kind === 'evaluator') return { kind: 'exact_match', metric_key: 'exact_match', definition: { direction: 'higher', aggregation: 'mean', value_type: 'number', threshold: null }, config: evaluatorDefaults('exact_match'), max_attempts: 2 }
  return { evaluator_version_ids: [] }
}
export const splitList = (value: string) => value.split(/[,\n]/).map(v => v.trim()).filter(Boolean)
export function validationErrors(kind: string, draft: Obj, project?: Project): string[] {
  const errors: string[] = []
  if (!draft || typeof draft !== 'object' || Array.isArray(draft)) return ['Version content must be a JSON object.']
  if (kind === 'dataset') {
    if (!draft.config || !Array.isArray(draft.cases) || !draft.cases.length) return ['Add at least one case.']
    const ids = new Set()
    draft.cases.forEach((c: Obj, i: number) => {
      if (!c || typeof c !== 'object') { errors.push(`Case ${i + 1}: use a JSON object.`); return }
      if (!c.case_id || !/^[\p{L}\p{N}_.:-]+$/u.test(c.case_id) || c.case_id.length > 160) errors.push(`Case ${i + 1}: use a stable ID with letters, numbers, dots, colons, underscores or hyphens.`)
      if (ids.has(c.case_id)) errors.push(`Duplicate case_id: ${c.case_id}`)
      ids.add(c.case_id)
      if (!('input' in c)) errors.push(`Case ${i + 1}: input is required; null is allowed.`)
      if (c.slices && Object.values(c.slices).some(v => typeof v !== 'string')) errors.push(`Case ${i + 1}: slice values must be strings.`)
    })
  }
  if (kind === 'target') {
    try { const u = new URL(draft.endpoint); if (!['http:', 'https:'].includes(u.protocol) || u.username || u.password) throw new Error() } catch { errors.push('Enter an HTTP or HTTPS endpoint without embedded credentials.') }
    if (Object.entries(draft.request_mapping || {}).some(([key, value]) => !key || key.includes('/') || typeof value !== 'string' || (!!value && !value.startsWith('/')))) errors.push('Request mapping: use a field name and a JSON Pointer, such as /text. An empty pointer maps the full input.')
    for (const key of ['output_pointer', 'trace_pointer', 'metadata_pointer', 'usage_pointer', 'cost_pointer']) if (draft[key] && !String(draft[key]).startsWith('/')) errors.push(`${key}: start with /, or leave empty for the root.`)
  }
  if (kind === 'evaluator') {
    if (!evaluatorKinds.some(k => k.value === draft.kind)) errors.push('Choose a supported evaluator.')
    if (!draft.metric_key || !/^[a-zA-Z0-9_.-]+$/.test(draft.metric_key)) errors.push('Metric key: use letters, numbers, dots, underscores or hyphens.')
    const c = draft.config || {}
    if (draft.kind === 'field_comparison' && (!Array.isArray(c.paths) || !c.paths.length || c.paths.some((p: unknown) => typeof p !== 'string' || (!!p && !p.startsWith('/'))))) errors.push('Add at least one valid JSON Pointer path, such as /answer.')
    if (draft.kind === 'classification' && (!Array.isArray(c.labels) || !c.labels.length || new Set(c.labels).size !== c.labels.length)) errors.push('Add distinct classification labels.')
    if (draft.kind === 'llm_judge') {
      if (!c.rubric?.trim() || !c.rubric_version?.trim()) errors.push('A rubric and rubric version are required.')
      if (c.mode === 'live' && (!c.model?.trim() || !c.credential_id)) errors.push('Live judging needs a model and a saved credential.')
    }
  }
  if (kind === 'suite') {
    if (!Array.isArray(draft.evaluator_version_ids) || !draft.evaluator_version_ids.length) return ['Select at least one evaluator version.']
    const selected = project?.resources.filter(r => r.kind === 'evaluator').flatMap(r => r.versions).filter(v => draft.evaluator_version_ids.includes(v.id)) || []
    if (new Set(selected.map(v => v.config.metric_key)).size !== selected.length) errors.push('Each evaluator in a suite must have a different metric key.')
  }
  return errors
}
