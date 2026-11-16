import { MantineProvider } from '@mantine/core'
import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import type { ElkNode } from '../graph/graph'
import SchemaView from './SchemaView'

vi.mock('../graph/layout', () => ({
  layoutGraph: async (root: ElkNode) => ({
    ...root,
    children: root.children?.map((c, i) => ({ ...c, x: i * 300, y: 0 })),
  }),
}))

it('draws each table with its columns and keys, and opens a table on click', async () => {
  const onOpen = vi.fn()
  const { container } = render(
    <MantineProvider>
      <SchemaView
        entities={[
          { id: 'owners', name: 'owners', store: 'db', fields: [{ name: 'id', type: 'INTEGER', pk: true }] },
          {
            id: 'items',
            name: 'items',
            fields: [
              { name: 'id', type: 'INTEGER', pk: true },
              { name: 'owner_id', type: 'INTEGER', fk: 'owners.id', nullable: true },
            ],
          },
        ]}
        storeNames={new Map([['db', 'app.db']])}
        onOpen={onOpen}
      />
    </MantineProvider>,
  )
  expect(await screen.findByText('owner_id')).toBeTruthy()
  expect(screen.getByText('app.db')).toBeTruthy()
  expect(screen.getByText('INTEGER?')).toBeTruthy() // nullable
  expect(screen.getAllByLabelText('primary key')).toHaveLength(2)
  expect(screen.getAllByLabelText('foreign key')).toHaveLength(1)
  // One handle per column and side, so lines attach to the right row.
  expect(container.querySelector('[data-handleid="owner_id:out"]')).toBeTruthy()
  expect(container.querySelector('[data-handleid="id:in"]')).toBeTruthy()
  fireEvent.click(container.querySelector('[data-table="items"]')!)
  expect(onOpen).toHaveBeenCalledWith('items')
})
