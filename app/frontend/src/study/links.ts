import type { Anchor } from '../api/types'

const VIEW: Record<NonNullable<Anchor['study']>['kind'], string> = {
  component: 'components',
  flow: 'flows',
  activity: 'logic',
  'state machine': 'states',
  entity: 'data',
  interface: 'interfaces',
  finding: 'findings',
}

/** The project page's Study tab, opened on one element of one snapshot (ADR 0019). */
export function studyUrl(s: NonNullable<Anchor['study']>): string {
  const q = new URLSearchParams({ tab: 'study', snap: s.snapshot, view: VIEW[s.kind] })
  if (s.kind !== 'entity' && s.kind !== 'interface' && s.kind !== 'finding') q.set('item', s.element)
  return `/projects/${encodeURIComponent(s.project)}?${q}`
}
