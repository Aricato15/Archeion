const SCHEME = /^[a-z][a-z0-9+.-]*:/i
const IMAGE = /\.(png|jpe?g|gif|webp|svg)$/i

/** Join a relative path onto a doc's folder; null when it climbs out of docs/. */
export function resolveRelative(fromDoc: string, target: string): string | null {
  const parts = fromDoc.split('/').slice(0, -1)
  for (const seg of target.split('/')) {
    if (seg === '' || seg === '.') continue
    if (seg === '..') {
      if (parts.length === 0) return null
      parts.pop()
    } else {
      parts.push(seg)
    }
  }
  return parts.length ? parts.join('/') : null
}

export function docUrl(path: string, hash = ''): string {
  return `/docs/${path.split('/').map(encodeURIComponent).join('/')}${hash}`
}

export function rawUrl(path: string): string {
  return `/api/docs/raw?path=${encodeURIComponent(path)}`
}

export type ResolvedLink =
  | { kind: 'external'; href: string }
  | { kind: 'anchor'; hash: string }
  | { kind: 'doc'; to: string }
  | { kind: 'file'; href: string }
  | { kind: 'outside'; href: string }

/** How a link inside a doc should behave in the viewer. */
export function resolveLink(fromDoc: string, href: string): ResolvedLink {
  if (SCHEME.test(href)) return { kind: 'external', href }
  if (href.startsWith('#')) return { kind: 'anchor', hash: href }
  if (href.startsWith('/')) return { kind: 'outside', href }
  const hashAt = href.indexOf('#')
  const target = hashAt >= 0 ? href.slice(0, hashAt) : href
  const hash = hashAt >= 0 ? href.slice(hashAt) : ''
  let decoded = target
  try {
    decoded = decodeURIComponent(target)
  } catch {
    // keep as written
  }
  const resolved = resolveRelative(fromDoc, decoded)
  if (resolved === null) return { kind: 'outside', href }
  if (resolved.toLowerCase().endsWith('.md')) return { kind: 'doc', to: docUrl(resolved, hash) }
  if (IMAGE.test(resolved)) return { kind: 'file', href: rawUrl(resolved) }
  return { kind: 'outside', href }
}

/** Image src inside a doc: relative paths load through the backend. */
export function imageSrc(fromDoc: string, src: string): string | null {
  if (/^(https?:|data:)/i.test(src)) return src
  if (SCHEME.test(src) || src.startsWith('/')) return null
  let decoded = src
  try {
    decoded = decodeURIComponent(src)
  } catch {
    // keep as written
  }
  const resolved = resolveRelative(fromDoc, decoded)
  return resolved && IMAGE.test(resolved) ? rawUrl(resolved) : null
}
