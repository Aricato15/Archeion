/** Clickable labels in a rendered diagram (used by DiagramFrame). */

export type LabelActions = Record<string, () => void>

const LABEL_SELECTOR = 'text, tspan, span, p, div.nodeLabel, .label'

/** Make the labels in `root` that match `labels` clickable. Returns the cleanup. */
export function bindLabels(root: HTMLElement, labels: LabelActions | undefined, moved: () => boolean): () => void {
  if (!labels || Object.keys(labels).length === 0) return () => {}
  const done: (() => void)[] = []
  const seen = new Set<Element>()
  for (const el of root.querySelectorAll<HTMLElement | SVGElement>(LABEL_SELECTOR)) {
    const text = el.textContent?.trim() ?? ''
    const action = labels[text]
    if (!action) continue
    // The innermost match only, so a click doesn't fire twice through nested labels.
    if ([...el.querySelectorAll(LABEL_SELECTOR)].some((child) => child.textContent?.trim() === text)) continue
    if (seen.has(el)) continue
    seen.add(el)
    const onClick = (e: Event) => {
      if (moved()) return
      e.stopPropagation()
      action()
    }
    el.classList.add('diagram-link')
    el.setAttribute('data-diagram-link', text)
    el.addEventListener('click', onClick)
    done.push(() => {
      el.removeEventListener('click', onClick)
      el.classList.remove('diagram-link')
    })
  }
  return () => done.forEach((f) => f())
}

const NODE_SELECTOR = '.node, .cluster, .actor, .entityBox, g[id^="state-"]'

function labelText(el: Element): string {
  return (el.textContent ?? '').replace(/\s+/g, ' ').trim()
}

/**
 * Highlight the labels in `root` that contain `query` (ignoring case) and dim the rest. Returns the
 * elements that matched, in document order, and a cleanup. An empty query highlights nothing.
 */
export function markHits(root: HTMLElement, query: string): { hits: Element[]; clear: () => void } {
  const needle = query.trim().toLowerCase()
  const marked: Element[] = []
  const hits: Element[] = []
  if (needle) {
    const seenNodes = new Set<Element>()
    for (const el of root.querySelectorAll(LABEL_SELECTOR)) {
      const text = labelText(el)
      if (!text || !text.toLowerCase().includes(needle)) continue
      // The innermost label only, so a wrapper holding a whole table doesn't count.
      if ([...el.querySelectorAll(LABEL_SELECTOR)].some((c) => labelText(c).toLowerCase().includes(needle))) continue
      el.classList.add('diagram-hit')
      marked.push(el)
      hits.push(el)
      const node = el.closest(NODE_SELECTOR)
      if (node && !seenNodes.has(node)) {
        seenNodes.add(node)
        node.classList.add('diagram-hit-node')
        marked.push(node)
      }
    }
    root.classList.add('diagram-searching')
  }
  return {
    hits,
    clear: () => {
      root.classList.remove('diagram-searching')
      for (const el of marked) el.classList.remove('diagram-hit', 'diagram-hit-node')
    },
  }
}

/**
 * Hovering a box or a label lights up every label with the same text (a participant's name shows at
 * the top and the bottom of a sequence diagram) and the box around it. Returns the cleanup.
 */
export function bindHover(root: HTMLElement): () => void {
  let lit: Element[] = []
  const off = () => {
    for (const el of lit) el.classList.remove('diagram-hover', 'diagram-hover-node')
    lit = []
    root.classList.remove('diagram-hovering')
  }
  const onOver = (e: Event) => {
    off()
    const target = e.target as Element | null
    if (!target?.closest) return
    const node = target.closest(NODE_SELECTOR)
    const label = target.closest(LABEL_SELECTOR)
    const text = label ? labelText(label) : ''
    if (node) {
      node.classList.add('diagram-hover-node')
      lit.push(node)
    }
    if (text && text.length <= 80) {
      for (const el of root.querySelectorAll(LABEL_SELECTOR)) {
        if (labelText(el) !== text || [...el.querySelectorAll(LABEL_SELECTOR)].some((c) => labelText(c) === text)) continue
        el.classList.add('diagram-hover')
        lit.push(el)
        const box = el.closest(NODE_SELECTOR)
        if (box && !lit.includes(box)) {
          box.classList.add('diagram-hover-node')
          lit.push(box)
        }
      }
    }
    if (lit.length) root.classList.add('diagram-hovering')
  }
  root.addEventListener('mouseover', onOver)
  root.addEventListener('mouseleave', off)
  return () => {
    root.removeEventListener('mouseover', onOver)
    root.removeEventListener('mouseleave', off)
    off()
  }
}
