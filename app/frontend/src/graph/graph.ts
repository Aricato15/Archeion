/**
 * The data side of GraphView (ADR 0015): a nested graph of boxes and arrows, folded and laid
 * out with ELK. Kept free of React so it can be unit tested. Both the registry maps and the
 * study component maps are built as a Graph.
 */

export type NodeTone = 'default' | 'blue' | 'grape' | 'teal' | 'orange' | 'gray' | 'red' | 'green'

export type GraphNode = {
  id: string
  label: string
  /** A second, smaller line: a kind, a status. */
  sublabel?: string
  /** The box it sits in. Boxes with children are drawn as containers that can fold. */
  parent?: string | null
  /** Shape hint: rounded for modules, a cylinder look for stores. */
  shape?: 'box' | 'round' | 'store' | 'external'
  tone?: NodeTone
  /** Drawn dashed: something outside what's shown, linked from inside. */
  ghost?: boolean
  /** Drawn faded: paused, archived. */
  dimmed?: boolean
}

export type EdgeStyle = 'solid' | 'dashed' | 'thick' | 'dotted'

export type GraphEdge = {
  id: string
  from: string
  to: string
  label?: string
  style?: EdgeStyle
  tone?: NodeTone
}

export type Graph = { nodes: GraphNode[]; edges: GraphEdge[] }

export type Positioned = {
  id: string
  x: number
  y: number
  width: number
  height: number
  /** The container it sits in, after folding (positions are relative to it). */
  parent: string | null
  container: boolean
  folded: boolean
}

export const LEAF_HEIGHT = 46
export const LEAF_SUB_HEIGHT = 58
const CHAR_WIDTH = 7.2
const MIN_WIDTH = 120
const MAX_WIDTH = 280
export const HEADER = 30

/** Width and height of a leaf box, from its text. */
export function leafSize(n: GraphNode): { width: number; height: number } {
  const chars = Math.max(n.label.length, (n.sublabel ?? '').length * 0.85)
  return {
    width: Math.round(Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, chars * CHAR_WIDTH + 36))),
    height: n.sublabel ? LEAF_SUB_HEIGHT : LEAF_HEIGHT,
  }
}

/** Every node's parent, ignoring parents that aren't in the graph and breaking cycles. */
export function parents(nodes: GraphNode[]): Map<string, string | null> {
  const ids = new Set(nodes.map((n) => n.id))
  const raw = new Map(nodes.map((n) => [n.id, n.parent && ids.has(n.parent) && n.parent !== n.id ? n.parent : null]))
  const out = new Map<string, string | null>()
  for (const n of nodes) {
    const seen = new Set<string>([n.id])
    let cur = raw.get(n.id) ?? null
    let ok = true
    while (cur) {
      if (seen.has(cur)) {
        ok = false
        break
      }
      seen.add(cur)
      cur = raw.get(cur) ?? null
    }
    out.set(n.id, ok ? (raw.get(n.id) ?? null) : null)
  }
  return out
}

/**
 * Hide the insides of folded containers. Edges into or out of hidden nodes move to their
 * nearest shown ancestor; edges that end up inside one box are dropped, and edges that land
 * on the same pair are merged (their labels joined, a count when there are many).
 */
export function fold(graph: Graph, folded: Set<string>): { graph: Graph; containers: Set<string> } {
  const parentOf = parents(graph.nodes)
  const hidden = new Set<string>()
  for (const n of graph.nodes) {
    let cur = parentOf.get(n.id) ?? null
    while (cur) {
      if (folded.has(cur)) {
        hidden.add(n.id)
        break
      }
      cur = parentOf.get(cur) ?? null
    }
  }
  const shownOf = (id: string): string | null => {
    let cur: string | null = id
    while (cur && hidden.has(cur)) cur = parentOf.get(cur) ?? null
    return cur
  }
  const nodes = graph.nodes.filter((n) => !hidden.has(n.id)).map((n) => ({ ...n, parent: parentOf.get(n.id) ?? null }))
  const hasKids = new Set<string>()
  for (const n of graph.nodes) {
    const p = parentOf.get(n.id)
    if (p) hasKids.add(p)
  }
  const containers = new Set([...hasKids].filter((id) => !hidden.has(id)))
  const merged = new Map<string, GraphEdge & { labels: string[]; count: number }>()
  for (const e of graph.edges) {
    const a = shownOf(e.from)
    const b = shownOf(e.to)
    if (!a || !b || a === b) continue
    // An edge between a box and something inside it says nothing once one end is folded away.
    if (isAncestor(parentOf, a, b) || isAncestor(parentOf, b, a)) continue
    const key = `${a}|${b}|${e.style ?? 'solid'}|${e.tone ?? ''}`
    const m = merged.get(key)
    if (m) {
      m.count += 1
      if (e.label && !m.labels.includes(e.label)) m.labels.push(e.label)
    } else {
      merged.set(key, { ...e, id: key, from: a, to: b, labels: e.label ? [e.label] : [], count: 1 })
    }
  }
  const edges: GraphEdge[] = [...merged.values()].map(({ labels, count, ...e }) => ({
    ...e,
    label:
      labels.length === 0
        ? count > 1
          ? `×${count}`
          : undefined
        : labels.slice(0, 2).join(', ') + (labels.length > 2 ? ` +${labels.length - 2}` : ''),
  }))
  return { graph: { nodes, edges }, containers }
}

function isAncestor(parentOf: Map<string, string | null>, ancestor: string, id: string): boolean {
  let cur = parentOf.get(id) ?? null
  while (cur) {
    if (cur === ancestor) return true
    cur = parentOf.get(cur) ?? null
  }
  return false
}

/** Ids of the nodes linked to `id` by an edge, plus `id` itself: what hovering highlights. */
export function neighbours(graph: Graph, id: string): Set<string> {
  const out = new Set([id])
  for (const e of graph.edges) {
    if (e.from === id) out.add(e.to)
    if (e.to === id) out.add(e.from)
  }
  return out
}

// --- ELK -----------------------------------------------------------------------------------------

export type ElkNode = {
  id: string
  width?: number
  height?: number
  x?: number
  y?: number
  children?: ElkNode[]
  edges?: { id: string; sources: string[]; targets: string[] }[]
  layoutOptions?: Record<string, string>
  labels?: { text: string }[]
}

export function toElk(graph: Graph, containers: Set<string>, direction: 'RIGHT' | 'DOWN'): ElkNode {
  const kids = new Map<string | null, GraphNode[]>()
  for (const n of graph.nodes) {
    const p = n.parent ?? null
    if (!kids.has(p)) kids.set(p, [])
    kids.get(p)!.push(n)
  }
  const build = (n: GraphNode): ElkNode => {
    const children = kids.get(n.id) ?? []
    if (containers.has(n.id) && children.length > 0) {
      return {
        id: n.id,
        children: children.map(build),
        layoutOptions: {
          'elk.padding': `[top=${HEADER + 12},left=14,bottom=14,right=14]`,
          'elk.direction': direction,
        },
      }
    }
    // A folded container keeps a header's worth of extra width for its fold button.
    const size = leafSize(n)
    return { id: n.id, width: size.width + (containers.has(n.id) ? 24 : 0), height: size.height }
  }
  return {
    id: '__root__',
    layoutOptions: {
      'elk.algorithm': 'layered',
      'elk.direction': direction,
      'elk.hierarchyHandling': 'INCLUDE_CHILDREN',
      'elk.layered.spacing.nodeNodeBetweenLayers': '56',
      'elk.spacing.nodeNode': '28',
      'elk.layered.nodePlacement.strategy': 'BRANDES_KOEPF',
      'elk.edgeRouting': 'ORTHOGONAL',
    },
    children: (kids.get(null) ?? []).map(build),
    edges: graph.edges.map((e) => ({ id: e.id, sources: [e.from], targets: [e.to] })),
  }
}

/** Positions from ELK's result: relative to the parent box, as React Flow wants them. */
export function positions(root: ElkNode, folded: Set<string>): Positioned[] {
  const out: Positioned[] = []
  const walk = (n: ElkNode, parent: string | null) => {
    for (const c of n.children ?? []) {
      const container = Boolean(c.children?.length)
      out.push({
        id: c.id,
        x: c.x ?? 0,
        y: c.y ?? 0,
        width: c.width ?? 0,
        height: c.height ?? 0,
        parent,
        container,
        folded: folded.has(c.id),
      })
      walk(c, c.id)
    }
  }
  walk(root, null)
  return out
}
