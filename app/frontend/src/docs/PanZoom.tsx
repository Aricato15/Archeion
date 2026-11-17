import { ActionIcon, Box, Stack, Tooltip } from '@mantine/core'
import { IconFocusCentered, IconZoomIn, IconZoomOut } from '@tabler/icons-react'
import { type ReactNode, useCallback, useEffect, useRef, useState } from 'react'

/**
 * A pan and zoom canvas for content the page draws itself (the interactive flow view). It looks
 * like the maps (`GraphView`): a bordered box with a dotted grid, zoom controls at the bottom left
 * and `toolbar` (the Find box) at the top left. The wheel zooms around the pointer and dragging
 * pans. `children` gets `moved()`, which says whether the last pointer gesture was a drag, so a
 * click after a drag isn't taken as a click.
 */

const MIN = 0.3
const MAX = 6
const STEP = 1.25
/** Room above the content for the toolbar, so it doesn't sit on the first row. */
const TOP = 48

type View = { scale: number; x: number; y: number }
const FIT: View = { scale: 1, x: 0, y: 0 }

export function PanZoom({
  children,
  height,
  toolbar,
}: {
  children: (moved: () => boolean) => ReactNode
  height?: number | string
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
  const control = (label: string, onClick: () => void, icon: ReactNode) => (
    <Tooltip label={label} position="right">
      <ActionIcon size="md" variant="default" aria-label={label} onClick={onClick}>
        {icon}
      </ActionIcon>
    </Tooltip>
  )

  return (
    <Box
      pos="relative"
      style={{ border: '1px solid var(--mantine-color-default-border)', borderRadius: 8, overflow: 'hidden' }}
    >
      <Box
        ref={outer}
        h={height}
        style={{
          position: 'relative',
          overflow: 'hidden',
          cursor: dragging ? 'grabbing' : 'grab',
          touchAction: 'none',
          userSelect: 'none',
          WebkitUserSelect: 'none',
          // The same dotted grid as the maps.
          backgroundImage:
            'radial-gradient(color-mix(in srgb, var(--mantine-color-dimmed) 40%, transparent) 1px, transparent 1px)',
          backgroundSize: '20px 20px',
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
            paddingTop: TOP,
            transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})`,
            transformOrigin: '0 0',
            transition: dragging ? undefined : 'transform 80ms ease-out',
          }}
        >
          {/* oxlint-disable-next-line react/refs -- `moved` reads the ref only when called, from a click */}
          {children(moved)}
        </div>
      </Box>
      <Box pos="absolute" top={8} left={8} style={{ zIndex: 2 }}>
        {toolbar}
      </Box>
      <Stack gap={2} pos="absolute" bottom={8} left={8} style={{ zIndex: 2 }}>
        {control('Zoom in', () => zoom(STEP), <IconZoomIn size={16} />)}
        {control('Zoom out', () => zoom(1 / STEP), <IconZoomOut size={16} />)}
        {control('Fit', () => setView(FIT), <IconFocusCentered size={16} />)}
      </Stack>
    </Box>
  )
}
