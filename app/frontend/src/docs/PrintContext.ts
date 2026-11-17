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
