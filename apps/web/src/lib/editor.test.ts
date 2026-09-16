import { describe, expect, it } from 'vitest'
import { defaults, validationErrors } from './editor'
import type { Project } from '@/api/client'
describe('version editor data integrity', () => {
  it('does not invent a null reference on a new case', () => {
    const draft = defaults('dataset')
    expect(draft.cases[0]).not.toHaveProperty('expected')
    draft.cases[0].expected = null
    expect(validationErrors('dataset', draft)).toEqual([])
    expect(JSON.parse(JSON.stringify(draft)).cases[0]).toHaveProperty('expected', null)
  })
  it('rejects duplicate IDs and absent inputs before saving a version', () => {
    const draft = { config: {}, cases: [{ case_id: 'a', input: null }, { case_id: 'a' }] }
    expect(validationErrors('dataset', draft)).toEqual(expect.arrayContaining(['Duplicate case_id: a', 'Case 2: input is required; null is allowed.']))
  })
  it('rejects malformed input mappings and embedded credentials', () => {
    expect(validationErrors('target', { endpoint: 'https://user:password@example.com', request_mapping: { text: 'reference.answer' } })).toHaveLength(2)
    expect(validationErrors('target', { endpoint: 'https://example.com', request_mapping: { text: '/text' }, output_pointer: '' })).toEqual([])
  })
  it('does not allow duplicate metric keys inside a suite', () => {
    const project = { resources: [{ kind: 'evaluator', versions: [{ id: 'a', config: { metric_key: 'quality' } }, { id: 'b', config: { metric_key: 'quality' } }] }] } as unknown as Project
    expect(validationErrors('suite', { evaluator_version_ids: ['a','b'] }, project)).toContain('Each evaluator in a suite must have a different metric key.')
  })
  it('requires model and credential for live judging, not for an explicit fixture', () => {
    const draft = { kind: 'llm_judge', metric_key: 'quality', config: { mode: 'live', rubric: 'Check answer', rubric_version: 'v1' } }
    expect(validationErrors('evaluator', draft)).toContain('Live judging needs a model and a saved credential.')
    draft.config.mode = 'fixture'
    expect(validationErrors('evaluator', draft)).toEqual([])
  })
})
