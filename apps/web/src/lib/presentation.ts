import { percent, type Experiment, type Obj, type Project, type Result } from '@/api/client'

export function metricLabel(key: string) {
  const names: Record<string, string> = {
    schema_valid: 'Schema validity', field_accuracy: 'Field accuracy',
    material_correct: 'Material accuracy', weight_correct: 'Weight accuracy',
    country_correct: 'Country accuracy', record_exact: 'Exact record', source_support: 'Source support',
  }
  const label = names[key] || key.replace(/[_.]+/g, ' ')
  return label.charAt(0).toUpperCase() + label.slice(1)
}

export function caseLabel(data: Obj | undefined, fallback: string) {
  const name = data?.context?.product || data?.input?.title
  return typeof name === 'string' && name.trim() ? name : fallback
}

export function criteriaSummary(results: Result[], expected = results.length) {
  const total = Math.max(expected, results.length)
  const scored = results.filter(r => r.status === 'scored')
  const passed = scored.filter(r => r.passed === true).length
  const failed = scored.filter(r => r.passed === false).length
  return { total, scored: scored.length, passed, failed, unscored: total - scored.length, noDecision: scored.length - passed - failed }
}

export function suiteMetrics(project: Project | undefined, experiment: Experiment | undefined) {
  if (!project || !experiment) return []
  const versions = project.resources.flatMap(r => r.versions)
  const ids: string[] = versions.find(v => v.id === experiment.suite_version_id)?.config.evaluator_version_ids || []
  return [...new Set(ids.map(id => versions.find(v => v.id === id)?.config.metric_key).filter((key): key is string => typeof key === 'string'))]
}

export function comparisonMetrics(project: Project | undefined, baselineId: string, candidateId: string) {
  const left = suiteMetrics(project, project?.experiments.find(e => e.id === baselineId))
  const right = suiteMetrics(project, project?.experiments.find(e => e.id === candidateId))
  return left.filter(key => right.includes(key))
}

export function preferredBaseline(project: Project, candidateId: string) {
  const candidate = project.experiments.find(e => e.id === candidateId)
  if (!candidate) return ''
  const compatible = project.experiments.filter(e => e.id !== candidateId && e.dataset_version_id === candidate.dataset_version_id && ['completed', 'partially_failed', 'failed', 'canceled'].includes(e.status))
  return compatible.find(e => e.id === candidate.baseline_id)?.id
    || compatible.find(e => project.baselines.some(b => b.experiment_id === e.id))?.id
    || compatible.at(-1)?.id || ''
}

export function releaseReason(reason: string) {
  if (reason === 'No pinned baseline available') return 'This run has no pinned baseline. Choose a candidate run with a baseline.'
  const minimum = reason.match(/^(.+): minimum accuracy ([\d.e-]+) not met$/)
  if (minimum) return `${metricLabel(minimum[1]!)}: minimum score of ${percent(Number(minimum[2]))} not met`
  const criterion = reason.match(/^([^:]+): (insufficient evaluation coverage|evaluator errors)$/)
  if (criterion) return `${metricLabel(criterion[1]!)}: ${criterion[2]}`
  const missing = reason.match(/^Configured metric does not exist: (.+)$/)
  if (missing) return `Required criterion is missing: ${metricLabel(missing[1]!)}`
  return reason
}
