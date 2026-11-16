/** Designs (ADR 0022): the API's views of registry/designs/. The model is a study's, intended rather than found. */

import type { StudyModel } from './study'

export type DesignStage = 'brief' | 'architecture' | 'plan' | 'approved' | 'handed off'
export const WORKING_STAGES = ['brief', 'architecture', 'plan'] as const
export const STAGES: DesignStage[] = ['brief', 'architecture', 'plan', 'approved', 'handed off']

export type DesignRevision = {
  id: string
  number: number
  date: string
  handoff: { thread: number | null; requested: string; consumed: string | null } | null
}

export type DesignStructure = {
  ports?: number[]
  depends_on?: string[]
  group?: string
  kind?: string
  status?: string
}

/** A design as lists show it. */
export type DesignRow = {
  project: string
  slug: string
  stage: DesignStage
  updated: string | null
  thread: number | null
  revision: number | null
  revisions: DesignRevision[]
  changed_since_revision: boolean
  summary: string
  valid: boolean
  problems: string[]
  files: Record<string, boolean>
  counts: Record<'components' | 'exposes' | 'calls' | 'entities' | 'flows', number>
  structure: DesignStructure
}

/** The design's model: a study's sections without a commit or findings, plus the structural facts. */
export type DesignModel = Omit<StudyModel, 'meta' | 'findings'> & {
  meta: { project: string; date: string; summary?: string; stack?: string[] }
  structure?: DesignStructure
}

export type DesignFull = Omit<DesignRow, 'files'> & {
  /** "working copy" or "revision N". */
  label: string
  /** Every document's text by name (decisions as decisions/NNNN-title.md). */
  files: Record<string, string>
  model: DesignModel
  model_problems: string[]
}

export type PreflightProblem = { severity: 'block' | 'warn' | 'info'; code: string; message: string; fix: string | null }
export type Preflight = { ok: boolean; problems: PreflightProblem[] }

export type Approval = {
  problems: string[]
  changes: { key: string; old: unknown; new: unknown; value: string }[]
  page: string
  next_revision: number
}

/** A model the study views can draw: they want a commit, and a design has none. */
export function asStudyModel(model: DesignModel | null | undefined): StudyModel | null {
  if (!model || !model.meta) return null
  const list = <T,>(v: T[] | undefined) => (Array.isArray(v) ? v : [])
  return {
    schema: 1,
    meta: { ...model.meta, commit: 'design' },
    components: list(model.components),
    relations: list(model.relations),
    interfaces: { exposes: list(model.interfaces?.exposes), calls: list(model.interfaces?.calls) },
    entities: list(model.entities).map((e) => ({ ...e, fields: list(e.fields) })),
    flows: list(model.flows).map((f) => ({ ...f, participants: list(f.participants), steps: list(f.steps) })),
    activities: list(model.activities).map((a) => ({ ...a, nodes: list(a.nodes), edges: list(a.edges) })),
    states: list(model.states).map((s) => ({ ...s, states: list(s.states), transitions: list(s.transitions) })),
    findings: [],
    questions: list(model.questions),
  }
}

/** What a design asks of another project (ADR 0022): a neighbour to tell, and what to tell it. */
export type Impact = {
  kind: string
  severity: 'block' | 'warn' | 'info'
  message: string
  neighbour: string | null
  suggestion: string | null
}

export type BuiltSection = { designed_only: string[]; built_only: string[]; both: number }
export type BuiltVsDesigned = { studied: string | null; sections: Record<string, BuiltSection> }
