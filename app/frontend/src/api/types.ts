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
  ports: number[]
  depends_on: string[]
  docs_dir: string
  verified: string | null
  summary: string
  available: boolean
  children: string[]
  used_by: string[]
}

export type Group = { id: string; title: string; page: string; summary: string; projects: string[] }

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
export type RootItem = {
  /** The project it's registered as, or the name suggested for registering it. */
  name: string
  path: string | null
  root: string | null
  /** Where it is inside the root. */
  folder: string
  parent_folder: string | null
  /** The registered project it would be a sub-project of. */
  parent: string | null
  registered: string | null
}

export type RootSurvey = { name: string; folder: string | null; granted: boolean; items: RootItem[] }

/** Where a project's folder is, as the registry says it: `root:path`, or just `path`. */
export function locationOf(item: { path: string | null; root: string | null }): string | null {
  if (!item.path) return null
  return item.root ? `${item.root}:${item.path}` : item.path
}

export type FeedbackKind = 'prompt' | 'review' | 'comment'
export type FeedbackStatus = 'open' | 'in_progress' | 'answered' | 'resolved'

export type Anchor = {
  heading?: string
  lines?: [number, number]
  quote?: string
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
  parent_id: number | null
  doc_rev: string | null
  created_at: string
  updated_at: string
  claimed_at: string | null
  answered_at: string | null
}

export type FeedbackSummary = Record<FeedbackStatus, number> & { waiting_by_source: Record<SourceId, number> }

export type NewFeedback = {
  kind: FeedbackKind
  body: string
  source?: SourceId | null
  doc_path?: string | null
  anchor?: Anchor | null
  parent_id?: number | null
}
