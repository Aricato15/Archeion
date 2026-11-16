import { MantineProvider } from '@mantine/core'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { ElkNode, Graph } from './graph'
import GraphView from './GraphView'

// A fake layout: everything in a row, containers sized to hold their children.
vi.mock('./layout', () => ({
  layoutGraph: async (root: ElkNode) => {
    const place = (n: ElkNode, i: number): ElkNode => {
      const children = n.children?.map(place)
      return { ...n, x: i * 200, y: 0, width: n.width ?? 400, height: n.height ?? 200, children }
    }
    return { ...root, children: root.children?.map(place) }
  },
}))

const graph: Graph = {
  nodes: [
    { id: 'api', label: 'API' },
    { id: 'routes', label: 'routes', parent: 'api' },
    { id: 'db', label: 'app.db', sublabel: 'database' },
  ],
  edges: [{ id: 'e', from: 'routes', to: 'db', label: 'SELECT' }],
}

describe('GraphView', () => {
  it('draws nodes, selects on click, opens on double click and folds containers', async () => {
    const onSelect = vi.fn()
    const onOpen = vi.fn()
    const { container } = render(
      <MantineProvider>
        <GraphView graph={graph} onSelect={onSelect} onOpen={onOpen} />
      </MantineProvider>,
    )
    expect(await screen.findByText('routes')).toBeTruthy()
    expect(screen.getByText('database')).toBeTruthy()
    fireEvent.click(container.querySelector('[data-node="db"]')!)
    expect(onSelect).toHaveBeenCalledWith('db')
    fireEvent.doubleClick(container.querySelector('[data-node="db"]')!)
    expect(onOpen).toHaveBeenCalledWith('db')
    fireEvent.click(screen.getByRole('button', { name: 'Fold API' }))
    expect(await screen.findByRole('button', { name: 'Unfold API' })).toBeTruthy()
    expect(screen.queryByText('routes')).toBeNull()
  })
})
