export function formatDate(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export function timeAgo(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return ''
  const d = new Date(iso)
  const seconds = Math.round((now.getTime() - d.getTime()) / 1000)
  if (Number.isNaN(seconds)) return iso
  if (seconds < 45) return 'just now'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} h ago`
  const days = Math.round(hours / 24)
  if (days < 30) return `${days} d ago`
  return formatDate(iso)
}

/** All file paths in a tree, depth first. */
export function flattenFiles(node: { type: string; path: string; children?: unknown[] }): string[] {
  if (node.type === 'file') return [node.path]
  return ((node.children ?? []) as (typeof node)[]).flatMap(flattenFiles)
}
