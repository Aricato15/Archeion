import type { FlowStep, StudyComponent, StudyFlow } from '../api/study'

/** The data side of the interactive flow view: a flow's steps placed on a grid. No React, so it can be tested. */

export const COL = 168
export const PAD = 24
export const HEAD = 62
const ROW = 38
const NOTE = 36
const BLOCK_TOP = 26
const BLOCK_END = 12
const DIVIDER = 24

export type Lane = { id: string; name: string; lines: string[]; x: number }

export type Placed =
  | { kind: 'msg'; n: number; y: number; from: number; to: number; label: string; reply: boolean; async: boolean }
  | { kind: 'note'; n: number; y: number; h: number; from: number; to: number; label: string }
  | {
      kind: 'block'
      y: number
      h: number
      from: number
      to: number
      depth: number
      type: string
      label: string
      dividers: { y: number; label: string }[]
    }

export type SequenceLayout = { lanes: Lane[]; items: Placed[]; width: number; height: number; footer: number }

/** A name broken over at most three short lines. */
export function wrapName(name: string, max = 20): string[] {
  const words = name.split(/(?<=[\s/_(-])/)
  const lines: string[] = []
  let cur = ''
  for (const w of words) {
    if (cur && (cur + w).length > max) {
      lines.push(cur.trim())
      cur = w
    } else cur += w
  }
  if (cur.trim()) lines.push(cur.trim())
  const out = lines.slice(0, 3)
  if (lines.length > 3) out[2] = out[2].slice(0, max - 1) + '…'
  return out.map((l) => (l.length > max + 4 ? l.slice(0, max + 3) + '…' : l))
}

export function layoutFlow(flow: StudyFlow, components: StudyComponent[]): SequenceLayout {
  const names = new Map(components.map((c) => [c.id, c.name]))
  const index = new Map<string, number>()
  const lanes: Lane[] = flow.participants.map((id, i) => {
    index.set(id, i)
    const name = names.get(id) ?? id
    return { id, name, lines: wrapName(name), x: PAD + i * COL + COL / 2 }
  })
  // A step may name a participant the flow didn't list; give it a lane so nothing is lost.
  const lane = (id: string): number => {
    let i = index.get(id)
    if (i === undefined) {
      i = lanes.length
      index.set(id, i)
      const name = names.get(id) ?? id
      lanes.push({ id, name, lines: wrapName(name), x: PAD + i * COL + COL / 2 })
    }
    return i
  }
  const items: Placed[] = []
  let y = HEAD + 18
  let n = 0

  /** Lays steps out from the current y; returns the lanes they touch (min, max), or null. */
  const emit = (steps: FlowStep[], depth: number): [number, number] | null => {
    let lo = Infinity
    let hi = -Infinity
    const touch = (a: number, b: number) => {
      lo = Math.min(lo, a, b)
      hi = Math.max(hi, a, b)
    }
    for (const s of steps) {
      if ('block' in s) {
        const start = y
        const block: Placed = {
          kind: 'block',
          y: start,
          h: 0,
          from: 0,
          to: 0,
          depth,
          type: s.block,
          label: s.label ?? '',
          dividers: [],
        }
        items.push(block)
        y += BLOCK_TOP
        let range = emit(s.steps, depth + 1)
        for (const other of s.block === 'alt' || s.block === 'par' ? (s.others ?? []) : []) {
          block.dividers.push({ y, label: other.label ?? '' })
          y += DIVIDER
          const r = emit(other.steps, depth + 1)
          if (r) range = range ? [Math.min(range[0], r[0]), Math.max(range[1], r[1])] : r
        }
        y += BLOCK_END
        block.h = y - start
        const [a, b] = range ?? [0, Math.max(0, lanes.length - 1)]
        block.from = a
        block.to = b
        touch(a, b)
        y += 6
      } else if ('note' in s) {
        const idx = s.over.map(lane)
        const a = Math.min(...idx)
        const b = Math.max(...idx)
        items.push({ kind: 'note', n: n++, y, h: NOTE - 8, from: a, to: b, label: s.note })
        touch(a, b)
        y += NOTE
      } else {
        const a = lane(s.from)
        const b = lane(s.to)
        items.push({
          kind: 'msg',
          n: n++,
          y: y + ROW - 12,
          from: a,
          to: b,
          label: s.label ?? '',
          reply: Boolean(s.reply),
          async: Boolean(s.async),
        })
        touch(a, b)
        y += ROW
      }
    }
    return lo === Infinity ? null : [lo, hi]
  }
  emit(flow.steps, 0)
  const footer = y + 10
  return { lanes, items, width: PAD * 2 + lanes.length * COL, height: footer + HEAD + 10, footer }
}

/** Which lanes (by id) a placed item involves, for highlighting. */
export function involves(item: Placed, lanes: Lane[]): Set<string> {
  const out = new Set<string>()
  if (item.kind === 'block') return out
  for (let i = Math.min(item.from, item.to); i <= Math.max(item.from, item.to); i++) {
    if (item.kind === 'note' || i === item.from || i === item.to) out.add(lanes[i].id)
  }
  return out
}
