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
