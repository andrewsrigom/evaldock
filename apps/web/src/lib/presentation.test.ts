import { describe, expect, it } from 'vitest'
import type { Experiment, Project, Result } from '@/api/client'
import { comparisonMetrics, criteriaSummary, preferredBaseline } from './presentation'

const run = (id: string, dataset: string, suite: string, baseline: string | null = null) => ({ id, dataset_version_id: dataset, suite_version_id: suite, baseline_id: baseline, status: 'completed' } as Experiment)
const project = {
  id: 'project', name: 'Pilot', description: '', fixture: true, workspace_id: 'workspace',
  experiments: [run('validation-ai', 'validation', 'ai', 'validation-base'), run('calibration-ai', 'calibration', 'ai', 'calibration-base'), run('calibration-base', 'calibration', 'rules'), run('validation-base', 'validation', 'rules')],
  baselines: [{ name: 'main', experiment_id: 'calibration-base' }, { name: 'validation', experiment_id: 'validation-base' }],
  resources: [{ id: 'resource', name: 'Criteria', kind: 'suite', versions: [{ id: 'ai', config: { evaluator_version_ids: ['exact', 'judge'] } }, { id: 'rules', config: { evaluator_version_ids: ['exact'] } }, { id: 'exact', config: { metric_key: 'record_exact' } }, { id: 'judge', config: { metric_key: 'source_support' } }].map(v => ({ ...v, number: 1, fingerprint: v.id, resource_id: 'resource', created_at: '2026-01-01' })) }],
} satisfies Project

describe('comparison defaults', () => {
  it('uses the validation baseline instead of the unrelated main baseline', () => {
    expect(preferredBaseline(project, 'validation-ai')).toBe('validation-base')
    expect(preferredBaseline(project, 'calibration-ai')).toBe('calibration-base')
  })
  it('does not invent a compatible baseline', () => {
    expect(preferredBaseline({ ...project, experiments: [project.experiments[0]!] }, 'validation-ai')).toBe('')
  })
  it('offers only criteria measured in both runs', () => {
    expect(comparisonMetrics(project, 'validation-base', 'validation-ai')).toEqual(['record_exact'])
    expect(comparisonMetrics(project, '', 'validation-ai')).toEqual([])
  })
})

it('keeps failures, missing scores and metrics without pass/fail distinct', () => {
  const results = [{ status: 'scored', passed: true }, { status: 'scored', passed: false }, { status: 'error', passed: null }, { status: 'scored', passed: null }] as Result[]
  expect(criteriaSummary(results, 5)).toEqual({ total: 5, scored: 3, passed: 1, failed: 1, unscored: 2, noDecision: 1 })
  expect(criteriaSummary([], 7).passed).toBe(0)
})
