import { describe, expect, it } from 'vitest'
import { compareVersions, updateNotes } from './updates'

describe('updates', () => {
  it('compares versions by number, not by text', () => {
    expect(compareVersions('1.10.0', '1.9.3')).toBeGreaterThan(0)
    expect(compareVersions('1.4.0', '1.4.0')).toBe(0)
    expect(compareVersions('1.3.2', '2.0.0')).toBeLessThan(0)
  })

  it('finds the notes and puts the newest first', () => {
    const notes = updateNotes([
      'updates/README.md',
      'updates/update-v1.3.2.md',
      'updates/update-v1.10.0.md',
      'guides/update_archeion_and_plugin.md',
      'updates/update-v1.4.0.md',
    ])
    expect(notes.map((n) => n.version)).toEqual(['1.10.0', '1.4.0', '1.3.2'])
    expect(notes[0].path).toBe('updates/update-v1.10.0.md')
  })
})
