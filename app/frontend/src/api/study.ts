/** Code studies (ADR 0019): the model a snapshot holds (`study.json`, schema 1) and the API's views of it. */

export type Cite = { path: string; line?: number; end?: number; snippet?: string }

type Element = { id: string; cites?: Cite[] }

export type ComponentKind =
  | 'service'
  | 'package'
  | 'module'
  | 'class'
  | 'function'
  | 'library'
  | 'database'
  | 'external'
  | 'ui'
  | 'cli'
  | 'job'
  | 'store'

export type StudyComponent = Element & {
  name: string
  kind: ComponentKind
  parent?: string
  summary?: string
  paths?: string[]
  tech?: string
}

export type RelationKind = 'imports' | 'calls' | 'http' | 'sql' | 'event' | 'reads' | 'writes'

export type StudyRelation = Element & { from: string; to: string; kind: RelationKind; label?: string }

export type Exposed = Element & {
  kind: 'http' | 'cli' | 'event' | 'file' | 'library'
  method?: string
  path?: string
  name?: string
  handler?: string
  summary?: string
}

export type Outgoing = Element & {
  kind: 'http' | 'event' | 'file' | 'library'
  target_project?: string
  target_url?: string
  port?: number
  method?: string
  path?: string
  from?: string
  summary?: string
}

export type EntityField = { name: string; type?: string; pk?: boolean; fk?: string; nullable?: boolean }

export type StudyEntity = Element & { name: string; store?: string; summary?: string; fields: EntityField[] }

export type FlowMessage = { from: string; to: string; label?: string; reply?: boolean; async?: boolean }
export type FlowNote = { note: string; over: string[] }
export type FlowBlock = {
  block: 'alt' | 'opt' | 'loop' | 'par'
  label?: string
  steps: FlowStep[]
  others?: { label?: string; steps: FlowStep[] }[]
}
export type FlowStep = FlowMessage | FlowNote | FlowBlock

export type StudyFlow = Element & {
  title: string
  summary?: string
  trigger?: string
  participants: string[]
  steps: FlowStep[]
}

export type StudyActivity = Element & {
  title: string
  summary?: string
  nodes: { id: string; label?: string; kind?: 'start' | 'end' | 'action' | 'decision' }[]
  edges: { from: string; to: string; label?: string }[]
}

export type StudyStates = Element & {
  title: string
  entity?: string
  summary?: string
  states: { id: string; label?: string }[]
  initial?: string
  final?: string[]
  transitions: { from: string; to: string; label?: string }[]
}

export type Finding = Element & { severity: 'info' | 'warn' | 'risk'; title: string; detail?: string; rule?: string }

export type StudyModel = {
  schema: 1
  meta: {
    project: string
    date: string
    commit: string
    dirty?: boolean
    summary?: string
    stack?: string[]
    coverage?: { files_total?: number; files_read?: number; note?: string }
    refreshed_from?: string
  }
  components: StudyComponent[]
  relations: StudyRelation[]
  interfaces: { exposes: Exposed[]; calls: Outgoing[] }
  entities: StudyEntity[]
  flows: StudyFlow[]
  activities: StudyActivity[]
  states: StudyStates[]
  findings: Finding[]
  questions: string[]
}

export type SnapshotCounts = Record<
  'components' | 'relations' | 'entities' | 'flows' | 'activities' | 'states' | 'findings' | 'exposes' | 'calls',
  number
>

/** A snapshot as lists show it. */
export type SnapshotRow = {
  id: string
  project: string
  date: string
  commit: string | null
  dirty: boolean
  summary: string
  counts: SnapshotCounts
  valid: boolean
  problems: string[]
  notes: boolean
  /** The draft of a study in progress (ADR 0020), listed ahead of the snapshots. */
  draft: boolean
  /** The feedback thread the study was discussed in, if any. */
  thread: number | null
  /** Commits in the project since the studied one; null when that can't be told. */
  commits_since: number | null
}

export type SnapshotFull = SnapshotRow & { model: StudyModel; notes_text: string }

/** One member of a group, with its latest study (ADR 0027). */
export type ComposedMember = {
  project: string
  title: string
  type: string
  kind: string | null
  snapshot: string | null
  date: string | null
  commit: string | null
  has_study: boolean
  valid: boolean
  commits_since: number | null
}

/** A group's study put together from its own and its members' (ADR 0027). */
export type ComposedStudy = {
  group: string
  own: string | null
  needs_restudy: boolean
  members: ComposedMember[]
  /** Components of the group's own study that a member's study replaced. */
  overridden: { component: string; name: string; group_summary: string; member_summary: string; differs: boolean }[]
  omitted: string[]
  model: StudyModel | null
  problems: string[]
}

export type DiffEntry = { id: string; label: string; fields?: string[] }
export type StudyDiff = {
  from: string
  to: string
  sections: Record<string, { added: DiffEntry[]; removed: DiffEntry[]; changed: DiffEntry[] }>
}

export type SystemLink = {
  from: string
  to: string
  calls: {
    id: string
    kind: string
    method?: string | null
    path?: string | null
    resolved_by: 'named' | 'port'
    exposed: string | null
    target_studied: boolean
  }[]
}

export type SystemLinks = {
  links: SystemLink[]
  unresolved: { from: string; call: string; target: string | number | null }[]
  drift: { project: string; code_only: string[]; registry_only: string[] }[]
  studied: string[]
}

/** An element of a latest study that matches a search. */
export type StudyHit = {
  project: string
  snapshot: string
  kind: 'component' | 'flow' | 'activity' | 'state machine' | 'entity' | 'interface' | 'finding'
  element: string
  label: string
  summary: string
}

/** Fill in sections a hand-edited or older model may leave out, so views can rely on them. */
export function normalizeModel(raw: Partial<StudyModel> | null | undefined): StudyModel | null {
  if (!raw || typeof raw !== 'object' || !raw.meta) return null
  const list = <T,>(v: T[] | undefined) => (Array.isArray(v) ? v : [])
  return {
    schema: 1,
    meta: raw.meta,
    components: list(raw.components),
    relations: list(raw.relations),
    interfaces: { exposes: list(raw.interfaces?.exposes), calls: list(raw.interfaces?.calls) },
    entities: list(raw.entities).map((e) => ({ ...e, fields: list(e.fields) })),
    flows: list(raw.flows).map((f) => ({ ...f, participants: list(f.participants), steps: list(f.steps) })),
    activities: list(raw.activities).map((a) => ({ ...a, nodes: list(a.nodes), edges: list(a.edges) })),
    states: list(raw.states).map((s) => ({ ...s, states: list(s.states), transitions: list(s.transitions) })),
    findings: list(raw.findings),
    questions: list(raw.questions),
  }
}
