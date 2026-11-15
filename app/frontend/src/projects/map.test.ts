import { describe, expect, it } from 'vitest'
import type { Project, Registry } from '../api/types'
import { buildMermaid, selectProjects } from './map'

function project(id: string, extra: Partial<Project> = {}): Project {
  return {
    id,
    title: id,
    page: `system/projects/${id}.md`,
    path: `../${id}`,
    parent: null,
    group: null,
    status: 'active',
    kind: null,
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
    project('web', { group: 'example-system', depends_on: ['bff'] }),
    project('bff', { group: 'example-system', depends_on: ['cdc'], used_by: ['web'] }),
    project('cdc', { children: ['example-collector'], used_by: ['bff'] }),
    project('example-collector', { parent: 'cdc', title: 'example-shop "tei"' }),
    project('notes', { status: 'archived' }),
  ],
  groups: [{ id: 'example-system', title: 'example-system', page: 'system/groups/example-system.md', summary: '', projects: ['web', 'bff'] }],
  warnings: [],
  unregistered: [],
}

describe('buildMermaid', () => {
  it('maps everything: groups as subgraphs, sub-projects nested, deps as arrows', () => {
    const m = buildMermaid(registry)
    expect(m.startsWith('flowchart LR')).toBe(true)
    expect(m).toContain('subgraph g_example-system["example-system"]')
    expect(m).toContain('subgraph p_cdc_box["cdc"]')
    expect(m).toContain('p_example-collector["example-shop  tei"]') // quotes stripped from labels
    expect(m).toContain('p_web --> p_bff')
    expect(m).toContain('p_bff --> p_cdc')
    expect(m).toContain('class p_notes inactive')
    expect(m).not.toContain('ghost')
  })

  it('maps one group, with outside dependencies dashed', () => {
    const m = buildMermaid(registry, { group: 'example-system' })
    expect(m).not.toContain('subgraph g_example-system')
    expect(m).toContain('p_bff --> p_cdc')
    expect(m).toContain('class p_cdc ghost')
    expect(m).not.toContain('p_notes')
  })

  it('focuses one project with its family and direct links', () => {
    const { shown, ghosts } = selectProjects(registry, { focus: 'cdc' })
    expect([...shown].sort()).toEqual(['cdc', 'example-collector'])
    expect([...ghosts]).toEqual(['bff'])
    expect(buildMermaid(registry, { focus: 'cdc' })).toContain('p_bff --> p_cdc')
  })

  it('returns nothing for an empty registry', () => {
    expect(buildMermaid({ projects: [], groups: [], warnings: [], unregistered: [] })).toBe('')
  })
})
