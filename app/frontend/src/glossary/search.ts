import type { GlossaryTerm } from '../api/queries'

/** Terms matching `q`, case-insensitively, in their name, aliases or definition. Names come first. */
export function searchTerms(terms: GlossaryTerm[], q: string): GlossaryTerm[] {
  const needle = q.trim().toLowerCase()
  if (!needle) return terms
  const rank = (t: GlossaryTerm): number => {
    if ([t.term, ...t.aliases].some((n) => n.toLowerCase().includes(needle))) return 0
    return t.definition.toLowerCase().includes(needle) ? 1 : 2
  }
  return terms
    .map((t) => [rank(t), t] as const)
    .filter(([r]) => r < 2)
    .sort((a, b) => a[0] - b[0])
    .map(([, t]) => t)
}
