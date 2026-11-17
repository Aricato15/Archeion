import { describe, expect, it } from 'vitest'
import type { StudyFlow } from '../api/study'
import { involves, layoutFlow, wrapName } from './sequence'

const components = [
  { id: 'api', name: 'API', kind: 'service' },
  { id: 'db', name: 'app.db', kind: 'database' },
] as never

const flow = {
  id: 'f',
  title: 'Read',
  participants: ['api', 'db'],
  steps: [
    { from: 'api', to: 'db', label: 'SELECT' },
    {
      block: 'alt',
      label: 'found',
      steps: [{ from: 'db', to: 'api', label: 'rows', reply: true }],
      others: [{ label: 'missing', steps: [{ note: 'nothing', over: ['api'] }] }],
    },
    { from: 'api', to: 'cache', label: 'unlisted participant' },
  ],
} as unknown as StudyFlow

describe('layoutFlow', () => {
  const l = layoutFlow(flow, components)
  it('keeps steps in order, top to bottom, and adds a lane for an unlisted participant', () => {
    const ys = l.items.filter((i) => i.kind !== 'block').map((i) => i.y)
    expect([...ys].sort((a, b) => a - b)).toEqual(ys)
    expect(l.lanes.map((x) => x.id)).toEqual(['api', 'db', 'cache'])
    expect(l.width).toBeGreaterThan(l.lanes[2].x)
  })
  it('wraps a block around the lanes its steps touch, with a divider for the other branch', () => {
    const b = l.items.find((i) => i.kind === 'block')!
    expect(b.kind === 'block' && b.dividers).toHaveLength(1)
    expect(b.kind === 'block' && [b.from, b.to]).toEqual([0, 1])
  })
  it('says which lanes a step involves', () => {
    const m = l.items.find((i) => i.kind === 'msg')!
    expect([...involves(m, l.lanes)].sort()).toEqual(['api', 'db'])
  })
})

it('wraps long names over a few short lines', () => {
  expect(wrapName('files (store/trash/restore/purge)').length).toBeGreaterThan(1)
  expect(wrapName('x'.repeat(100)).length).toBe(1)
})
