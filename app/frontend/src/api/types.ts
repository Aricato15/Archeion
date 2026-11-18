/** "archeion" (this repo's docs/), "registry" (the private registry folder) or a project's id. */
export type SourceId = string
export const SELF = 'archeion'
export const REGISTRY = 'registry'
/** Sources that are folders of this repo rather than registered projects. */
export const isOwnSource = (id: SourceId) => id === SELF || id === REGISTRY

export type TreeNode = {
  name: string
  path: string
  type: 'dir' | 'file'
  children?: TreeNode[]
}

export type DocFile = {
  source: SourceId
  path: string
  content: string
  sha: string
  modified_at: string
  dirty: boolean
  /** gitignored by design (the registry): no history, never "uncommitted" */
  private?: boolean
  frontmatter: Record<string, unknown> | null
}

export type Commit = {
  rev: string
  short: string
  author_name: string
  date: string
  subject: string
}

export type DiffResult = { source: SourceId; path: string; rev: string; diff: string }
export type DocAt = { source: SourceId; path: string; rev: string; content: string }

export type RoadmapItem = { text: string; links: { label: string; path: string }[] }
export type RoadmapDoc = {
  path: string
  updated: string | null
  now: RoadmapItem[]
  next: RoadmapItem[]
  later: RoadmapItem[]
  structured: boolean
  plans: { path: string; title: string; date: string | null }[]
}
export type Roadmaps = {
  cross: RoadmapDoc | null
  projects: { project: string; title: string; roadmap: RoadmapDoc | null }[]
}

export type Diagram = {
  source: SourceId
  path: string
  heading: string | null
  index: number
  line: number
  code: string
}
export type SearchHit = { source: SourceId; path: string; line: number; snippet: string }

export type Source = { id: SourceId; title: string; kind: 'archeion' | 'registry' | 'project' }

export type ProjectStatus = 'active' | 'paused' | 'archived' | 'planned'

/** ADR 0027: a 'group' is a group with a home, set by promoting a project; it's never detected. */
export type ProjectType = 'project' | 'module' | 'group'

export type Project = {
  id: string
  title: string
  page: string
  path: string | null
  /** A named root from ARCHEION_ROOTS (ADR 0008); null: `path` is relative to Archeion. */
  root: string | null
  parent: string | null
  group: string | null
  status: ProjectStatus | string
  kind: string | null
  /** ADR 0016: a project has its own repository, a module lives inside one. */
  type: ProjectType
  /** 'page': set with `type:` on the registry page; 'detected': worked out from the folder. */
  type_source: 'page' | 'detected'
  /** What it would be without `type:` on its page. */
  detected_type: ProjectType
  /** A module's project (its nearest ancestor that's a project); null for a project. */
  owner: string | null
  /** ADR 0017: whether Archeion's /inbox may edit this project's files for its inbox items. */
  inbox_edits: boolean
  /** 'page': `inbox_edits:` on its page; 'owner': a module following its project; 'default': allowed. */
  inbox_edits_source: 'page' | 'owner' | 'default'
  ports: number[]
  depends_on: string[]
  /** Groups without a home that it depends on (ADR 0027). */
  depends_on_groups: string[]
  docs_dir: string
  verified: string | null
  summary: string
  available: boolean
  children: string[]
  used_by: string[]
  /** A group with a home (ADR 0027): its member pages. Empty for anything else. */
  members: string[]
  /** When it was promoted to a group (ISO time), if it was. */
  promoted: string | null
  /** A group promoted after it was studied, with no newer study yet (ADR 0027). */
  needs_restudy: boolean
}

/** What promoting a project to a group would do, and what stops it (ADR 0027). */
export type PromotePlan = {
  project: string
  page: string
  ok: boolean
  problems: string[]
  members: string[]
  group_page: string | null
  has_study: boolean
  has_design: boolean
}

export type Group = {
  id: string
  title: string
  page: string
  summary: string
  projects: string[]
  /** The project page of the same name that gives the group a folder (ADR 0027); null for a virtual group. */
  home: string | null
  /** Projects that list this group under depends_on. */
  used_by: string[]
}

export type Registry = {
  projects: Project[]
  groups: Group[]
  /** `page` is empty for problems in the settings (.env) rather than in a registry page. */
  warnings: { page: string; message: string }[]
  unregistered: { name: string; path: string; root: string | null; parent: string | null }[]
}

/** A root Archeion may read projects from (ADR 0008), with the projects registered in it. */
export type RootEntry = { name: string; folder: string; projects: string[] }

export type RootsSettings = {
  /** ARCHEION_WORKSPACE_ROOT, the root named "workspace"; null when it isn't set (the default, ADR 0012). */
  workspace: RootEntry | null
  roots: RootEntry[]
  /** Entries of ARCHEION_ROOTS that were refused; saving drops them. */
  errors: string[]
  editable: boolean
  locked_reason: string | null
}

/** A folder found in a root, or a registered project living there (ADR 0010). */
/** A project that was removed and not registered since (ADR 0026). */
export type RemovedProject = {
  name: string
  removed_on: string
  path: string | null
  root: string | null
  /** What the registry still keeps for it besides its page: studies, designs, glossary, reports. */
  kept: string[]
}

export type RootItem = {
  /** The project it's registered as, or the name suggested for registering it. */
  name: string
  path: string | null
  root: string | null
  /** Where it is inside the root. */
  folder: string
  parent_folder: string | null
  /** The registered project it sits inside. */
  parent: string | null
  registered: string | null
  /** Its type once registered without a choice (ADR 0016), or a registered project's type. */
  detected_type: ProjectType
}

export type RootSurvey = { name: string; folder: string | null; granted: boolean; items: RootItem[] }

/** Where a project's folder is, as the registry says it: `root:path`, or just `path`. */
export function locationOf(item: { path: string | null; root: string | null }): string | null {
  if (!item.path) return null
  return item.root ? `${item.root}:${item.path}` : item.path
}

export type FeedbackKind = 'prompt' | 'review' | 'comment'
export type FeedbackStatus = 'open' | 'in_progress' | 'answered' | 'resolved'

export type StudyElementKind = 'component' | 'flow' | 'activity' | 'state machine' | 'entity' | 'interface' | 'finding'

export type Anchor = {
  heading?: string
  lines?: [number, number]
  quote?: string
  /** A job the thread is about, such as studying a project (ADR 0020). Needs no doc. */
  task?: { type: 'study' | 'design' | 'handoff-design' | 'report'; project: string; slug?: string; revision?: number }
  /** An element of a code study (ADR 0019), for a question about it. Needs no doc. */
  study?: { project: string; snapshot: string; element: string; kind: StudyElementKind }
}

export type FeedbackItem = {
  id: number
  kind: FeedbackKind
  source: SourceId
  /** The registered project whose session sent it (ADR 0009); null when written in the viewer. */
  origin: string | null
  doc_path: string | null
  anchor: Anchor | null
  body: string
  status: FeedbackStatus
  reply: string | null
  /** The message this one follows up on. */
  parent_id: number | null
  /** The thread's first item (ADR 0018); equal to id for the first one. */
  thread_id: number
  doc_rev: string | null
  created_at: string
  updated_at: string
  claimed_at: string | null
  answered_at: string | null
}

/**
 * One thread in a list (ADR 0018): its first item's request, doc and anchor, with the
 * thread's status (its latest item's), latest reply and last change in their place.
 */
export type FeedbackThread = FeedbackItem & {
  messages: number
  latest_id: number
}

/** Threads per status. */
export type FeedbackSummary = Record<FeedbackStatus, number> & { waiting_by_source: Record<SourceId, number> }

export type NewFeedback = {
  /** Required for a new thread; a follow-up takes its thread's. */
  kind?: FeedbackKind
  body: string
  source?: SourceId | null
  doc_path?: string | null
  anchor?: Anchor | null
  parent_id?: number | null
}

/** On-demand Claude (ADR 0020, ADR 0021): a Claude run started whenever a new message waits. */
export type ResponderStatus = {
  enabled: boolean
  running: boolean
  /** The runs going now: a visible session in its own window, or headless. */
  jobs: { pid: number; started_at: string; mode: 'window' | 'headless' }[]
  /** Runs open no window; their events go to a log. */
  headless: boolean
  /** Auto permission mode (true), or seek the user's confirmation for each (both terminals). */
  accept_edits: boolean
  /** How many Claude processes may run at once, the inbox terminal included (1 or 2). */
  max_instances: number
  /** Claude processes running now, the inbox terminal included. */
  instances: number
  terminal_running: boolean
  last_run_at: string | null
  /** Open messages newer than the last run. */
  waiting: number
  can_start: boolean
  reason: string | null
}

/** The inbox terminal: Claude Code running `/loop <interval> /inbox` (ADR 0013). */
export type RunnerStatus = {
  running: boolean
  /** The saved interval, such as 10m or 1h. A running terminal keeps the one it started with. */
  interval: string
  pid: number | null
  started_at: string | null
  can_start: boolean
  /** Why it can't be started here, when can_start is false. */
  reason: string | null
}
