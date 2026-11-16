/** What kind of Mermaid diagram a block is, from its first keyword (after any frontmatter). */

export const DIAGRAM_KINDS: Record<string, string> = {
  flowchart: 'Flowchart',
  sequence: 'Sequence',
  er: 'Entity relationship',
  state: 'State',
  class: 'Class',
  architecture: 'Architecture',
  other: 'Other',
}

export function diagramKind(code: string): keyof typeof DIAGRAM_KINDS {
  const body = code.replace(/^\s*---[\s\S]*?---\s*/, '')
  const first = body
    .split('\n')
    .map((l) => l.trim())
    .find((l) => l && !l.startsWith('%%'))
  const word = (first ?? '').split(/\s+/)[0]
  if (word === 'flowchart' || word === 'graph') return 'flowchart'
  if (word === 'sequenceDiagram') return 'sequence'
  if (word === 'erDiagram') return 'er'
  if (word.startsWith('stateDiagram')) return 'state'
  if (word === 'classDiagram') return 'class'
  if (word.startsWith('architecture')) return 'architecture'
  return 'other'
}
