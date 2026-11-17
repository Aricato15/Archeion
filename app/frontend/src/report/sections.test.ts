import { describe, expect, it } from 'vitest'
import type { ReportContent } from '../api/reports'
import { normalizeModel, type StudyModel } from '../api/study'
import { diagramCode, heading, pageCss } from './sections'

const model = normalizeModel({
  schema: 1,
  meta: { project: 'example', date: '2026-11-16', commit: 'abcdef1' },
  components: [
    { id: 'api', name: 'API', kind: 'service' },
    { id: 'api.routes', name: 'routes', kind: 'module', parent: 'api' },
    { id: 'api.store', name: 'store', kind: 'module', parent: 'api' },
    { id: 'db', name: 'app.db', kind: 'database' },
  ],
  relations: [{ id: 'r1', from: 'api.routes', to: 'db', kind: 'sql', label: 'SELECT' }],
  entities: [{ id: 'items', name: 'items', fields: [{ name: 'id', type: 'int', pk: true }] }],
  flows: [
    {
      id: 'read',
      title: 'Read',
      participants: ['api.routes', 'db'],
      steps: [{ from: 'api.routes', to: 'db', label: 'SELECT' }],
    },
  ],
  activities: [{ id: 'act', title: 'Act', nodes: [{ id: 'a', kind: 'start' }], edges: [] }],
  states: [{ id: 'st', title: 'St', states: [{ id: 'new' }], transitions: [] }],
}) as StudyModel

const study: ReportContent['study'] = { id: '2026-11-16-abcdef1', date: '2026-11-16', commit: 'abcdef1', model }

const diagram = (extra: Record<string, unknown>) =>
  ({ id: 'x', title: 'X', type: 'diagram', ...extra }) as Parameters<typeof diagramCode>[0]

describe('diagramCode', () => {
  it('draws the compact map as the top level only', () => {
    const code = diagramCode(diagram({ diagram: 'map', focus: null }), study, undefined)!
    expect(code).toContain('flowchart LR')
    expect(code).toContain('API')
    expect(code).not.toContain('routes') // a child of the API: it has a diagram of its own
  })

  it('draws a sub-system as the children of one component, with what they reach outside as ghosts', () => {
    const code = diagramCode(diagram({ diagram: 'map', focus: 'api' }), study, undefined)!
    expect(code).toContain('routes')
    expect(code).toContain('store')
    expect(code).toMatch(/\("app.db"\)/)
  })

  it('draws flows, logic, states and the schema from their ids', () => {
    expect(diagramCode(diagram({ diagram: 'flow', ref: 'read' }), study, undefined)).toContain('sequenceDiagram')
    expect(diagramCode(diagram({ diagram: 'activity', ref: 'act' }), study, undefined)).toContain('flowchart TD')
    expect(diagramCode(diagram({ diagram: 'state', ref: 'st' }), study, undefined)).toContain('stateDiagram')
    expect(diagramCode(diagram({ diagram: 'schema' }), study, undefined)).toContain('erDiagram')
  })

  it('returns null when the study no longer has what the section points at', () => {
    expect(diagramCode(diagram({ diagram: 'flow', ref: 'gone' }), study, undefined)).toBeNull()
    expect(diagramCode(diagram({ diagram: 'map', focus: null }), null, undefined)).toBeNull()
    expect(diagramCode(diagram({ diagram: 'group', group: 'g' }), study, undefined)).toBeNull()
  })
})

describe('page', () => {
  it('numbers headings in the chosen order', () => {
    expect(heading(0, { title: 'Overview' })).toBe('1. Overview')
  })

  it('sets the page size and orientation, with a safe default', () => {
    expect(pageCss({ page_size: 'Letter', orientation: 'landscape' })).toContain('size: Letter landscape')
    expect(pageCss({ page_size: 'x', orientation: 'y' })).toContain('size: A4 portrait')
  })
})
