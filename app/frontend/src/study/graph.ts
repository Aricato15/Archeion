import type { StudyActivity, StudyComponent, StudyModel, StudyStates } from '../api/study'
import type { EdgeStyle, Graph, GraphNode, NodeTone } from '../graph/graph'

/** A study's components as an interactive graph (GraphView): nested by parent, arrows from relations. */

const TONE: Partial<Record<StudyComponent['kind'], NodeTone>> = {
  service: 'blue',
  ui: 'grape',
  cli: 'grape',
  job: 'teal',
  database: 'orange',
  store: 'orange',
  external: 'gray',
  library: 'green',
}

/** The colour a component kind gets on the maps, and on the flow view's participants. */
export const toneOf = (kind: string | undefined): NodeTone | undefined => TONE[kind as StudyComponent['kind']]

const SHAPE: Partial<Record<StudyComponent['kind'], GraphNode['shape']>> = {
  database: 'store',
  store: 'store',
  external: 'external',
  module: 'round',
  package: 'round',
  function: 'round',
  class: 'round',
}

const STYLE: Record<string, EdgeStyle> = {
  imports: 'dotted',
  calls: 'solid',
  reads: 'solid',
  writes: 'thick',
  sql: 'thick',
  http: 'dashed',
  event: 'dashed',
}

export type ComponentGraphOptions = {
  /** Only this component's insides, with what they link to outside drawn as ghosts. */
  focus?: string | null
  hideKinds?: string[]
}

export function componentGraph(model: StudyModel, opts: ComponentGraphOptions = {}): Graph {
  const byId = new Map(model.components.map((c) => [c.id, c]))
  const focus = opts.focus && byId.has(opts.focus) ? opts.focus : null
  const inside = (id: string): boolean => {
    if (!focus) return true
    let cur = byId.get(id)?.parent
    const seen = new Set<string>()
    while (cur && !seen.has(cur)) {
      if (cur === focus) return true
      seen.add(cur)
      cur = byId.get(cur)?.parent
    }
    return false
  }
  const hide = new Set(opts.hideKinds ?? [])
  const rels = model.relations.filter((r) => !hide.has(r.kind) && byId.has(r.from) && byId.has(r.to))
  const shown = new Set(model.components.filter((c) => inside(c.id)).map((c) => c.id))
  const ghosts = new Set<string>()
  if (focus) {
    // The outermost ancestor outside the focus stands in for anything it contains.
    const outer = (id: string) => {
      let cur = byId.get(id)!
      // Bounded: an invalid snapshot (served raw) could have a parent cycle.
      for (let i = 0; i < 100 && cur.parent && byId.has(cur.parent); i++) {
        if (cur.parent === focus || isAncestorOf(byId, cur.parent, focus)) break
        cur = byId.get(cur.parent)!
      }
      return cur.id
    }
    for (const r of rels) {
      if (shown.has(r.from) && !shown.has(r.to) && r.to !== focus) ghosts.add(outer(r.to))
      if (shown.has(r.to) && !shown.has(r.from) && r.from !== focus) ghosts.add(outer(r.from))
    }
  }
  const node = (c: StudyComponent, ghost: boolean): GraphNode => ({
    id: c.id,
    label: c.name,
    sublabel: [c.kind, c.tech].filter(Boolean).join(' · '),
    parent: ghost || c.parent === focus ? null : (c.parent ?? null),
    shape: SHAPE[c.kind] ?? 'box',
    tone: TONE[c.kind],
    ghost,
  })
  const nodes = [
    ...model.components.filter((c) => shown.has(c.id)).map((c) => node(c, false)),
    ...[...ghosts].map((id) => node(byId.get(id)!, true)),
  ]
  const present = new Set(nodes.map((n) => n.id))
  // Relations to a ghost's insides attach to the ghost.
  const attach = (id: string): string | null => {
    let cur: string | undefined = id
    const seen = new Set<string>()
    while (cur && !seen.has(cur)) {
      if (present.has(cur)) return cur
      seen.add(cur)
      cur = byId.get(cur)?.parent
    }
    return null
  }
  const edges = rels.flatMap((r) => {
    const a = attach(r.from)
    const b = attach(r.to)
    if (!a || !b || a === b) return []
    return [{ id: r.id, from: a, to: b, label: r.label, style: STYLE[r.kind] ?? 'solid' }]
  })
  return { nodes, edges }
}

function isAncestorOf(byId: Map<string, StudyComponent>, ancestor: string, id: string): boolean {
  let cur = byId.get(id)?.parent
  const seen = new Set<string>()
  while (cur && !seen.has(cur)) {
    if (cur === ancestor) return true
    seen.add(cur)
    cur = byId.get(cur)?.parent
  }
  return false
}

/** Containers that start folded so the map opens `depth` levels deep. */
export function foldedAtDepth(graph: Graph, depth: number): string[] {
  const parentOf = new Map(graph.nodes.map((n) => [n.id, n.parent ?? null]))
  const hasKids = new Set(graph.nodes.map((n) => n.parent).filter((p): p is string => Boolean(p)))
  const level = (id: string) => {
    let n = 0
    let cur = parentOf.get(id)
    while (cur && n < 50) {
      n += 1
      cur = parentOf.get(cur)
    }
    return n
  }
  return [...hasKids].filter((id) => level(id) >= depth)
}

// --- states and activities -------------------------------------------------------------------

/** A state machine as a graph: states as rounded boxes, the initial one green and the final ones red. */
export function stateGraph(m: StudyStates): Graph {
  const finals = new Set(m.final ?? [])
  const nodes: GraphNode[] = m.states.map((s) => ({
    id: s.id,
    label: s.label || s.id,
    shape: 'round',
    sublabel: s.id === m.initial ? 'initial' : finals.has(s.id) ? 'final' : undefined,
    tone: s.id === m.initial ? 'green' : finals.has(s.id) ? 'red' : 'default',
  }))
  const ids = new Set(m.states.map((s) => s.id))
  const edges = m.transitions
    .filter((t) => ids.has(t.from) && ids.has(t.to))
    .map((t, i) => ({ id: `t${i}`, from: t.from, to: t.to, label: t.label }))
  return { nodes, edges }
}

/** An activity as a flowchart: start and end as round boxes, decisions in orange, actions plain. */
export function activityGraph(a: StudyActivity): Graph {
  const nodes: GraphNode[] = a.nodes.map((n) => {
    const kind = n.kind ?? 'action'
    return {
      id: n.id,
      label: n.label || (kind === 'start' ? 'Start' : kind === 'end' ? 'End' : n.id),
      shape: kind === 'start' || kind === 'end' ? 'round' : 'box',
      sublabel: kind === 'decision' ? 'decision' : undefined,
      tone: kind === 'start' ? 'green' : kind === 'end' ? 'red' : kind === 'decision' ? 'orange' : 'default',
    }
  })
  const ids = new Set(a.nodes.map((n) => n.id))
  const edges = a.edges
    .filter((e) => ids.has(e.from) && ids.has(e.to))
    .map((e, i) => ({ id: `e${i}`, from: e.from, to: e.to, label: e.label }))
  return { nodes, edges }
}
