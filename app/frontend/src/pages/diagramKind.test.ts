import { expect, it } from 'vitest'
import { diagramKind } from './diagramKind'

it('reads the kind from the first keyword, past frontmatter and comments', () => {
  expect(diagramKind('---\nconfig:\n  layout: elk\n---\nflowchart LR\n  A --> B')).toBe('flowchart')
  expect(diagramKind('graph TD\n A-->B')).toBe('flowchart')
  expect(diagramKind('%% a note\nsequenceDiagram\n A->>B: hi')).toBe('sequence')
  expect(diagramKind('erDiagram')).toBe('er')
  expect(diagramKind('stateDiagram-v2\n [*] --> a')).toBe('state')
  expect(diagramKind('architecture-beta\n group g')).toBe('architecture')
  expect(diagramKind('pie\n "a": 1')).toBe('other')
})
