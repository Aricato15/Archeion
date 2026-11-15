import { notifications } from '@mantine/notifications'
import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { useLocation } from 'react-router'

type DocsChanged = { source: string; kind: 'added' | 'modified' | 'deleted'; paths: string[] }

/** The [source, path] of the doc being viewed, if any. */
function currentDoc(pathname: string): [string, string] | null {
  try {
    if (pathname.startsWith('/docs/')) return ['archeion', decodeURIComponent(pathname.slice('/docs/'.length))]
    const m = pathname.match(/^\/p\/([^/]+)\/(.+)$/)
    if (m) return [decodeURIComponent(m[1]), decodeURIComponent(m[2])]
  } catch {
    // malformed URL: no current doc
  }
  return null
}

/**
 * Subscribes to /api/events and turns server events into cache invalidation,
 * so open pages update in place while Claude (or an editor) changes the docs.
 */
export function useEvents() {
  const qc = useQueryClient()
  const location = useLocation()
  const pathRef = useRef(location.pathname)
  useEffect(() => {
    pathRef.current = location.pathname
  }, [location.pathname])

  useEffect(() => {
    let source: EventSource | null = null
    let retry: number | undefined
    let stopped = false
    let connectedBefore = false

    const connect = () => {
      source = new EventSource('/api/events')

      source.addEventListener('hello', () => {
        // After a reconnect we may have missed events: refresh everything.
        if (connectedBefore) qc.invalidateQueries()
        connectedBefore = true
      })

      source.addEventListener('docs.changed', (e) => {
        const data = JSON.parse((e as MessageEvent).data) as DocsChanged
        const source = data.source ?? 'archeion'
        if (data.kind !== 'modified') qc.invalidateQueries({ queryKey: ['tree', source] })
        for (const p of data.paths) {
          qc.invalidateQueries({ queryKey: ['doc', source, p] })
          qc.invalidateQueries({ queryKey: ['history', source, p] })
          qc.invalidateQueries({ queryKey: ['diff', source, p] })
        }
        for (const key of ['roadmap', 'diagrams', 'search']) qc.invalidateQueries({ queryKey: [key] })
        const open = currentDoc(pathRef.current)
        if (open && open[0] === source && data.paths.includes(open[1])) {
          notifications.show({
            id: `doc-changed-${source}-${open[1]}`,
            color: data.kind === 'deleted' ? 'orange' : 'blue',
            message: data.kind === 'deleted' ? 'This doc was deleted.' : 'This doc was just updated.',
            autoClose: 2500,
          })
        }
      })

      source.addEventListener('feedback.changed', () => qc.invalidateQueries({ queryKey: ['feedback'] }))

      // A registry page changed: projects, their sources and the maps may all differ now.
      source.addEventListener('registry.changed', () => {
        for (const key of ['registry', 'sources', 'tree', 'roadmap', 'diagrams']) qc.invalidateQueries({ queryKey: [key] })
      })

      source.addEventListener('session.expired', () => {
        source?.close()
        qc.setQueryData(['session'], null)
      })

      source.onerror = () => {
        // EventSource retries by itself unless the server refused the stream (e.g. 401).
        if (source?.readyState === EventSource.CLOSED && !stopped) {
          window.clearTimeout(retry)
          retry = window.setTimeout(() => {
            qc.invalidateQueries({ queryKey: ['session'] })
            connect()
          }, 5000)
        }
      }
    }

    connect()
    return () => {
      stopped = true
      window.clearTimeout(retry)
      source?.close()
    }
  }, [qc])
}
