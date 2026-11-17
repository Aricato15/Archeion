import type { CatalogEntry, ReportOptions, ReportPreset } from '../api/reports'

/**
 * The standard report's configuration (ADR 0025), as plain functions over an ordered list of
 * section ids. The dialog keeps that list; checking a box adds to it, dragging reorders it, and
 * a preset is the list plus the page options.
 */
export type Selection = string[]

export const DEFAULT_OPTIONS: ReportOptions = { page_size: 'A4', orientation: 'portrait', cover: true, toc: true }

export const GROUP_ORDER: CatalogEntry['group'][] = ['overview', 'docs', 'study', 'design', 'glossary', 'system']

export const GROUP_TITLES: Record<CatalogEntry['group'], string> = {
  overview: 'Overview',
  docs: 'Project docs',
  study: 'Code study',
  design: 'Design',
  glossary: 'Glossary',
  system: 'In the system',
}

/** What a new report holds: every section that has a source, in catalog order. */
export const defaultSelection = (entries: CatalogEntry[]): Selection =>
  entries.filter((e) => e.available).map((e) => e.id)

export const groupEntries = (entries: CatalogEntry[]): { group: CatalogEntry['group']; entries: CatalogEntry[] }[] =>
  GROUP_ORDER.map((group) => ({ group, entries: entries.filter((e) => e.group === group) })).filter(
    (g) => g.entries.length > 0,
  )

/**
 * Adds a section, or removes it. A sub-system diagram is placed after the last section of its
 * parent map, so a map and its parts stay together until the reader moves them.
 */
export function toggle(selection: Selection, entry: CatalogEntry, entries: CatalogEntry[]): Selection {
  if (selection.includes(entry.id)) return selection.filter((id) => id !== entry.id)
  if (entry.parent) {
    const family = new Set([entry.parent, ...entries.filter((e) => e.parent === entry.parent).map((e) => e.id)])
    let last = -1
    selection.forEach((id, i) => {
      if (family.has(id)) last = i
    })
    if (last >= 0) return [...selection.slice(0, last + 1), entry.id, ...selection.slice(last + 1)]
  }
  return [...selection, entry.id]
}

/** Checks or unchecks every available section of one group, keeping the order of what stays. */
export function toggleGroup(
  selection: Selection,
  entries: CatalogEntry[],
  group: CatalogEntry['group'],
  on: boolean,
): Selection {
  const inGroup = entries.filter((e) => e.group === group && e.available)
  if (!on) {
    const drop = new Set(inGroup.map((e) => e.id))
    return selection.filter((id) => !drop.has(id))
  }
  return inGroup.reduce((sel, e) => (sel.includes(e.id) ? sel : toggle(sel, e, entries)), selection)
}

export type GroupState = 'all' | 'some' | 'none'

export function groupState(selection: Selection, entries: CatalogEntry[], group: CatalogEntry['group']): GroupState {
  const ids = entries.filter((e) => e.group === group && e.available).map((e) => e.id)
  const chosen = ids.filter((id) => selection.includes(id)).length
  return chosen === 0 ? 'none' : chosen === ids.length ? 'all' : 'some'
}

/** A saved preset's sections that still have a source, and the ones that don't any more. */
export function fromPreset(preset: ReportPreset, entries: CatalogEntry[]): { selection: Selection; dropped: string[] } {
  const usable = new Set(entries.filter((e) => e.available).map((e) => e.id))
  const ids = preset.sections.map((s) => s.id)
  return { selection: ids.filter((id) => usable.has(id)), dropped: ids.filter((id) => !usable.has(id)) }
}

export const NAME_PATTERN = /^[a-z0-9][a-z0-9-]{0,39}$/

/** The name a typed preset name becomes: lowercase letters, digits and dashes. */
export const slugName = (text: string): string =>
  text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 40)

export function toPreset(input: {
  name: string
  title: string
  options: ReportOptions
  selection: Selection
}): ReportPreset {
  return {
    name: input.name,
    mode: 'standard',
    title: input.title.trim(),
    options: input.options,
    sections: input.selection.map((id) => ({ id })),
  }
}
