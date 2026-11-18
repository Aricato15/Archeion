import { TextInput } from '@mantine/core'
import { IconSearch } from '@tabler/icons-react'
import { useMemo, useState } from 'react'
import type { StudyComponent, StudyFlow } from '../api/study'
import { PanZoom } from '../docs/PanZoom'
import { toneOf } from './graph'
import { COL, HEAD, involves, layoutFlow, type Placed } from './sequence'

/**
 * A flow as an interactive sequence diagram. Hover a participant to see only its messages, hover a
 * message to see who it joins and its full text, click a participant to open it, search to dim the
 * rest, and zoom and pan. It's drawn from the same model as the Mermaid version, which stays one click away.
 */

const LINE = 'var(--mantine-color-dimmed)'
const TEXT = 'var(--mantine-color-text)'
const HIT = 'var(--mantine-color-yellow-filled)'

/** A participant's colour, by what it is, as on the maps. */
const accent = (kind: string | undefined) => {
  const tone = toneOf(kind)
  return tone && tone !== 'default' ? `var(--mantine-color-${tone}-filled)` : LINE
}

function clip(text: string, room: number): string {
  const max = Math.max(8, Math.floor(room / 6))
  return text.length > max ? text.slice(0, max - 1) + '…' : text
}

export function SequenceView({
  flow,
  components,
  onOpen,
  height = 560,
}: {
  flow: StudyFlow
  components: StudyComponent[]
  /** Called with a participant's component id when it's clicked. */
  onOpen?: (id: string) => void
  height?: number
}) {
  const layout = useMemo(() => layoutFlow(flow, components), [flow, components])
  const [lane, setLane] = useState<string | null>(null)
  const [step, setStep] = useState<number | null>(null)
  const [query, setQuery] = useState('')
  const needle = query.trim().toLowerCase()
  const { lanes, items } = layout
  const laneName = new Map(lanes.map((l) => [l.id, l.name]))

  const matches = (it: Placed): boolean => {
    if (!needle || it.kind === 'block') return false
    if (it.label.toLowerCase().includes(needle)) return true
    return [...involves(it, lanes)].some((id) => (laneName.get(id) ?? '').toLowerCase().includes(needle))
  }
  const hitCount = items.filter(matches).length
  const faded = (it: Placed): boolean => {
    if (it.kind === 'block') return false
    if (step !== null) return it.n !== step
    if (lane) return !involves(it, lanes).has(lane)
    if (needle) return !matches(it)
    return false
  }
  const laneFaded = (id: string): boolean => {
    if (step !== null) {
      const it = items.find((i) => i.kind !== 'block' && i.n === step)
      return it ? !involves(it, lanes).has(id) : false
    }
    if (lane) return id !== lane
    if (needle) return !(laneName.get(id) ?? '').toLowerCase().includes(needle)
    return false
  }

  const header = (y: number, close: () => void) =>
    lanes.map((l) => (
      <g
        key={`${l.id}-${y}`}
        opacity={laneFaded(l.id) ? 0.3 : 1}
        style={{ cursor: onOpen ? 'pointer' : undefined }}
        onMouseEnter={() => setLane(l.id)}
        onMouseLeave={() => setLane(null)}
        onClick={() => {
          close()
          onOpen?.(l.id)
        }}
        data-lane={l.id}
      >
        <title>{l.name}</title>
        <rect
          x={l.x - COL / 2 + 12}
          y={y}
          width={COL - 24}
          height={HEAD - 8}
          rx={6}
          fill="var(--mantine-color-body)"
          stroke={lane === l.id ? 'var(--mantine-color-blue-filled)' : LINE}
          strokeWidth={lane === l.id ? 2 : 1}
        />
        {/* The coloured left edge the maps give a box, by kind. */}
        <rect x={l.x - COL / 2 + 12} y={y} width={5} height={HEAD - 8} rx={2} fill={accent(l.kind)} />
        {l.lines.map((t, i) => (
          <text
            key={i}
            x={l.x}
            y={y + (HEAD - 8) / 2 + (i - (l.lines.length - 1) / 2) * 14 + 4}
            textAnchor="middle"
            fontSize={12}
            fontWeight={500}
            fill={TEXT}
          >
            {t}
          </text>
        ))}
      </g>
    ))

  return (
    <PanZoom
      height={height}
      title={flow.title}
      toolbar={
        <TextInput
          size="xs"
          w={170}
          aria-label="Find in the flow"
          placeholder="Find a step or participant"
          leftSection={<IconSearch size={12} />}
          value={query}
          onChange={(e) => setQuery(e.currentTarget.value)}
          onKeyDown={(e) => e.key === 'Escape' && setQuery('')}
          rightSection={needle ? <span style={{ fontSize: 11 }}>{hitCount}</span> : null}
        />
      }
    >
      {(moved, close) => (
        <svg
          role="img"
          aria-label={flow.title}
          viewBox={`0 0 ${layout.width} ${layout.height}`}
          width={layout.width}
          height={layout.height}
          style={{ maxWidth: '100%', height: 'auto', display: 'block' }}
          onClick={(e) => moved() && e.stopPropagation()}
        >
          <defs>
            <marker id="seq-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill={LINE} />
            </marker>
            <marker id="seq-open" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10" fill="none" stroke={LINE} strokeWidth={1.5} />
            </marker>
          </defs>
          {items
            .filter((i) => i.kind === 'block')
            .map((b, k) => {
              if (b.kind !== 'block') return null
              const x = lanes[b.from].x - COL / 2 + 6
              const w = lanes[b.to].x - lanes[b.from].x + COL - 12
              return (
                <g key={`b${k}`} opacity={0.9}>
                  <rect
                    x={x}
                    y={b.y}
                    width={w}
                    height={b.h}
                    rx={10}
                    fill="color-mix(in srgb, var(--mantine-color-default-hover) 55%, transparent)"
                    stroke="var(--mantine-color-default-border)"
                  />
                  <rect x={x} y={b.y} width={Math.max(38, b.type.length * 8 + 14)} height={18} fill={LINE} opacity={0.25} rx={5} />
                  <text x={x + 6} y={b.y + 13} fontSize={11} fontWeight={600} fill={TEXT}>
                    {b.type}
                  </text>
                  {b.label && (
                    <text x={x + b.type.length * 8 + 22} y={b.y + 13} fontSize={11} fill={TEXT}>
                      {clip(`[${b.label}]`, w - 70)}
                    </text>
                  )}
                  {b.dividers.map((d, i) => (
                    <g key={i}>
                      <line x1={x} x2={x + w} y1={d.y} y2={d.y} stroke={LINE} strokeDasharray="4 3" />
                      {d.label && (
                        <text x={x + 6} y={d.y + 15} fontSize={11} fill={TEXT}>
                          {clip(`[${d.label}]`, w - 12)}
                        </text>
                      )}
                    </g>
                  ))}
                </g>
              )
            })}
          {lanes.map((l) => (
            <line
              key={l.id}
              x1={l.x}
              x2={l.x}
              y1={HEAD - 8}
              y2={layout.footer}
              stroke={LINE}
              strokeWidth={lane === l.id ? 1.6 : 0.8}
              opacity={laneFaded(l.id) ? 0.2 : 0.6}
            />
          ))}
          {items.map((it) => {
            if (it.kind === 'block') return null
            const lit = matches(it)
            const op = faded(it) ? 0.2 : 1
            if (it.kind === 'note') {
              // A note is as wide as its text needs (up to a limit), centred over the lanes it names.
              const span = lanes[it.to].x - lanes[it.from].x + COL - 32
              const w = Math.max(span, Math.min(it.label.length * 6.2 + 24, 380))
              const x = (lanes[it.from].x + lanes[it.to].x) / 2 - w / 2
              return (
                <g key={`n${it.n}`} opacity={op} onMouseEnter={() => setStep(it.n)} onMouseLeave={() => setStep(null)}>
                  <title>{it.label}</title>
                  <rect
                    x={x}
                    y={it.y}
                    width={w}
                    height={it.h}
                    rx={4}
                    fill="var(--mantine-color-default-hover)"
                    stroke={lit ? HIT : LINE}
                    strokeWidth={lit ? 2 : 1}
                  />
                  <text x={x + w / 2} y={it.y + it.h / 2 + 4} textAnchor="middle" fontSize={11} fill={TEXT}>
                    {clip(it.label, w - 10)}
                  </text>
                </g>
              )
            }
            const a = lanes[it.from].x
            const b = lanes[it.to].x
            const self = it.from === it.to
            const mid = (a + b) / 2
            // A label may run past its arrow, since it's centred and has a halo; the full text is in the tooltip.
            const room = self ? COL - 40 : Math.max(Math.abs(b - a) - 12, COL * 2.4)
            const on = step === it.n
            const stroke = on ? 'var(--mantine-color-blue-filled)' : lit ? HIT : LINE
            return (
              <g key={`m${it.n}`} opacity={op} onMouseEnter={() => setStep(it.n)} onMouseLeave={() => setStep(null)}>
                <title>{`${laneName.get(lanes[it.from].id)} → ${laneName.get(lanes[it.to].id)}: ${it.label}`}</title>
                {/* A wide, invisible line so thin arrows are easy to hover. */}
                {self ? (
                  <path
                    d={`M ${a} ${it.y - 10} h 26 v 14 h -26`}
                    fill="none"
                    stroke={stroke}
                    strokeWidth={on || lit ? 2 : 1.2}
                    markerEnd="url(#seq-arrow)"
                  />
                ) : (
                  <>
                    <line x1={a} x2={b} y1={it.y} y2={it.y} stroke="transparent" strokeWidth={14} />
                    <line
                      x1={a}
                      x2={b}
                      y1={it.y}
                      y2={it.y}
                      stroke={stroke}
                      strokeWidth={on || lit ? 2 : 1.2}
                      strokeDasharray={it.reply ? '5 4' : undefined}
                      markerEnd={it.async ? 'url(#seq-open)' : 'url(#seq-arrow)'}
                    />
                  </>
                )}
                <text
                  x={self ? a + 32 : mid}
                  y={self ? it.y - 3 : it.y - 5}
                  textAnchor={self ? 'start' : 'middle'}
                  fontSize={11}
                  fill={TEXT}
                  stroke="var(--mantine-color-body)"
                  strokeWidth={3}
                  paintOrder="stroke"
                  fontWeight={on || lit ? 600 : 400}
                >
                  {clip(`${it.n + 1}. ${it.label}`, room)}
                </text>
              </g>
            )
          })}
          {header(0, close)}
          {header(layout.footer, close)}
        </svg>
      )}
    </PanZoom>
  )
}
