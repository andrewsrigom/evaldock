export interface Difference { path: string; before: unknown; after: unknown; beforeMissing: boolean; afterMissing: boolean; changed: boolean }
function flatten(value: unknown, path = ''): Record<string, unknown> {
  if (value !== null && typeof value === 'object' && Object.keys(value).length) {
    return Object.assign({}, ...Object.entries(value).map(([key, child]) => flatten(child, `${path}/${key.replaceAll('~', '~0').replaceAll('/', '~1')}`)))
  }
  return { [path || '/']: value }
}
export function jsonDiff(before: unknown, after: unknown): Difference[] {
  const a = flatten(before), b = flatten(after)
  return [...new Set([...Object.keys(a), ...Object.keys(b)])].sort().map(path => ({ path, before: a[path], after: b[path], beforeMissing: !(path in a), afterMissing: !(path in b), changed: !(path in a) || !(path in b) || JSON.stringify(a[path]) !== JSON.stringify(b[path]) }))
}
