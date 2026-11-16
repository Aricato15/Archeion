import { ActionIcon, Box, Group, Modal, Text, Tooltip } from '@mantine/core'
import { IconArrowsMaximize, IconFocusCentered, IconZoomIn, IconZoomOut } from '@tabler/icons-react'
import { useEffect, useRef, useState } from 'react'
import { bindLabels, type LabelActions } from './diagramLabels'

export type { LabelActions }

/**
 * A rendered diagram (an SVG string) you can zoom, pan and open full screen. Inline, Ctrl+wheel
 * zooms so the page still scrolls with the wheel; full screen, the wheel zooms. Drag to pan.
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
  wheelZooms,
  height,
  view,
  setView,
}: {
  svg: string
  labels?: LabelActions
  wheelZooms: boolean
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
      if (!wheelZooms && !e.ctrlKey && !e.metaKey) return
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
  }, [wheelZooms, setView])

  useEffect(() => {
    const el = inner.current
    if (!el) return
    return bindLabels(el, labels, () => movedRef.current)
  }, [svg, labels])

  return (
    <Box
      ref={outer}
      style={{
        position: 'relative',
        overflow: 'hidden',
        height,
        cursor: dragging ? 'grabbing' : 'grab',
        touchAction: 'none',
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

function Toolbar({ view, setView, onFull }: { view: View; setView: (v: View) => void; onFull?: () => void }) {
  return (
    <Group gap={2} className="diagram-toolbar">
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
      <Box pos="absolute" top={4} right={4} style={{ zIndex: 2 }}>
        <Toolbar view={view} setView={setView} onFull={() => setFull(true)} />
      </Box>
      <Viewport svg={svg} labels={labels} wheelZooms={false} view={view} setView={setView} />
      <Modal opened={full} onClose={() => setFull(false)} fullScreen title={title ?? 'Diagram'} padding="sm">
        <Group justify="space-between" mb="xs">
          <Text size="xs" c="dimmed">
            Wheel to zoom, drag to pan.
          </Text>
          <Toolbar view={fullView} setView={setFullView} />
        </Group>
        {full && (
          <Viewport
            svg={svg}
            labels={fullLabels}
            wheelZooms
            height="calc(100vh - 110px)"
            view={fullView}
            setView={setFullView}
          />
        )}
      </Modal>
    </Box>
  )
}
