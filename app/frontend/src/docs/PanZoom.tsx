import { ActionIcon, Box, Group, Text, Tooltip } from '@mantine/core'
import { IconFocusCentered, IconZoomIn, IconZoomOut } from '@tabler/icons-react'
import { type ReactNode, useCallback, useEffect, useRef, useState } from 'react'

/**
 * A pan and zoom surface for content the page draws itself (the interactive flow view). The wheel
 * zooms around the pointer and dragging pans, as in DiagramFrame. `children` gets `moved()`, which
 * says whether the last pointer gesture was a drag, so a click after a drag isn't taken as a click.
 */

const MIN = 0.3
const MAX = 6
const STEP = 1.25

type View = { scale: number; x: number; y: number }
const FIT: View = { scale: 1, x: 0, y: 0 }

export function PanZoom({
  children,
  height,
  toolbar,
}: {
  children: (moved: () => boolean) => ReactNode
  height?: number | string
  /** Extra controls, shown left of the zoom buttons. */
  toolbar?: ReactNode
}) {
  const outer = useRef<HTMLDivElement>(null)
  const [view, setView] = useState<View>(FIT)
  const [dragging, setDragging] = useState(false)
  const drag = useRef<{ x: number; y: number; vx: number; vy: number } | null>(null)
  const movedRef = useRef(false)
  const moved = useCallback(() => movedRef.current, [])

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
  }, [])

  const zoom = (f: number) => setView((v) => ({ ...v, scale: Math.min(MAX, Math.max(MIN, v.scale * f)) }))
  return (
    <Box>
      <Group gap={4} justify="flex-end" mb={4} wrap="nowrap">
        {toolbar}
        <Tooltip label="Zoom out">
          <ActionIcon size="sm" variant="default" aria-label="Zoom out" onClick={() => zoom(1 / STEP)}>
            <IconZoomOut size={14} />
          </ActionIcon>
        </Tooltip>
        <Text size="xs" c="dimmed" w={38} ta="center">
          {Math.round(view.scale * 100)}%
        </Text>
        <Tooltip label="Zoom in">
          <ActionIcon size="sm" variant="default" aria-label="Zoom in" onClick={() => zoom(STEP)}>
            <IconZoomIn size={14} />
          </ActionIcon>
        </Tooltip>
        <Tooltip label="Fit">
          <ActionIcon size="sm" variant="default" aria-label="Fit" onClick={() => setView(FIT)}>
            <IconFocusCentered size={14} />
          </ActionIcon>
        </Tooltip>
      </Group>
      <Box
        ref={outer}
        style={{
          position: 'relative',
          overflow: 'hidden',
          height,
          cursor: dragging ? 'grabbing' : 'grab',
          touchAction: 'none',
          userSelect: 'none',
          WebkitUserSelect: 'none',
        }}
        onPointerDown={(e) => {
          if (e.button !== 0) return
          drag.current = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y }
          movedRef.current = false
        }}
        onPointerMove={(e) => {
          const d = drag.current
          if (!d) return
          const dx = e.clientX - d.x
          const dy = e.clientY - d.y
          if (!movedRef.current && Math.hypot(dx, dy) < 4) return
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
          style={{
            transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})`,
            transformOrigin: '0 0',
            transition: dragging ? undefined : 'transform 80ms ease-out',
          }}
        >
          {/* oxlint-disable-next-line react/refs -- `moved` reads the ref only when called, from a click */}
          {children(moved)}
        </div>
      </Box>
    </Box>
  )
}
