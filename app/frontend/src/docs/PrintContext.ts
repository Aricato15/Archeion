import { createContext } from 'react'

/**
 * Set by the report's print route (ADR 0025). Diagrams inside it render as plain light-theme SVG
 * (no zoom, search or dark mode), and each one tells the page when it has finished, so the page
 * can say the whole report is ready to be turned into a PDF.
 */
export type PrintContextValue = {
  /** Call when a diagram starts; the function it returns is called once, when it has finished. */
  track: () => (ok: boolean) => void
}

export const PrintContext = createContext<PrintContextValue | null>(null)

// What a page of a report can hold at 96 dpi, with its heading and margins taken off: A4 or Letter.
const PORTRAIT = { w: 690, h: 740 }
const LANDSCAPE = { w: 1010, h: 540 }

/**
 * Whether a diagram is easier to read on a landscape page. A diagram is never drawn larger than
 * its natural size, so this compares how much each orientation would have to shrink it, and
 * switches only for a clear gain (a wide flow or a wide map, not a slightly wider box).
 */
export function prefersLandscape(svg: string): boolean {
  const m = /viewBox="[-\d.]+\s+[-\d.]+\s+([\d.]+)\s+([\d.]+)"/.exec(svg)
  if (!m) return false
  const w = Number(m[1])
  const h = Number(m[2])
  if (!(w > 0 && h > 0)) return false
  const fit = (box: { w: number; h: number }) => Math.min(1, box.w / w, box.h / h)
  return fit(LANDSCAPE) > fit(PORTRAIT) * 1.15
}
