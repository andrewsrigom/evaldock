import type { components } from './schema'

export type Launch = components['schemas']['Launch']
export type ResourceCreate = components['schemas']['ResourceCreate']
export type Json = null | boolean | number | string | Json[] | { [key: string]: Json }
export type Obj = Record<string, any>
export interface User { id: string; name: string; email: string; workspaces: { id: string; name: string; role: string }[] }
export interface Version { id: string; number: number; config: Obj; fingerprint: string; resource_id: string; created_at: string }
export interface Resource { id: string; name: string; kind: string; versions: Version[] }
export interface Experiment { id: string; project_id: string; name: string; status: string; dataset_version_id: string; suite_version_id: string; target_version_id: string | null; baseline_id: string | null; parent_id: string | null; mode: string; created_at: string; repetitions: number; concurrency: number; options: Obj }
export interface Project { id: string; name: string; description: string; fixture: boolean; workspace_id: string; resources: Resource[]; experiments: Experiment[]; baselines: { name: string; experiment_id: string }[] }
export interface Result { metric_key: string; status: string; score: number | null; passed: boolean | null; explanation: string; evidence: string[]; details: Obj; evaluator_version: string }
export interface Execution { id: string; experiment_id?: string; case_id: string; replicate: number; status: string; output: Json; output_present: boolean; trace: Json; case: Obj; results: Result[]; reviews: Obj[]; target_latency_ms: number | null; evaluation_latency_ms: number | null; target_error: string | null; metadata: Obj; late_completion: boolean; attempts?: Obj[]; experiment_name?: string }
export interface Report extends Experiment { executions: Execution[]; summary: Obj; calibration: Obj }
export interface Pair { case_id: string; replicate: number; state: string; baseline: Execution; candidate: Execution; delta: number | null }
export interface Comparison { metric_key: string; same_dataset: boolean; warning: string | null; counts: Record<string, number>; paired_count: number; rows: Pair[]; added: string[][]; removed: string[][]; changed: string[][]; delta: Obj; latency_comparable: boolean; baseline_name: string; candidate_name: string }

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api${path}`, { ...options, credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-EvalDock-CSRF': '1', ...options.headers } })
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: `Request failed (${response.status})` }))
    const detail = payload.detail
    const message = Array.isArray(detail) ? detail.map((issue: {loc?: (string | number)[]; msg?: string}) => `${(issue.loc || []).filter(p => p !== 'body').join(' → ')}: ${issue.msg || 'Invalid value'}`).join('\n') : typeof detail === 'string' ? detail : `Request failed (${response.status}). Please retry.`
    throw new Error(message)
  }
  return response.json() as Promise<T>
}
export const post = <T>(path: string, body: unknown = {}) => api<T>(path, { method: 'POST', body: JSON.stringify(body) })
export const percent = (value: number | null | undefined) => value == null ? '—' : `${(value * 100).toFixed(1)}%`
export const ms = (value: number | null | undefined) => value == null ? 'Unavailable' : `${value.toFixed(1)} ms`
export const pretty = (value: unknown) => JSON.stringify(value, null, 2)
export const human = (value: string) => value.replaceAll('_', ' ')
