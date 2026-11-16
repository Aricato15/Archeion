import { describe, expect, it } from 'vitest'
import type { Project, Registry } from '../api/types'
import { buildGraph, buildMermaid, selectProjects } from './map'

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

describe('buildGraph', () => {
  it('nests projects in groups and parents, with dependencies as arrows', () => {
    const g = buildGraph(registry)
    expect(g.nodes[0]).toMatchObject({ id: 'group:shop', label: 'Shop' })
    expect(g.nodes.find((n) => n.id === 'web')!.parent).toBe('group:shop')
    expect(g.nodes.find((n) => n.id === 'collector-a')!.parent).toBe('datasvc')
    expect(g.nodes.find((n) => n.id === 'notes')).toMatchObject({ dimmed: true, sublabel: 'archived' })
    expect(g.edges.map((e) => `${e.from}>${e.to}`).sort()).toEqual(['bff>datasvc', 'web>bff'])
  })

  it('focuses one project, with its links as ghosts and no group boxes', () => {
    const g = buildGraph(registry, { focus: 'datasvc' })
    expect(g.nodes.map((n) => n.id).sort()).toEqual(['bff', 'collector-a', 'datasvc'])
    expect(g.nodes.find((n) => n.id === 'bff')).toMatchObject({ ghost: true, parent: null })
    expect(g.nodes.find((n) => n.id === 'datasvc')!.tone).toBe('blue')
  })

  it('labels arrows with the calls found in the code, and marks drift', () => {
    const call = (id: string, path: string) => ({ id, kind: 'http', method: 'GET', path, resolved_by: 'port' as const, exposed: null, target_studied: true })
    const g = buildGraph(registry, {}, {
      links: [
        { from: 'bff', to: 'datasvc', calls: [call('c1', '/items')] },
        { from: 'web', to: 'datasvc', calls: [call('c2', '/a'), call('c3', '/b'), call('c4', '/c')] },
      ],
      unresolved: [],
      drift: [],
      studied: ['bff', 'web'],
    })
    const edge = (id: string) => g.edges.find((e) => e.id === id)!
    expect(edge('dep:bff>datasvc')).toMatchObject({ label: 'GET /items', tone: 'blue' })
    expect(edge('dep:web>bff')).toMatchObject({ label: 'not seen in code', style: 'dotted' })
    expect(edge('code:web>datasvc')).toMatchObject({ style: 'dashed', tone: 'orange', label: 'in code only: GET /a, GET /b +1' })
  })
})