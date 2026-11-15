import { describe, expect, it } from 'vitest'
import type { Project, Registry } from '../api/types'
import { buildMermaid, selectProjects } from './map'

function project(id: string, extra: Partial<Project> = {}): Project {
  return {
    id,
    title: id,
    page: `projects/${id}.md`,
    path: `../${id}`,
    root: null,
    parent: null,
    group: null,
    status: 'active',
    kind: null,
    type: 'project',
    type_source: 'detected',
    detected_type: 'project',
    owner: null,
    inbox_edits: true,
    inbox_edits_source: 'default',
    ports: [],
    depends_on: [],
    docs_dir: 'docs',
    verified: null,
    summary: '',
    available: true,
    children: [],
    used_by: [],
    ...extra,
  }
}

const registry: Registry = {
  projects: [
    project('web', { group: 'shop', depends_on: ['bff'] }),
    project('bff', { group: 'shop', depends_on: ['datasvc'], used_by: ['web'] }),
    project('datasvc', { children: ['collector-a'], used_by: ['bff'] }),
    project('collector-a', { parent: 'datasvc', title: 'coll "tei"' }),
    project('notes', { status: 'archived' }),
  ],
  groups: [{ id: 'shop', title: 'Shop', page: 'groups/shop.md', summary: '', projects: ['web', 'bff'] }],
  warnings: [],
  unregistered: [],
}

describe('buildMermaid', () => {
  it('maps everything: groups as subgraphs, sub-projects nested, deps as arrows', () => {
    const m = buildMermaid(registry)
    expect(m.startsWith('---\nconfig:\n  layout: elk\n---\nflowchart LR\n')).toBe(true)
    expect(m).toContain('subgraph g_shop["Shop"]')
    expect(m).toContain('subgraph p_datasvc_box["datasvc"]')
    expect(m).toContain('p_collector_a["coll  tei"]') // quotes stripped from labels
    expect(m).toContain('p_web --> p_bff')
    expect(m).toContain('p_bff --> p_datasvc')
    expect(m).toContain('class p_notes inactive')
    expect(m).not.toContain('ghost')
  })

  it('maps one group, with outside dependencies dashed', () => {
    const m = buildMermaid(registry, { group: 'shop' })
    expect(m).not.toContain('subgraph g_shop')
    expect(m).toContain('p_bff --> p_datasvc')
    expect(m).toContain('class p_datasvc ghost')
    expect(m).not.toContain('p_notes')
  })

  it('focuses one project with its family and direct links', () => {
    const { shown, ghosts } = selectProjects(registry, { focus: 'datasvc' })
    expect([...shown].sort()).toEqual(['collector-a', 'datasvc'])
    expect([...ghosts]).toEqual(['bff'])
    expect(buildMermaid(registry, { focus: 'datasvc' })).toContain('p_bff --> p_datasvc')
  })

  it('returns nothing for an empty registry', () => {
    expect(buildMermaid({ projects: [], groups: [], warnings: [], unregistered: [] })).toBe('')
  })
})
