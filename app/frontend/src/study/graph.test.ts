import { describe, expect, it } from 'vitest'
import { normalizeModel, type StudyModel } from '../api/study'
import { componentGraph, foldedAtDepth } from './graph'

const model = normalizeModel({
  schema: 1,
  meta: { project: 'example', date: '2026-11-16', commit: 'abcdef1' },
  components: [
    { id: 'api', name: 'API', kind: 'service' },
    { id: 'api.routes', name: 'routes', kind: 'module', parent: 'api' },
    { id: 'api.store', name: 'store', kind: 'module', parent: 'api' },
    { id: 'api.store.q', name: 'queries', kind: 'function', parent: 'api.store' },
    { id: 'web', name: 'web', kind: 'ui' },
    { id: 'web.client', name: 'client', kind: 'module', parent: 'web' },
    { id: 'db', name: 'app.db', kind: 'database' },
  ],
  relations: [
    { id: 'r1', from: 'api.routes', to: 'api.store.q', kind: 'calls' },
    { id: 'r2', from: 'api.store.q', to: 'db', kind: 'sql', label: 'SELECT' },
    { id: 'r3', from: 'web.client', to: 'api.routes', kind: 'http', label: 'GET /items' },
    { id: 'r4', from: 'api.routes', to: 'api.store', kind: 'imports' },
  ],
}) as StudyModel

describe('componentGraph', () => {
  it('draws every component, nested, with styled relations', () => {
    const g = componentGraph(model)
    expect(g.nodes).toHaveLength(7)
    expect(g.nodes.find((n) => n.id === 'db')).toMatchObject({ shape: 'store', tone: 'orange', parent: null })
    expect(g.nodes.find((n) => n.id === 'api.store.q')!.parent).toBe('api.store')
    expect(g.edges.find((e) => e.id === 'r2')).toMatchObject({ style: 'thick', label: 'SELECT' })
    expect(g.edges.find((e) => e.id === 'r3')!.style).toBe('dashed')
    expect(componentGraph(model, { hideKinds: ['imports'] }).edges.some((e) => e.id === 'r4')).toBe(false)
  })

  it('focuses on one component and shows what it links to outside as ghosts', () => {
    const g = componentGraph(model, { focus: 'api' })
    const ids = g.nodes.map((n) => n.id).sort()
    // web.client's caller is drawn as its outermost box, web; the database as itself.
    expect(ids).toEqual(['api.routes', 'api.store', 'api.store.q', 'db', 'web'])
    expect(g.nodes.find((n) => n.id === 'web')).toMatchObject({ ghost: true, parent: null })
    expect(g.nodes.find((n) => n.id === 'api.routes')!.parent).toBeNull() // the focus itself isn't drawn
    expect(g.edges.find((e) => e.id === 'r3')).toMatchObject({ from: 'web', to: 'api.routes' })
  })

  it('starts folded below the chosen depth', () => {
    const g = componentGraph(model)
    expect(foldedAtDepth(g, 0).sort()).toEqual(['api', 'api.store', 'web'])
    expect(foldedAtDepth(g, 1)).toEqual(['api.store'])
    expect(foldedAtDepth(g, 2)).toEqual([])
  })
})
