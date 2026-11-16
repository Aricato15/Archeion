import type { StudyEntity } from '../api/study'

/**
 * A study's entities as a relational schema: tables with their columns, and links from a
 * foreign-key column to the column it references. Declared keys (`fk: "<entity>.<field>"`)
 * come first. A column that isn't declared but reads like one (`owner_id`, `ownerId`) is linked
 * to the matching table's primary key and marked inferred, so the view can tell them apart.
 */

export type Column = { name: string; type: string; pk: boolean; fk: boolean; nullable: boolean }
export type Table = { id: string; name: string; store?: string; columns: Column[] }
export type Link = {
  id: string
  from: string // table id
  fromColumn: string
  to: string
  toColumn: string
  inferred: boolean
  /** The referencing column can be empty: zero or one, rather than exactly one. */
  optional: boolean
}

const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, '')

/** "owner" -> the names a table holding owners might have. */
function tableNames(base: string): string[] {
  const b = norm(base)
  const out = [b, `${b}s`, `${b}es`]
  if (b.endsWith('y')) out.push(`${b.slice(0, -1)}ies`)
  return out
}

/** The table a column name points at by convention, without its id suffix. */
function referencedBase(column: string): string | null {
  const m = column.match(/^(.+?)(?:_id|Id|ID)$/)
  return m && m[1].length > 0 ? m[1] : null
}

export function buildSchema(entities: StudyEntity[]): { tables: Table[]; links: Link[] } {
  const byId = new Map(entities.map((e) => [e.id, e]))
  const byName = new Map<string, StudyEntity>()
  for (const e of entities) {
    byName.set(norm(e.name), e)
    byName.set(norm(e.id), e)
  }
  const pkOf = (e: StudyEntity) => e.fields.find((f) => f.pk)?.name ?? (e.fields.some((f) => f.name === 'id') ? 'id' : null)

  const links: Link[] = []
  const linked = new Set<string>() // "<entity>.<column>" with a link, declared or inferred
  for (const e of entities) {
    for (const f of e.fields) {
      if (!f.fk) continue
      const [target, field] = f.fk.split('.')
      if (!byId.has(target) || !field) continue
      links.push({
        id: `fk:${e.id}.${f.name}`,
        from: e.id,
        fromColumn: f.name,
        to: target,
        toColumn: field,
        inferred: false,
        optional: Boolean(f.nullable),
      })
      linked.add(`${e.id}.${f.name}`)
    }
  }
  for (const e of entities) {
    for (const f of e.fields) {
      if (f.pk || f.fk || linked.has(`${e.id}.${f.name}`)) continue
      const base = referencedBase(f.name)
      if (!base) continue
      const target = tableNames(base)
        .map((n) => byName.get(n))
        .find((t): t is StudyEntity => Boolean(t))
      const pk = target ? pkOf(target) : null
      if (!target || !pk) continue
      links.push({
        id: `inferred:${e.id}.${f.name}`,
        from: e.id,
        fromColumn: f.name,
        to: target.id,
        toColumn: pk,
        inferred: true,
        optional: Boolean(f.nullable),
      })
      linked.add(`${e.id}.${f.name}`)
    }
  }

  const tables: Table[] = entities.map((e) => ({
    id: e.id,
    name: e.name,
    store: e.store,
    columns: e.fields.map((f) => ({
      name: f.name,
      type: f.type ?? '',
      pk: Boolean(f.pk),
      fk: linked.has(`${e.id}.${f.name}`),
      nullable: Boolean(f.nullable),
    })),
  }))
  return { tables, links }
}

export const HEADER_H = 34
export const ROW_H = 24
export const TABLE_W = 250

export const tableHeight = (t: Table) => HEADER_H + Math.max(1, t.columns.length) * ROW_H + 6
