import { createContext, useContext } from 'react'
import { REGISTRY, SELF, type SourceId } from '../api/types'

const SCHEME = /^[a-z][a-z0-9+.-]*:/i
const IMAGE = /\.(png|jpe?g|gif|webp|svg)$/i

/**
 * Where each source lives, relative to this repo's root: "docs" for archeion, "registry" for
 * the private registry folder, the registry `path` (e.g. "../my-service") for projects. With it, a link written in any doc can be
 * followed into whichever source it points at, so docs never need to copy each other.
 */
export type LinkContext = { bases: Record<SourceId, string> }
export const DEFAULT_LINKS: LinkContext = { bases: { [SELF]: 'docs', [REGISTRY]: 'registry' } }
export const LinkContextValue = createContext<LinkContext>(DEFAULT_LINKS)
export const useLinkContext = () => useContext(LinkContextValue)

/** Normalise a posix path, keeping leading '..' segments ("a/../../b" -> "../b"). */
export function normalize(path: string): string {
  const out: string[] = []
  for (const seg of path.split('/')) {
    if (seg === '' || seg === '.') continue
    if (seg === '..' && out.length && out[out.length - 1] !== '..') out.pop()
    else out.push(seg)
  }
  return out.join('/')
}

function dirname(path: string): string {
  const i = path.lastIndexOf('/')
  return i < 0 ? '' : path.slice(0, i)
}

const encodePath = (path: string) => path.split('/').map(encodeURIComponent).join('/')

export function docUrl(source: SourceId, path: string, hash = ''): string {
  return source === SELF ? `/docs/${encodePath(path)}${hash}` : `/p/${encodeURIComponent(source)}/${encodePath(path)}${hash}`
}

export function rawUrl(source: SourceId, path: string): string {
  return `/api/docs/raw?source=${encodeURIComponent(source)}&path=${encodeURIComponent(path)}`
}

export const projectUrl = (id: string) => `/projects/${encodeURIComponent(id)}`

/** The source (deepest base wins) and source-relative path for a repo-relative path. */
export function locate(ctx: LinkContext, full: string): { source: SourceId; rel: string } | null {
  let best: { source: SourceId; rel: string; depth: number } | null = null
  for (const [source, rawBase] of Object.entries(ctx.bases)) {
    const base = normalize(rawBase)
    if (full !== base && !full.startsWith(`${base}/`)) continue
    const depth = base.split('/').length
    if (!best || depth > best.depth) best = { source, rel: full === base ? '' : full.slice(base.length + 1), depth }
  }
  return best && { source: best.source, rel: best.rel }
}

export type ResolvedLink =
  | { kind: 'external'; href: string }
  | { kind: 'anchor'; hash: string }
  | { kind: 'doc'; to: string }
  | { kind: 'project'; to: string }
  | { kind: 'file'; href: string }
  | { kind: 'outside'; href: string }

/** How a link inside a doc of `source` should behave in the viewer. */
export function resolveLink(ctx: LinkContext, source: SourceId, fromDoc: string, href: string): ResolvedLink {
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
  const base = ctx.bases[source]
  if (base === undefined) return { kind: 'outside', href }
  const full = normalize(`${dirname(normalize(`${base}/${fromDoc}`))}/${decoded}`)
  const found = locate(ctx, full)
  if (!found) return { kind: 'outside', href }
  if (found.rel === '') {
    return found.source === SELF || found.source === REGISTRY
      ? { kind: 'outside', href }
      : { kind: 'project', to: projectUrl(found.source) }
  }
  if (found.rel.toLowerCase().endsWith('.md')) return { kind: 'doc', to: docUrl(found.source, found.rel, hash) }
  if (IMAGE.test(found.rel)) return { kind: 'file', href: rawUrl(found.source, found.rel) }
  return { kind: 'outside', href }
}

/** Image src inside a doc: relative paths load through the backend. */
export function imageSrc(ctx: LinkContext, source: SourceId, fromDoc: string, src: string): string | null {
  if (/^(https?:|data:)/i.test(src)) return src
  if (SCHEME.test(src) || src.startsWith('/')) return null
  const link = resolveLink(ctx, source, fromDoc, src)
  return link.kind === 'file' ? link.href : null
}
