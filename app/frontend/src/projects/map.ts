import type { Group, Project, Registry } from '../api/types'

/**
 * Mermaid flowcharts generated from the registry, so the maps can't drift from the pages:
 * groups become subgraphs, sub-projects nest inside their parent, and depends_on becomes an
 * arrow. Projects outside the shown set that are linked to appear dashed.
 */

const nodeId = (id: string) => `p_${id.replace(/[^A-Za-z0-9_]/g, '_')}`
const groupId = (id: string) => `g_${id.replace(/[^A-Za-z0-9_]/g, '_')}`
// Mermaid labels: quotes and brackets would end the label early.
const label = (text: string) => text.replace(/["[\]{}<>]/g, ' ').trim() || '?'

export type MapOptions = {
  /** Only this group's projects (plus dashed neighbours they link to). */
  group?: string
  /** One project, its parent, children and direct links. */
  focus?: string
  direction?: 'LR' | 'TB'
}

function topGroup(reg: Map<string, Project>, p: Project): string | null {
  let cur: Project | undefined = p
  while (cur) {
    if (cur.group) return cur.group
    cur = cur.parent ? reg.get(cur.parent) : undefined
  }
  return null
}

export function selectProjects(registry: Registry, opts: MapOptions): { shown: Set<string>; ghosts: Set<string> } {
  const byId = new Map(registry.projects.map((p) => [p.id, p]))
  let shown: Set<string>
  if (opts.focus) {
    const p = byId.get(opts.focus)
    shown = new Set(p ? [p.id, ...(p.parent ? [p.parent] : []), ...p.children] : [])
  } else if (opts.group) {
    shown = new Set(registry.projects.filter((p) => topGroup(byId, p) === opts.group).map((p) => p.id))
  } else {
    shown = new Set(byId.keys())
  }
  const ghosts = new Set<string>()
  for (const p of registry.projects) {
    if (shown.has(p.id)) for (const d of p.depends_on) if (!shown.has(d)) ghosts.add(d)
    if (!shown.has(p.id) && p.depends_on.some((d) => shown.has(d)) && (opts.focus || opts.group)) ghosts.add(p.id)
  }
  if (opts.focus) {
    const p = byId.get(opts.focus)
    for (const d of p?.depends_on ?? []) ghosts.add(d)
    for (const u of p?.used_by ?? []) ghosts.add(u)
    for (const s of shown) ghosts.delete(s)
  }
  return { shown, ghosts }
}

export function buildMermaid(registry: Registry, opts: MapOptions = {}): string {
  const byId = new Map(registry.projects.map((p) => [p.id, p]))
  const groups = new Map<string, Group>(registry.groups.map((g) => [g.id, g]))
  const { shown, ghosts } = selectProjects(registry, opts)
  const lines = [`flowchart ${opts.direction ?? 'LR'}`]
  const visible = new Set([...shown, ...ghosts])
  if (visible.size === 0) return ''

  const childrenOf = (id: string) => [...visible].filter((c) => byId.get(c)?.parent === id).sort()
  const roots = [...visible].filter((id) => {
    const parent = byId.get(id)?.parent
    return !parent || !visible.has(parent)
  })

  const emit = (id: string, indent: string) => {
    const p = byId.get(id)
    const title = label(p?.title ?? id)
    const kids = childrenOf(id)
    if (kids.length) {
      lines.push(`${indent}subgraph ${nodeId(id)}_box["${title}"]`)
      lines.push(`${indent}  ${nodeId(id)}["${title}"]`)
      for (const k of kids) emit(k, `${indent}  `)
      lines.push(`${indent}end`)
    } else {
      lines.push(`${indent}${nodeId(id)}["${title}"]`)
    }
  }

  const byGroup = new Map<string | null, string[]>()
  for (const id of roots.sort()) {
    const p = byId.get(id)
    const g = p ? topGroup(byId, p) : null
    byGroup.set(g, [...(byGroup.get(g) ?? []), id])
  }
  for (const [g, ids] of [...byGroup.entries()].sort(([a], [b]) => (a ?? '~').localeCompare(b ?? '~'))) {
    if (g && !opts.group) {
      lines.push(`  subgraph ${groupId(g)}["${label(groups.get(g)?.title ?? g)}"]`)
      for (const id of ids) emit(id, '    ')
      lines.push('  end')
    } else {
      for (const id of ids) emit(id, '  ')
    }
  }

  for (const p of registry.projects) {
    if (!visible.has(p.id)) continue
    for (const d of p.depends_on) if (visible.has(d)) lines.push(`  ${nodeId(p.id)} --> ${nodeId(d)}`)
  }

  // No 'click' links: Mermaid runs with securityLevel 'strict', which disables them.
  // The project cards under each map do the navigation.
  if (ghosts.size) {
    lines.push('  classDef ghost stroke-dasharray: 4 3,opacity:0.7')
    lines.push(`  class ${[...ghosts].map(nodeId).join(',')} ghost`)
  }
  const inactive = [...visible].filter((id) => {
    const s = byId.get(id)?.status
    return s === 'paused' || s === 'archived'
  })
  if (inactive.length) {
    lines.push('  classDef inactive fill:#8881,color:#888')
    lines.push(`  class ${inactive.map(nodeId).join(',')} inactive`)
  }
  return lines.join('\n')
}
