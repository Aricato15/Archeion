import type { Anchor } from '../api/types'

const HEADING = /^H[1-6]$/
export const MAX_QUOTE = 2000

/** The top-level block (a direct child of root) that contains node, if any. */
export function blockOf(root: HTMLElement, node: Node | null): HTMLElement | null {
  let el: Node | null = node
  while (el && el.parentNode !== root) el = el.parentNode
  return el instanceof HTMLElement && el.dataset.lineStart ? el : null
}

/** Text of the nearest heading at or before a block. */
export function headingFor(block: HTMLElement): string | undefined {
  let el: Element | null = block
  while (el) {
    if (HEADING.test(el.tagName)) return el.textContent?.trim() || undefined
    el = el.previousElementSibling
  }
  return undefined
}

export function lineRange(start: HTMLElement, end: HTMLElement = start): [number, number] {
  const a = Number(start.dataset.lineStart)
  const b = Number(end.dataset.lineEnd ?? end.dataset.lineStart)
  return a <= b ? [a, b] : [b, a]
}

export function anchorForBlock(block: HTMLElement): Anchor {
  return { heading: headingFor(block), lines: lineRange(block) }
}

/** Anchor for a text selection inside root, or null if the selection isn't in the doc. */
export function anchorForSelection(root: HTMLElement, selection: Selection | null): Anchor | null {
  if (!selection || selection.isCollapsed || selection.rangeCount === 0) return null
  const text = selection.toString().trim()
  if (!text) return null
  const range = selection.getRangeAt(0)
  const start = blockOf(root, range.startContainer)
  const end = blockOf(root, range.endContainer)
  if (!start || !end) return null
  return { heading: headingFor(start), lines: lineRange(start, end), quote: text.slice(0, MAX_QUOTE) }
}

/** The block whose source range contains a line (or the last block starting before it). */
export function blockForLine(root: HTMLElement, line: number): HTMLElement | null {
  let best: HTMLElement | null = null
  for (const child of Array.from(root.children)) {
    if (!(child instanceof HTMLElement) || !child.dataset.lineStart) continue
    const start = Number(child.dataset.lineStart)
    const end = Number(child.dataset.lineEnd ?? start)
    if (start <= line && line <= end) return child
    if (start <= line) best = child
  }
  return best
}

export function describeAnchor(anchor: Anchor | null | undefined): string {
  if (!anchor) return 'Whole doc'
  const parts = []
  if (anchor.heading) parts.push(`§ ${anchor.heading}`)
  if (anchor.lines) {
    const [a, b] = anchor.lines
    parts.push(a === b ? `line ${a}` : `lines ${a}–${b}`)
  }
  return parts.join(', ') || 'Whole doc'
}
