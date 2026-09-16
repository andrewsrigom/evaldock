import { describe, expect, it } from 'vitest'
import { jsonDiff } from './diff'
import { percent, ms } from '@/api/client'
describe('evidence formatting', () => {
  it('distinguishes absent keys, null values, and mismatches', () => {
    const rows = jsonDiff({ a: null, b: 2 }, { b: 3, c: null })
    expect(rows.find(r => r.path === '/a')).toMatchObject({ afterMissing: true, beforeMissing: false, changed: true })
    expect(rows.find(r => r.path === '/c')).toMatchObject({ beforeMissing: true, afterMissing: false })
    expect(rows.find(r => r.path === '/b')?.changed).toBe(true)
  })
  it('escapes JSON Pointer paths and preserves explicit zeros', () => {
    expect(jsonDiff({ 'a/b': { '~': 0 } }, { 'a/b': { '~': 0 } })[0]).toMatchObject({ path: '/a~1b/~0', changed: false })
    expect(percent(null)).toBe('—'); expect(percent(0)).toBe('0.0%')
    expect(ms(null)).toBe('Unavailable'); expect(ms(0)).toBe('0.0 ms')
  })
})
