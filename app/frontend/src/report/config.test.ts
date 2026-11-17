import { describe, expect, it } from 'vitest'
import type { CatalogEntry, ReportPreset } from '../api/reports'
import {
  DEFAULT_OPTIONS,
  defaultSelection,
  fromPreset,
  groupEntries,
  groupState,
  slugName,
  toggle,
  toggleGroup,
  toPreset,
} from './config'

const e = (id: string, group: CatalogEntry['group'], extra: Partial<CatalogEntry> = {}): CatalogEntry => ({
  id,
  group,
  title: id,
  kind: 'text',
  available: true,
  reason: null,
  parent: null,
  ...extra,
})

const entries: CatalogEntry[] = [
  e('overview.facts', 'overview'),
  e('docs:README.md', 'docs'),
  e('study.map', 'study', { kind: 'diagram' }),
  e('study.sub:a', 'study', { kind: 'diagram', parent: 'study.map' }),
  e('study.sub:b', 'study', { kind: 'diagram', parent: 'study.map' }),
  e('study.flow:f', 'study', { kind: 'diagram' }),
  e('design.brief', 'design', { available: false, reason: 'no design yet' }),
]

describe('selection', () => {
  it('starts with every available section in catalog order', () => {
    expect(defaultSelection(entries)).toEqual([
      'overview.facts',
      'docs:README.md',
      'study.map',
      'study.sub:a',
      'study.sub:b',
      'study.flow:f',
    ])
  })

  it('adds at the end and removes in place', () => {
    const sel = toggle(['overview.facts'], entries[1]!, entries)
    expect(sel).toEqual(['overview.facts', 'docs:README.md'])
    expect(toggle(sel, entries[1]!, entries)).toEqual(['overview.facts'])
  })

  it('keeps a sub-system diagram next to its map, even after the reader moved things', () => {
    const sel = ['study.map', 'study.sub:a', 'overview.facts', 'study.flow:f']
    expect(toggle(sel, entries[4]!, entries)).toEqual([
      'study.map',
      'study.sub:a',
      'study.sub:b',
      'overview.facts',
      'study.flow:f',
    ])
    // With no map chosen it goes to the end.
    expect(toggle(['overview.facts'], entries[3]!, entries)).toEqual(['overview.facts', 'study.sub:a'])
  })

  it('toggles a whole group, skipping what has no source and keeping other order', () => {
    const none = toggleGroup(defaultSelection(entries), entries, 'study', false)
    expect(none).toEqual(['overview.facts', 'docs:README.md'])
    expect(toggleGroup(['docs:README.md'], entries, 'design', true)).toEqual(['docs:README.md'])
    expect(toggleGroup(['study.flow:f'], entries, 'study', true)).toEqual([
      'study.flow:f',
      'study.map',
      'study.sub:a',
      'study.sub:b',
    ])
  })

  it('says whether a group is fully, partly or not chosen', () => {
    expect(groupState(['study.map'], entries, 'study')).toBe('some')
    expect(groupState(defaultSelection(entries), entries, 'study')).toBe('all')
    expect(groupState([], entries, 'study')).toBe('none')
  })

  it('groups the catalog in the report order and leaves out empty groups', () => {
    expect(groupEntries(entries).map((g) => g.group)).toEqual(['overview', 'docs', 'study', 'design'])
  })
})

describe('presets', () => {
  const preset: ReportPreset = {
    name: 'full',
    mode: 'standard',
    title: 'T',
    options: DEFAULT_OPTIONS,
    sections: [{ id: 'study.flow:f' }, { id: 'design.brief' }, { id: 'gone' }, { id: 'overview.facts' }],
  }

  it('loads what still has a source, in the saved order, and says what was dropped', () => {
    expect(fromPreset(preset, entries)).toEqual({
      selection: ['study.flow:f', 'overview.facts'],
      dropped: ['design.brief', 'gone'],
    })
  })

  it('builds a standard preset from the dialog state', () => {
    expect(toPreset({ name: 'full', title: '  Q4  ', options: DEFAULT_OPTIONS, selection: ['overview.facts'] })).toEqual({
      name: 'full',
      mode: 'standard',
      title: 'Q4',
      options: DEFAULT_OPTIONS,
      sections: [{ id: 'overview.facts' }],
    })
  })

  it('turns a typed name into one the backend accepts', () => {
    expect(slugName('  Executive Summary! ')).toBe('executive-summary')
    expect(slugName('***')).toBe('')
    expect(slugName('x'.repeat(60))).toHaveLength(40)
  })
})
