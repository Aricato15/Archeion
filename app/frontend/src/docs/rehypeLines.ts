import type { Root } from 'hast'

/**
 * Marks every top-level block with the source lines it came from
 * (data-line-start / data-line-end). Comments use these as their anchor,
 * and ?line=N jumps to the block that contains line N.
 */
export function rehypeLines() {
  return (tree: Root) => {
    for (const node of tree.children) {
      if (node.type !== 'element' || !node.position) continue
      node.properties = {
        ...node.properties,
        dataLineStart: node.position.start.line,
        dataLineEnd: node.position.end.line,
      }
    }
  }
}
