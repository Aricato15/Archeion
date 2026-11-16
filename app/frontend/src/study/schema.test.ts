import { expect, it } from 'vitest'
import { buildSchema, tableHeight } from './schema'

it('links declared foreign keys column to column, and infers the obvious ones', () => {
  const { tables, links } = buildSchema([
    { id: 'owners', name: 'owners', fields: [{ name: 'id', type: 'INTEGER', pk: true }] },
    { id: 'categories', name: 'categories', fields: [{ name: 'code', type: 'TEXT', pk: true }] },
    {
      id: 'items',
      name: 'items',
      fields: [
        { name: 'id', type: 'INTEGER', pk: true },
        { name: 'owner_id', type: 'INTEGER', fk: 'owners.id', nullable: true },
        { name: 'category_id', type: 'TEXT' },
        { name: 'parentId', type: 'INTEGER' },
        { name: 'ghost_id', type: 'INTEGER' },
        { name: 'id_card', type: 'TEXT' },
      ],
    },
    { id: 'item', name: 'item', fields: [] },
  ])
  const byId = Object.fromEntries(links.map((l) => [l.id, l]))
  expect(byId['fk:items.owner_id']).toMatchObject({ to: 'owners', toColumn: 'id', inferred: false, optional: true })
  // category_id -> categories, by its primary key (code, not id)
  expect(byId['inferred:items.category_id']).toMatchObject({ to: 'categories', toColumn: 'code', inferred: true })
  // parentId -> no "parent" table; ghost_id -> no "ghost" table; id_card isn't a key
  expect(Object.keys(byId).sort()).toEqual(['fk:items.owner_id', 'inferred:items.category_id'])
  const items = tables.find((t) => t.id === 'items')!
  expect(items.columns.filter((c) => c.fk).map((c) => c.name)).toEqual(['owner_id', 'category_id'])
  expect(tableHeight(items)).toBeGreaterThan(tableHeight(tables[0]))
})

it('ignores keys that point nowhere', () => {
  const { links } = buildSchema([
    { id: 'a', name: 'a', fields: [{ name: 'b_ref', fk: 'missing.id' }, { name: 'x', fk: 'a' }] },
  ])
  expect(links).toEqual([])
})
