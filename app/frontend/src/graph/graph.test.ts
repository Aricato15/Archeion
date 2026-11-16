import { describe, expect, it } from 'vitest'
import { fold, type Graph, leafSize, neighbours, parents, positions, toElk } from './graph'

const graph: Graph = {
  nodes: [
    { id: 'sys', label: 'System' },
    { id: 'api', label: 'API', parent: 'sys' },
    { id: 'routes', label: 'routes', parent: 'api' },
    { id: 'store', label: 'store', parent: 'api' },
    { id: 'db', label: 'db', parent: 'sys', shape: 'store' },
    { id: 'ext', label: 'outside' },
  ],
  edges: [
    { id: 'e1', from: 'routes', to: 'store', label: 'load' },
    { id: 'e2', from: 'store', to: 'db', label: 'SELECT', style: 'thick' },
    { id: 'e3', from: 'routes', to: 'db', label: 'UPDATE', style: 'thick' },
    { id: 'e4', from: 'routes', to: 'ext', style: 'dashed' },
    { id: 'e5', from: 'api', to: 'routes' },
  ],
}

describe('fold', () => {
  it('keeps everything when nothing is folded, minus edges into a box from inside it', () => {
    const { graph: g, containers } = fold(graph, new Set())
    expect(g.nodes).toHaveLength(6)
    expect([...containers].sort()).toEqual(['api', 'sys'])
    expect(g.edges.map((e) => e.label)).toEqual(['load', 'SELECT', 'UPDATE', undefined])
  })

  it('moves edges to the folded box and merges the ones that land together', () => {
    const { graph: g, containers } = fold(graph, new Set(['api']))
    expect(g.nodes.map((n) => n.id)).toEqual(['sys', 'api', 'db', 'ext'])
    expect(containers.has('api')).toBe(true) // still foldable: it can be unfolded again
    const toDb = g.edges.find((e) => e.from === 'api' && e.to === 'db')!
    expect(toDb.label).toBe('SELECT, UPDATE')
    expect(g.edges.find((e) => e.to === 'ext')!.from).toBe('api')
    expect(g.edges.some((e) => e.from === e.to)).toBe(false)
  })

  it('hides everything inside a folded outer box', () => {
    const { graph: g } = fold(graph, new Set(['sys']))
    expect(g.nodes.map((n) => n.id)).toEqual(['sys', 'ext'])
    expect(g.edges).toEqual([expect.objectContaining({ from: 'sys', to: 'ext', style: 'dashed' })])
  })
})

describe('parents', () => {
  it('ignores missing parents and breaks cycles', () => {
    const p = parents([
      { id: 'a', label: 'a', parent: 'b' },
      { id: 'b', label: 'b', parent: 'a' },
      { id: 'c', label: 'c', parent: 'nowhere' },
    ])
    expect(p.get('a')).toBeNull()
    expect(p.get('b')).toBeNull()
    expect(p.get('c')).toBeNull()
  })
})

describe('elk', () => {
  it('nests containers and sizes leaves from their text', () => {
    const { graph: g, containers } = fold(graph, new Set())
    const root = toElk(g, containers, 'RIGHT')
    expect(root.children!.map((c) => c.id)).toEqual(['sys', 'ext'])
    const sys = root.children![0]
    expect(sys.children!.map((c) => c.id)).toEqual(['api', 'db'])
    expect(sys.width).toBeUndefined()
    expect(root.edges).toHaveLength(4)
    expect(leafSize({ id: 'x', label: 'x' }).width).toBe(120)
    expect(leafSize({ id: 'x', label: 'x'.repeat(200) }).width).toBe(280)
    expect(leafSize({ id: 'x', label: 'x', sublabel: 'y' }).height).toBeGreaterThan(leafSize({ id: 'x', label: 'x' }).height)
  })

  it('reads positions back relative to their parent', () => {
    const laid = {
      id: '__root__',
      children: [
        { id: 'sys', x: 10, y: 20, width: 300, height: 200, children: [{ id: 'db', x: 5, y: 40, width: 120, height: 46 }] },
        { id: 'ext', x: 400, y: 0, width: 120, height: 46 },
      ],
    }
    expect(positions(laid, new Set(['ext']))).toEqual([
      { id: 'sys', x: 10, y: 20, width: 300, height: 200, parent: null, container: true, folded: false },
      { id: 'db', x: 5, y: 40, width: 120, height: 46, parent: 'sys', container: false, folded: false },
      { id: 'ext', x: 400, y: 0, width: 120, height: 46, parent: null, container: false, folded: true },
    ])
  })
})

it('neighbours are the nodes one edge away', () => {
  expect([...neighbours(graph, 'store')].sort()).toEqual(['db', 'routes', 'store'])
})
