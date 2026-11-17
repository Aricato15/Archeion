import { ActionIcon, Box, Group, Modal, Text, TextInput, Tooltip } from '@mantine/core'
import { IconArrowsMaximize, IconFocusCentered, IconSearch, IconZoomIn, IconZoomOut } from '@tabler/icons-react'
import { useEffect, useRef, useState } from 'react'
import { bindHover, bindLabels, type LabelActions, markHits } from './diagramLabels'

export type { LabelActions }

/**
 * A rendered diagram (an SVG string) you can zoom, pan and open full screen. The wheel zooms
 * around the pointer, wherever the diagram is shown. Drag to pan.
 * `labels` maps a label's text to what clicking it does, which gives static diagrams links
 * (Mermaid's own click handling is off, since it runs with securityLevel strict).
 */

const MIN = 0.2
const MAX = 8
const STEP = 1.25

type View = { scale: number; x: number; y: number }
const FIT: View = { scale: 1, x: 0, y: 0 }

function Viewport({
  svg,
  labels,
  height,
  view,
  setView,
  query,
  findTick,
}: {
  svg: string
  labels?: LabelActions
  query: string
  findTick: number
  height?: number | string
  view: View
  setView: (v: View | ((v: View) => View)) => void
}) {
  const outer = useRef<HTMLDivElement>(null)
  const inner = useRef<HTMLDivElement>(null)
  const drag = useRef<{ x: number; y: number; vx: number; vy: number; moved: boolean } | null>(null)
  const movedRef = useRef(false)
  const [dragging, setDragging] = useState(false)

  // Wheel zoom around the pointer. A native listener, since React's wheel events are passive.
  useEffect(() => {
    const el = outer.current
    if (!el) return
    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      const box = el.getBoundingClientRect()
      const px = e.clientX - box.left
      const py = e.clientY - box.top
      setView((v) => {
        const scale = Math.min(MAX, Math.max(MIN, v.scale * (e.deltaY < 0 ? 1.12 : 1 / 1.12)))
        const k = scale / v.scale
        return { scale, x: px - (px - v.x) * k, y: py - (py - v.y) * k }
      })
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [setView])

  useEffect(() => {
    const el = inner.current
    if (!el) return
    return bindLabels(el, labels, () => movedRef.current)
  }, [svg, labels])

  useEffect(() => {
    const el = inner.current
    if (!el) return
    return bindHover(el)
  }, [svg])

  // Search: highlight what matches, and (on Enter) pan the first match to the middle.
  const hits = useRef<Element[]>([])
  useEffect(() => {
    const el = inner.current
    if (!el) return
    const found = markHits(el, query)
    hits.current = found.hits
    return found.clear
  }, [svg, query])
  useEffect(() => {
    const first = hits.current[0]
    const box = outer.current
    if (!findTick || !first || !box) return
    const a = first.getBoundingClientRect()
    const b = box.getBoundingClientRect()
    setView((v) => ({
      ...v,
      x: v.x + (b.left + b.width / 2 - (a.left + a.width / 2)),
      y: v.y + (b.top + b.height / 2 - (a.top + a.height / 2)),
    }))
    // Only when Enter is pressed, not whenever the view moves.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [findTick])

  return (
    <Box
      ref={outer}
      style={{
        position: 'relative',
        overflow: 'hidden',
        height,
        cursor: dragging ? 'grabbing' : 'grab',
        touchAction: 'none',
        // Dragging pans the diagram, so it shouldn't also select the text under the pointer.
        userSelect: 'none',
        WebkitUserSelect: 'none',
      }}
      onPointerDown={(e) => {
        if (e.button !== 0) return
        drag.current = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y, moved: false }
        movedRef.current = false
      }}
      onPointerMove={(e) => {
        const d = drag.current
        if (!d) return
        const dx = e.clientX - d.x
        const dy = e.clientY - d.y
        if (!d.moved && Math.hypot(dx, dy) < 4) return
        if (!d.moved) (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId)
        d.moved = true
        movedRef.current = true
        setDragging(true)
        setView((v) => ({ ...v, x: d.vx + dx, y: d.vy + dy }))
      }}
      onPointerUp={() => {
        drag.current = null
        setDragging(false)
      }}
      onPointerCancel={() => {
        drag.current = null
        setDragging(false)
      }}
    >
      <div
        ref={inner}
        className="mermaid-block"
        role="img"
        style={{
          transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})`,
          transformOrigin: '0 0',
          transition: dragging ? undefined : 'transform 80ms ease-out',
        }}
        dangerouslySetInnerHTML={{ __html: svg }}
      />
    </Box>
  )
}

function Toolbar({
  view,
  setView,
  onFull,
  query,
  setQuery,
  onFind,
}: {
  view: View
  setView: (v: View) => void
  onFull?: () => void
  query: string
  setQuery: (q: string) => void
  onFind: () => void
}) {
  return (
    <Group gap={2} className="diagram-toolbar">
      <TextInput
        size="xs"
        w={130}
        aria-label="Find in the diagram"
        placeholder="Find"
        leftSection={<IconSearch size={12} />}
        value={query}
        onChange={(e) => setQuery(e.currentTarget.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') onFind()
          if (e.key === 'Escape') setQuery('')
        }}
      />
      <Tooltip label="Zoom out">
        <ActionIcon size="sm" variant="default" aria-label="Zoom out" onClick={() => setView({ ...view, scale: Math.max(MIN, view.scale / STEP) })}>
          <IconZoomOut size={14} />
        </ActionIcon>
      </Tooltip>
      <Text size="xs" c="dimmed" w={38} ta="center">
        {Math.round(view.scale * 100)}%
      </Text>
      <Tooltip label="Zoom in">
        <ActionIcon size="sm" variant="default" aria-label="Zoom in" onClick={() => setView({ ...view, scale: Math.min(MAX, view.scale * STEP) })}>
          <IconZoomIn size={14} />
        </ActionIcon>
      </Tooltip>
      <Tooltip label="Fit">
        <ActionIcon size="sm" variant="default" aria-label="Fit" onClick={() => setView(FIT)}>
          <IconFocusCentered size={14} />
        </ActionIcon>
      </Tooltip>
      {onFull && (
        <Tooltip label="Full screen">
          <ActionIcon size="sm" variant="default" aria-label="Full screen" onClick={onFull}>
            <IconArrowsMaximize size={14} />
          </ActionIcon>
        </Tooltip>
      )}
    </Group>
  )
}

export function DiagramFrame({ svg, labels, title }: { svg: string; labels?: LabelActions; title?: string }) {
  const [view, setView] = useState<View>(FIT)
  const [full, setFull] = useState(false)
  const [fullView, setFullView] = useState<View>(FIT)
  const [query, setQuery] = useState('')
  const [findTick, setFindTick] = useState(0)
  const find = () => setFindTick((n) => n + 1)
  // A click on a label while full screen should show its target, so close first.
  const fullLabels =
    labels &&
    Object.fromEntries(
      Object.entries(labels).map(([k, f]) => [
        k,
        () => {
          setFull(false)
          f()
        },
      ]),
    )
  return (
    <Box pos="relative" className="diagram-frame">
      {/* Above the diagram, not over it, so it never covers a label. */}
      <Group justify="flex-end" mb={4}>
        <Toolbar view={view} setView={setView} onFull={() => setFull(true)} query={query} setQuery={setQuery} onFind={find} />
      </Group>
      <Viewport svg={svg} labels={labels} view={view} setView={setView} query={query} findTick={findTick} />
      <Modal opened={full} onClose={() => setFull(false)} fullScreen title={title ?? 'Diagram'} padding="sm">
        <Group justify="space-between" mb="xs">
          <Text size="xs" c="dimmed">
            Wheel to zoom, drag to pan.
          </Text>
          <Toolbar view={fullView} setView={setFullView} query={query} setQuery={setQuery} onFind={find} />
        </Group>
        {full && (
          <Viewport
            svg={svg}
            labels={fullLabels}
            height="calc(100vh - 110px)"
            view={fullView}
            setView={setFullView}
            query={query}
            findTick={findTick}
          />
        )}
      </Modal>
    </Box>
  )
}
