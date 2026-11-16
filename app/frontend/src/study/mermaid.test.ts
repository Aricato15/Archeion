import { describe, expect, it } from 'vitest'
import { normalizeModel, type StudyModel } from '../api/study'
import { activity, componentMap, erDiagram, label, sequence, stateDiagram } from './mermaid'

const model = normalizeModel({
  schema: 1,
  meta: { project: 'example', date: '2026-11-16', commit: 'abcdef1' },
  components: [
    { id: 'api', name: 'API "server"', kind: 'service', tech: 'FastAPI' },
    { id: 'api.routes', name: 'routes', kind: 'module', parent: 'api' },
    { id: 'api.store', name: 'store', kind: 'module', parent: 'api' },
    { id: 'api.store.q', name: 'queries', kind: 'function', parent: 'api.store' },
    { id: 'db', name: 'app.db', kind: 'database' },
    { id: 'other', name: 'other', kind: 'external' },
  ],
  relations: [
    { id: 'r1', from: 'api.routes', to: 'api.store.q', kind: 'calls', label: 'load' },
    { id: 'r2', from: 'api.store.q', to: 'db', kind: 'sql', label: 'SELECT' },
    { id: 'r3', from: 'api.routes', to: 'other', kind: 'http', label: 'POST /x' },
    { id: 'r4', from: 'api.routes', to: 'api.store', kind: 'imports' },
  ],
}) as StudyModel

describe('componentMap', () => {
  it('nests children in their parent and draws relations between what is shown', () => {
    const code = componentMap(model, { depth: 1 })
    expect(code).toContain('layout: elk')
    expect(code).toMatch(/subgraph c0\["API #quot;server#quot;"\]/)
    // depth 1: queries isn't drawn, so its relations attach to its parent, store.
    expect(code).not.toContain('queries')
    expect(code).toMatch(/c\d+\[\("app.db<br\/>database"\)\]/)
    expect(code).toMatch(/c\d+ ==>\|"SELECT"\| c\d+/)
    expect(code).toMatch(/c\d+ -.->\|"POST \/x"\| c\d+/)
  })

  it('hides relation kinds and focuses on one component with ghosts outside', () => {
    expect(componentMap(model, { hideKinds: ['imports', 'calls'] })).not.toContain('load')
    const focused = componentMap(model, { focus: 'api' })
    expect(focused).toContain('routes')
    expect(focused).toContain('class')
    expect(focused).toMatch(/\("app.db"\)/) // the database is outside the focus: a ghost
    expect(componentMap(normalizeModel({ ...model, components: [] })!)).toBe('')
  })
})

describe('sequence', () => {
  it('writes messages, replies, notes and nested blocks', () => {
    const code = sequence(
      {
        id: 'f',
        title: 'Read',
        participants: ['api.routes', 'db'],
        steps: [
          { from: 'api.routes', to: 'db', label: 'SELECT a; b' },
          {
            block: 'alt',
            label: 'found',
            steps: [{ from: 'db', to: 'api.routes', label: 'row', reply: true }],
            others: [{ label: 'missing', steps: [{ note: '404: none', over: ['api.routes'] }] }],
          },
          { block: 'loop', label: 'each', steps: [{ from: 'api.routes', to: 'db', async: true }] },
        ],
      },
      model.components,
    )
    expect(code.split('\n')).toEqual([
      'sequenceDiagram',
      '  participant p0 as routes',
      '  participant p1 as app.db',
      '  p0->>p1: SELECT a#59; b',
      '  alt found',
      '    p1-->>p0: row',
      '  else missing',
      '    Note over p0: 404#58; none',
      '  end',
      '  loop each',
      '    p0-)p1:  ',
      '  end',
    ])
  })
})

describe('activity, erDiagram and stateDiagram', () => {
  it('draws an activity with start, decision and end', () => {
    const code = activity({
      id: 'a',
      title: 'Sync',
      nodes: [
        { id: 's', kind: 'start' },
        { id: 'd', kind: 'decision', label: 'more?' },
        { id: 'e', kind: 'end' },
      ],
      edges: [
        { from: 's', to: 'd' },
        { from: 'd', to: 'e', label: 'no' },
      ],
    })
    expect(code).toContain('a0(("Start"))')
    expect(code).toContain('a1{"more?"}')
    expect(code).toContain('a2((("End")))')
    expect(code).toContain('a1 -->|"no"| a2')
  })

  it('draws entities with keys and foreign keys', () => {
    const code = erDiagram([
      { id: 'owners', name: 'owners', fields: [{ name: 'id', type: 'INTEGER', pk: true }] },
      {
        id: 'items',
        name: 'item list',
        fields: [{ name: 'owner_id', type: 'INTEGER', fk: 'owners.id', nullable: true }, { name: 'x' }],
      },
    ])
    expect(code).toContain('INTEGER id PK')
    expect(code).toContain('item_list {')
    expect(code).toContain('INTEGER owner_id FK')
    expect(code).toContain('any x')
    expect(code).toContain('owners |o--o{ item_list : "owner_id"')
    expect(erDiagram([])).toBe('')
  })

  it('draws a state machine', () => {
    const code = stateDiagram({
      id: 'm',
      title: 'Order',
      states: [{ id: 'new' }, { id: 'paid', label: 'Paid: ok' }],
      initial: 'new',
      final: ['paid'],
      transitions: [{ from: 'new', to: 'paid', label: 'pay' }],
    })
    expect(code.split('\n')).toEqual([
      'stateDiagram-v2',
      '  s0 : new',
      '  s1 : Paid#58; ok',
      '  [*] --> s0',
      '  s0 --> s1 : pay',
      '  s1 --> [*]',
    ])
  })

  it('escapes labels', () => {
    expect(label('a "b" <c>\nd')).toBe('a #quot;b#quot; #lt;c#gt; d')
  })
})
