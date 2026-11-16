import { Loader } from '@mantine/core'
import { lazy, Suspense } from 'react'
import type { GraphViewProps } from './GraphView'

// React Flow is its own chunk, loaded by the first page with a graph (ADR 0015).
const GraphView = lazy(() => import('./GraphView'))

export function LazyGraph(props: GraphViewProps) {
  return (
    <Suspense fallback={<Loader size="sm" />}>
      <GraphView {...props} />
    </Suspense>
  )
}
