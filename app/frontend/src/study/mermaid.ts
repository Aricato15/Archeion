import type {
  FlowStep,
  StudyActivity,
  StudyComponent,
  StudyEntity,
  StudyFlow,
  StudyModel,
  StudyStates,
} from '../api/study'

/**
 * Mermaid diagrams generated from a study's model (ADR 0019), so they can't drift from it:
 * the component map (nested by parent, arrows from relations), a sequence diagram per flow,
 * an activity diagram per activity, the ER diagram of the entities and a state diagram per
 * state machine. Element ids are mapped to safe Mermaid ids, and label text is escaped.
 */

/** Ids that Mermaid accepts, one per element id, stable within one diagram. */
class Ids {
  private map = new Map<string, string>()
  private prefix: string
  constructor(prefix: string) {
    this.prefix = prefix
  }
  get(id: string): string {
    let v = this.map.get(id)
    if (!v) {
      v = `${this.prefix}${this.map.size}`
      this.map.set(id, v)
    }
    return v
  }
}

/** Text inside a quoted flowchart label. */
export const label = (text: string | undefined | null) =>
  (text ?? '')
    .replace(/"/g, '#quot;')
    .replace(/</g, '#lt;')
    .replace(/>/g, '#gt;')
    .replace(/[\r\n]+/g, ' ')
    .trim()

/** Text after a colon in sequence and state diagrams, where ';' and '#' end or escape the line. */
const message = (text: string | undefined | null) =>
  (text ?? '')
    .replace(/#/g, '#35;')
    .replace(/;/g, '#59;')
    .replace(/:/g, '#58;')
    .replace(/[\r\n]+/g, ' ')
    .trim()

/** A bare word for ER names and types: letters, digits, _ and -. */
const word = (text: string | undefined | null, fallback: string) => {
  const w = (text ?? '').replace(/[^A-Za-z0-9_-]+/g, '_').replace(/^_+|_+$/g, '')
  return w && /^[A-Za-z_]/.test(w) ? w : w ? `_${w}` : fallback
}

const ELK = '---\nconfig:\n  layout: elk\n---\n'

// --- component map ------------------------------------------------------------------------

export type ComponentMapOptions = {
  /** Show this component's insides (its children, nested), plus what they connect to outside. */
  focus?: string | null
  /** How many levels of nesting to draw below the top (default 2). */
  depth?: number
  /** Leave out relations of these kinds (e.g. imports, which can crowd the map). */
  hideKinds?: string[]
}

function shape(c: StudyComponent, text: string, ghost: boolean): string {
  const t = `"${text}"`
  if (ghost) return `(${t})`
  switch (c.kind) {
    case 'database':
    case 'store':
      return `[(${t})]`
    case 'external':
      return `{{${t}}}`
    case 'library':
      return `[/${t}/]`
    case 'function':
    case 'class':
      return `([${t}])`
    case 'ui':
    case 'cli':
      return `[/${t}\\]`
    default:
      return `[${t}]`
  }
}

const ARROW: Record<string, string> = {
  imports: '-->',
  calls: '-->',
  http: '-.->',
  event: '-.->',
  sql: '==>',
  reads: '-->',
  writes: '==>',
}

export function componentMap(model: StudyModel, opts: ComponentMapOptions = {}): string {
  const byId = new Map(model.components.map((c) => [c.id, c]))
  if (byId.size === 0) return ''
  const depth = opts.depth ?? 2
  const children = new Map<string | null, StudyComponent[]>()
  for (const c of model.components) {
    const parent = c.parent && byId.has(c.parent) ? c.parent : null
    if (!children.has(parent)) children.set(parent, [])
    children.get(parent)!.push(c)
  }
  const focus = opts.focus && byId.has(opts.focus) ? opts.focus : null
  const top = children.get(focus) ?? []

  // Which components are drawn, and how deep below the top each one sits.
  const shown = new Map<string, number>()
  const walk = (c: StudyComponent, level: number) => {
    shown.set(c.id, level)
    if (level < depth) for (const k of children.get(c.id) ?? []) walk(k, level + 1)
  }
  for (const c of top) walk(c, 0)

  // A component's nearest ancestor that's drawn (itself if it is).
  const visible = (id: string): string | null => {
    let cur: string | undefined = id
    const seen = new Set<string>()
    while (cur && !seen.has(cur)) {
      if (shown.has(cur)) return cur
      seen.add(cur)
      cur = byId.get(cur)?.parent
    }
    return null
  }

  const ids = new Ids('c')
  const hide = new Set(opts.hideKinds ?? [])
  const edges = new Map<string, { from: string; to: string; kind: string; labels: Set<string> }>()
  const ghosts = new Set<string>()
  for (const r of model.relations) {
    if (hide.has(r.kind) || !byId.has(r.from) || !byId.has(r.to)) continue
    let a = visible(r.from)
    let b = visible(r.to)
    // In a focused map, the far end of a relation that leaves the focus is a dashed ghost.
    if (focus && a && !b && r.to !== focus) {
      b = r.to
      ghosts.add(b)
    } else if (focus && !a && b && r.from !== focus) {
      a = r.from
      ghosts.add(a)
    }
    if (!a || !b || a === b) continue
    const key = `${a}|${b}|${r.kind}`
    const e = edges.get(key) ?? { from: a, to: b, kind: r.kind, labels: new Set<string>() }
    if (r.label) e.labels.add(r.label)
    edges.set(key, e)
  }

  const lines: string[] = [`${ELK}flowchart LR`]
  const nodeText = (c: StudyComponent) => {
    const sub = [c.kind, c.tech].filter(Boolean).join(' · ')
    return `${label(c.name)}<br/>${label(sub)}`
  }
  const emit = (c: StudyComponent, indent: string) => {
    const kids = (children.get(c.id) ?? []).filter((k) => shown.has(k.id))
    if (kids.length > 0) {
      lines.push(`${indent}subgraph ${ids.get(c.id)}["${label(c.name)}"]`)
      for (const k of kids) emit(k, `${indent}  `)
      lines.push(`${indent}end`)
    } else {
      lines.push(`${indent}${ids.get(c.id)}${shape(c, nodeText(c), false)}`)
    }
  }
  for (const c of top) emit(c, '  ')
  for (const g of ghosts) {
    const c = byId.get(g)!
    lines.push(`  ${ids.get(g)}${shape(c, label(c.name), true)}`)
  }
  for (const e of edges.values()) {
    const text = [...e.labels].slice(0, 2).join(', ') + (e.labels.size > 2 ? ` +${e.labels.size - 2}` : '')
    const arrow = ARROW[e.kind] ?? '-->'
    lines.push(`  ${ids.get(e.from)} ${arrow}${text ? `|"${label(text)}"|` : ''} ${ids.get(e.to)}`)
  }
  if (ghosts.size) lines.push(`  classDef ghost stroke-dasharray: 4 3,opacity:0.7`)
  for (const g of ghosts) lines.push(`  class ${ids.get(g)} ghost`)
  return lines.join('\n')
}

// --- sequence ------------------------------------------------------------------------------

export function sequence(flow: StudyFlow, components: StudyComponent[]): string {
  const names = new Map(components.map((c) => [c.id, c.name]))
  const ids = new Ids('p')
  const lines = ['sequenceDiagram']
  for (const p of flow.participants) {
    lines.push(`  participant ${ids.get(p)} as ${message(names.get(p) ?? p)}`)
  }
  const emit = (steps: FlowStep[], indent: string) => {
    for (const s of steps) {
      if ('block' in s) {
        lines.push(`${indent}${s.block} ${message(s.label)}`.trimEnd())
        emit(s.steps, `${indent}  `)
        const joiner = s.block === 'par' ? 'and' : 'else'
        for (const other of s.block === 'alt' || s.block === 'par' ? (s.others ?? []) : []) {
          lines.push(`${indent}${joiner} ${message(other.label)}`.trimEnd())
          emit(other.steps, `${indent}  `)
        }
        lines.push(`${indent}end`)
      } else if ('note' in s) {
        lines.push(`${indent}Note over ${s.over.map((o) => ids.get(o)).join(',')}: ${message(s.note)}`)
      } else {
        const arrow = s.reply ? '-->>' : s.async ? '-)' : '->>'
        lines.push(`${indent}${ids.get(s.from)}${arrow}${ids.get(s.to)}: ${message(s.label) || ' '}`)
      }
    }
  }
  emit(flow.steps, '  ')
  return lines.join('\n')
}

// --- activity -------------------------------------------------------------------------------

export function activity(a: StudyActivity): string {
  const ids = new Ids('a')
  const lines = ['flowchart TD']
  for (const n of a.nodes) {
    const t = label(n.label || (n.kind === 'start' ? 'Start' : n.kind === 'end' ? 'End' : n.id))
    const shapeOf = {
      start: `(("${t}"))`,
      end: `((("${t}")))`,
      decision: `{"${t}"}`,
      action: `["${t}"]`,
    } as const
    lines.push(`  ${ids.get(n.id)}${shapeOf[n.kind ?? 'action']}`)
  }
  for (const e of a.edges) {
    lines.push(`  ${ids.get(e.from)} -->${e.label ? `|"${label(e.label)}"|` : ''} ${ids.get(e.to)}`)
  }
  return lines.join('\n')
}

// --- entities ---------------------------------------------------------------------------------

/** The name each entity has in the ER diagram (a bare word, unique), by entity id. */
export function erNames(entities: StudyEntity[]): Map<string, string> {
  const names = new Map<string, string>()
  const used = new Set<string>()
  for (const e of entities) {
    let n = word(e.name, 'entity')
    while (used.has(n)) n = `${n}_`
    used.add(n)
    names.set(e.id, n)
  }
  return names
}

export function erDiagram(entities: StudyEntity[]): string {
  if (entities.length === 0) return ''
  const names = erNames(entities)
  const lines = ['erDiagram']
  const rels: string[] = []
  for (const e of entities) {
    lines.push(`  ${names.get(e.id)} {`)
    for (const f of e.fields) {
      const keys = [f.pk ? 'PK' : '', f.fk ? 'FK' : ''].filter(Boolean).join(', ')
      lines.push(`    ${word(f.type, 'any')} ${word(f.name, 'field')}${keys ? ` ${keys}` : ''}`)
      if (f.fk) {
        const target = names.get(f.fk.split('.')[0])
        if (target) {
          const card = f.nullable ? '|o--o{' : '||--o{'
          rels.push(`  ${target} ${card} ${names.get(e.id)} : "${label(f.name)}"`)
        }
      }
    }
    lines.push('  }')
  }
  return [...lines, ...rels].join('\n')
}

// --- states -------------------------------------------------------------------------------------

export function stateDiagram(m: StudyStates): string {
  const ids = new Ids('s')
  const lines = ['stateDiagram-v2']
  for (const s of m.states) lines.push(`  ${ids.get(s.id)} : ${message(s.label || s.id)}`)
  if (m.initial) lines.push(`  [*] --> ${ids.get(m.initial)}`)
  for (const t of m.transitions) {
    lines.push(`  ${ids.get(t.from)} --> ${ids.get(t.to)}${t.label ? ` : ${message(t.label)}` : ''}`)
  }
  for (const f of m.final ?? []) lines.push(`  ${ids.get(f)} --> [*]`)
  return lines.join('\n')
}
