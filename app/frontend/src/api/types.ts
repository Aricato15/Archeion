export type TreeNode = {
  name: string
  path: string
  type: 'dir' | 'file'
  children?: TreeNode[]
}

export type DocFile = {
  path: string
  content: string
  sha: string
  modified_at: string
  dirty: boolean
}

export type Commit = {
  rev: string
  short: string
  author_name: string
  date: string
  subject: string
}

export type DiffResult = { path: string; rev: string; diff: string }
export type DocAt = { path: string; rev: string; content: string }

export type RoadmapItem = { text: string; links: { label: string; path: string }[] }
export type Roadmap = {
  path: string
  updated: string | null
  now: RoadmapItem[]
  next: RoadmapItem[]
  later: RoadmapItem[]
  plans: { path: string; title: string; date: string | null }[]
}

export type Diagram = { path: string; heading: string | null; index: number; line: number; source: string }
export type SearchHit = { path: string; line: number; snippet: string }

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

export type FeedbackSummary = Record<FeedbackStatus, number>

export type NewFeedback = {
  kind: FeedbackKind
  body: string
  doc_path?: string | null
  anchor?: Anchor | null
  parent_id?: number | null
}
