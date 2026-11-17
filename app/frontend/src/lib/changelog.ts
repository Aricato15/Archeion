export type Release = {
  /** "1.2.0", or "Unreleased". */
  version: string
  /** YYYY-MM-DD, or null for Unreleased and for headings without a date. */
  date: string | null
  /** The Markdown under the heading. */
  body: string
}

const HEADING = /^##\s+\[?([^\]\s]+)\]?(?:\s*[-–—]\s*(\d{4}-\d{2}-\d{2}))?\s*$/

/** The releases of a Keep a Changelog file, in the order they're written (newest first). Empty sections are dropped. */
export function parseChangelog(text: string): Release[] {
  const out: Release[] = []
  let cur: { version: string; date: string | null; lines: string[] } | null = null
  let fenced = false
  const close = () => {
    if (cur) out.push({ version: cur.version, date: cur.date, body: cur.lines.join('\n').trim() })
  }
  for (const line of text.split(/\r?\n/)) {
    if (/^```/.test(line)) fenced = !fenced
    const m = !fenced ? HEADING.exec(line) : null
    if (m) {
      close()
      cur = { version: m[1], date: m[2] ?? null, lines: [] }
    } else cur?.lines.push(line)
  }
  close()
  return out.filter((r) => r.body !== '')
}

/** Newest first. Unreleased goes before the dated releases, and a release without a date after them. */
export function byNewest(a: Release & { title: string }, b: Release & { title: string }): number {
  const rank = (e: Release) => (e.version === 'Unreleased' ? 2 : e.date ? 1 : 0)
  if (rank(a) !== rank(b)) return rank(b) - rank(a)
  if (a.date && b.date && a.date !== b.date) return a.date < b.date ? 1 : -1
  return a.title.localeCompare(b.title)
}
