import { notifications } from '@mantine/notifications'
import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { useLocation } from 'react-router'

type DocsChanged = { kind: 'added' | 'modified' | 'deleted'; paths: string[] }

function currentDoc(pathname: string): string | null {
  if (!pathname.startsWith('/docs/')) return null
  try {
    return decodeURIComponent(pathname.slice('/docs/'.length))
  } catch {
    return null
  }
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
        if (data.kind !== 'modified') qc.invalidateQueries({ queryKey: ['tree'] })
        for (const p of data.paths) {
          qc.invalidateQueries({ queryKey: ['doc', p] })
          qc.invalidateQueries({ queryKey: ['history', p] })
          qc.invalidateQueries({ queryKey: ['diff', p] })
        }
        for (const key of ['roadmap', 'diagrams', 'search']) qc.invalidateQueries({ queryKey: [key] })
        const open = currentDoc(pathRef.current)
        if (open && data.paths.includes(open)) {
          notifications.show({
            id: `doc-changed-${open}`,
            color: data.kind === 'deleted' ? 'orange' : 'blue',
            message: data.kind === 'deleted' ? 'This doc was deleted.' : 'This doc was just updated.',
            autoClose: 2500,
          })
        }
      })

      source.addEventListener('feedback.changed', () => qc.invalidateQueries({ queryKey: ['feedback'] }))

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
