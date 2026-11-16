import type { ElkNode } from './graph'

type Elk = { layout: (graph: ElkNode) => Promise<ElkNode> }
let elk: Promise<Elk> | null = null

/**
 * Lays a graph out with ELK in a web worker, so a big map doesn't block the page. The ELK
 * engine is a separate chunk, fetched by the first graph that needs it.
 */
export function layoutGraph(graph: ElkNode): Promise<ElkNode> {
  elk ??= import('elkjs/lib/elk-api.js')
    .then(
      ({ default: ELK }) =>
        new ELK({
          workerFactory: () => new Worker(new URL('elkjs/lib/elk-worker.min.js', import.meta.url)),
        }) as unknown as Elk,
    )
    .catch((err: unknown) => {
      elk = null
      throw err
    })
  return elk.then((e) => e.layout(graph))
}
