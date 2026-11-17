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

let ctx: CanvasRenderingContext2D | null | undefined

/** Width of `text` in the page's font, measured on a canvas. Falls back to a per-character guess
 *  where there's no canvas (tests) so the layout still works. */
export function textWidth(text: string, size = 14, weight = 500): number {
  if (ctx === undefined) {
    try {
      ctx = typeof document === 'undefined' ? null : document.createElement('canvas').getContext('2d')
    } catch {
      ctx = null
    }
  }
  if (!ctx) return text.length * CHAR_WIDTH * (size / 14)
  const family = typeof getComputedStyle === 'function' ? getComputedStyle(document.body).fontFamily : 'sans-serif'
  ctx.font = `${weight} ${size}px ${family || 'sans-serif'}`
  return ctx.measureText(text).width
}

/** Width and height of a leaf box, from its text. */
export function leafSize(n: GraphNode): { width: number; height: number } {
  const text = Math.max(textWidth(n.label, 14, 500), n.sublabel ? textWidth(n.sublabel, 12, 400) : 0)
  return {
    width: Math.round(Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, text + 40))),
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

export type Point = { x: number; y: number }
export type ElkLabel = { text: string; width?: number; height?: number; x?: number; y?: number }
export type ElkEdge = {
  id: string
  sources: string[]
  targets: string[]
  labels?: ElkLabel[]
  sections?: { startPoint: Point; endPoint: Point; bendPoints?: Point[] }[]
}

/** Above this many edges, labels are drawn only for the hovered box, and take no room in the layout. */
export const LABEL_LIMIT = 40
/** Above this many edges, lines are faint until a box is hovered. */
export const DENSE_LIMIT = 60

export type ElkNode = {
  id: string
  width?: number
  height?: number
  x?: number
  y?: number
  children?: ElkNode[]
  edges?: ElkEdge[]
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
      'org.eclipse.elk.json.edgeCoords': 'ROOT',
      'elk.spacing.edgeNode': '18',
      'elk.spacing.edgeEdge': '12',
      'elk.layered.spacing.edgeNodeBetweenLayers': '22',
      'elk.layered.spacing.edgeEdgeBetweenLayers': '14',
    },
    children: (kids.get(null) ?? []).map(build),
    edges: graph.edges.map((e) => ({
      id: e.id,
      sources: [e.from],
      targets: [e.to],
      // Labels get room in the layout, so they don't land on boxes. Many edges: none, to stay readable.
      labels:
        e.label && graph.edges.length <= LABEL_LIMIT
          ? [{ text: e.label, width: Math.round(textWidth(e.label, 11, 400)) + 10, height: 16 }]
          : undefined,
    })),
  }
}

export type Route = { points: Point[]; label?: { x: number; y: number } }

/** The edges as ELK routed them, in absolute coordinates (every box's position is relative to its
 *  container, but `edgeCoords: ROOT` gives the lines absolute ones). */
export function routes(root: ElkNode): Map<string, Route> {
  const out = new Map<string, Route>()
  const walk = (n: ElkNode) => {
    for (const e of n.edges ?? []) {
      const sec = e.sections?.[0]
      if (!sec) continue
      const l = e.labels?.[0]
      out.set(e.id, {
        points: [sec.startPoint, ...(sec.bendPoints ?? []), sec.endPoint],
        label: l && l.x !== undefined && l.y !== undefined ? { x: l.x + (l.width ?? 0) / 2, y: l.y + (l.height ?? 0) / 2 } : undefined,
      })
    }
    n.children?.forEach(walk)
  }
  walk(root)
  return out
}

/** A polyline as an SVG path with rounded corners. */
export function roundedPath(points: Point[], radius = 8): string {
  if (points.length < 2) return ''
  let d = `M ${points[0].x} ${points[0].y}`
  for (let i = 1; i < points.length - 1; i++) {
    const prev = points[i - 1]
    const cur = points[i]
    const next = points[i + 1]
    const a = Math.hypot(cur.x - prev.x, cur.y - prev.y)
    const b = Math.hypot(next.x - cur.x, next.y - cur.y)
    const r = Math.min(radius, a / 2, b / 2)
    if (r < 1) {
      d += ` L ${cur.x} ${cur.y}`
      continue
    }
    const p1 = { x: cur.x + ((prev.x - cur.x) / a) * r, y: cur.y + ((prev.y - cur.y) / a) * r }
    const p2 = { x: cur.x + ((next.x - cur.x) / b) * r, y: cur.y + ((next.y - cur.y) / b) * r }
    d += ` L ${p1.x} ${p1.y} Q ${cur.x} ${cur.y} ${p2.x} ${p2.y}`
  }
  const last = points[points.length - 1]
  return `${d} L ${last.x} ${last.y}`
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
