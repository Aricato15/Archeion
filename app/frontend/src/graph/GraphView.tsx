import '@xyflow/react/dist/style.css'
import { ActionIcon, Alert, Box, Loader, Text, TextInput, useComputedColorScheme } from '@mantine/core'
import { IconChevronDown, IconChevronRight, IconSearch } from '@tabler/icons-react'
import {
  Background,
  BaseEdge,
  Controls,
  type Edge,
  EdgeLabelRenderer,
  type EdgeProps,
  Handle,
  MarkerType,
  MiniMap,
  type Node,
  type NodeProps,
  Panel,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
} from '@xyflow/react'
import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { FULL_HEIGHT, FullScreenButton, FullScreenModal } from '../lib/FullScreen'
import {
  DENSE_LIMIT,
  type EdgeStyle,
  fold,
  type Graph,
  type GraphNode,
  HEADER,
  LABEL_LIMIT,
  neighbours,
  type NodeTone,
  parents,
  type Point,
  positions,
  roundedPath,
  routes,
  toElk,
} from './graph'
import { layoutGraph } from './layout'

/**
 * An interactive nested graph (ADR 0015): React Flow draws it, ELK lays it out in a worker.
 * Containers fold and unfold, hovering a node highlights what it's linked to, a click selects
 * and a double click opens. Colours follow the Mantine light and dark theme.
 */

// React Flow's own default line is a pale grey that nearly vanishes on both themes, so a line with no tone
// takes Mantine's dimmed text colour, which is readable in light and dark.
const EDGE_COLOR = 'var(--mantine-color-dimmed)'

const toneColor = (tone: NodeTone | undefined) =>
  !tone || tone === 'default' ? 'var(--mantine-color-default-border)' : `var(--mantine-color-${tone}-filled)`

const DASH: Record<EdgeStyle, string | undefined> = { solid: undefined, thick: undefined, dashed: '6 4', dotted: '2 4' }

type BoxData = {
  node: GraphNode
  container: boolean
  canFold: boolean
  folded: boolean
  faded: boolean
  selected: boolean
  match: boolean
  vertical: boolean
  onToggle: (id: string) => void
  onOpen?: (id: string) => void
}

const Box_ = memo(function BoxNode({ data }: NodeProps<Node<BoxData>>) {
  const { node, container, canFold, folded, faded, selected, match, vertical, onToggle, onOpen } = data
  const accent = toneColor(node.tone)
  const radius = node.shape === 'round' ? 18 : node.shape === 'store' ? '12px / 18px' : 6
  const toggle = canFold && (
    <ActionIcon
      size="xs"
      variant="subtle"
      aria-label={folded ? `Unfold ${node.label}` : `Fold ${node.label}`}
      onClick={(e) => {
        e.stopPropagation()
        onToggle(node.id)
      }}
      onDoubleClick={(e) => e.stopPropagation()}
    >
      {folded ? <IconChevronRight size={14} /> : <IconChevronDown size={14} />}
    </ActionIcon>
  )
  const handles = (
    <>
      <Handle type="target" position={vertical ? Position.Top : Position.Left} style={{ opacity: 0 }} isConnectable={false} />
      <Handle type="source" position={vertical ? Position.Bottom : Position.Right} style={{ opacity: 0 }} isConnectable={false} />
    </>
  )
  const common = {
    opacity: faded ? 0.25 : node.dimmed ? 0.6 : 1,
    transition: 'opacity 120ms',
    outline: selected
      ? '2px solid var(--mantine-color-blue-filled)'
      : match
        ? '2px solid var(--mantine-color-yellow-filled)'
        : undefined,
    outlineOffset: 2,
  }
  if (container) {
    return (
      <div
        data-node={node.id}
        onDoubleClick={() => onOpen?.(node.id)}
        style={{
          ...common,
          width: '100%',
          height: '100%',
          borderRadius: 10,
          border: `1px ${node.ghost ? 'dashed' : 'solid'} ${accent}`,
          background: 'color-mix(in srgb, var(--mantine-color-default-hover) 55%, transparent)',
        }}
      >
        {handles}
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, height: HEADER, padding: '0 8px' }}>
          {toggle}
          <Text size="xs" fw={600} truncate>
            {node.label}
          </Text>
          {node.sublabel && (
            <Text size="xs" c="dimmed" truncate>
              {node.sublabel}
            </Text>
          )}
        </div>
      </div>
    )
  }
  return (
    <div
      data-node={node.id}
      onDoubleClick={() => onOpen?.(node.id)}
      style={{
        ...common,
        width: '100%',
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        gap: 4,
        padding: '4px 10px',
        borderRadius: radius,
        border: `${node.shape === 'external' ? 2 : 1}px ${node.ghost ? 'dashed' : 'solid'} ${accent}`,
        borderLeftWidth: node.tone && node.tone !== 'default' && !node.ghost ? 4 : undefined,
        background: 'var(--mantine-color-body)',
        boxSizing: 'border-box',
      }}
    >
      {handles}
      {toggle}
      <div style={{ minWidth: 0 }}>
        <Text size="sm" fw={500} truncate>
          {node.label}
        </Text>
        {node.sublabel && (
          <Text size="xs" c="dimmed" truncate>
            {node.sublabel}
          </Text>
        )}
      </div>
    </div>
  )
})

type RoutedData = { points: Point[]; label?: { x: number; y: number }; text?: string; show: boolean }

/** An edge drawn along the route ELK found for it, so it goes around boxes instead of through them. */
const Routed = memo(function RoutedEdge({ id, data, style, markerEnd }: EdgeProps<Edge<RoutedData>>) {
  if (!data || data.points.length < 2) return null
  const mid = data.points[Math.floor(data.points.length / 2)]
  const at = data.label ?? mid
  return (
    <>
      <BaseEdge id={id} path={roundedPath(data.points)} style={style} markerEnd={markerEnd} />
      {data.text && data.show && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${at.x}px, ${at.y}px)`,
              fontSize: 11,
              padding: '0 4px',
              borderRadius: 3,
              background: 'var(--mantine-color-body)',
              pointerEvents: 'none',
              opacity: style?.opacity,
              whiteSpace: 'nowrap',
            }}
          >
            {data.text}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  )
})

const nodeTypes = { box: Box_ }
const edgeTypes = { routed: Routed }

export type GraphViewProps = {
  graph: Graph
  direction?: 'LR' | 'TB'
  height?: number | string
  selected?: string | null
  onSelect?: (id: string) => void
  onOpen?: (id: string) => void
  /** Containers folded at first. Give the view a new `key` to start over. */
  initialFolded?: string[]
  minimap?: boolean
  /** Shown in the full screen window's title bar. */
  title?: string
}

type InnerProps = Omit<GraphViewProps, 'title'> & { onFull?: () => void }

function Inner({
  graph: given,
  direction = 'LR',
  height = 460,
  selected,
  onSelect,
  onOpen,
  initialFolded,
  minimap,
  onFull,
}: InnerProps) {
  const scheme = useComputedColorScheme('light')
  const flow = useReactFlow()
  const [folded, setFolded] = useState(() => new Set(initialFolded ?? []))
  const [hover, setHover] = useState<string | null>(null)
  const [laid, setLaid] = useState<{ nodes: Node<BoxData>[]; edges: Edge[]; shown: Graph } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const fitTo = useRef<string[] | null>(null)
  const foldedRef = useRef<Set<string>>(new Set())
  const vertical = direction === 'TB'
  // Laid out again only when the graph's content changes, not each time a parent re-renders it.
  const sig = JSON.stringify(given)
  const graph = useMemo(() => JSON.parse(sig) as Graph, [sig])

  const matches = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return [] as string[]
    return graph.nodes
      .filter((n) => n.label.toLowerCase().includes(needle) || (n.sublabel ?? '').toLowerCase().includes(needle))
      .map((n) => n.id)
  }, [graph, query])

  // A search opens the boxes that hide a match; the layout that follows zooms to the matches.
  useEffect(() => {
    if (matches.length === 0) return
    const parentOf = parents(graph.nodes)
    const open = new Set<string>()
    for (const id of matches) {
      let cur = parentOf.get(id) ?? null
      while (cur) {
        open.add(cur)
        cur = parentOf.get(cur) ?? null
      }
    }
    const hidden = [...open].some((o) => foldedRef.current.has(o))
    if (hidden) {
      fitTo.current = matches
      setFolded((prev) => new Set([...prev].filter((f) => !open.has(f))))
    } else {
      requestAnimationFrame(() =>
        flow.fitView({ nodes: matches.map((id) => ({ id })), padding: 0.4, duration: 200, maxZoom: 1.2 }),
      )
    }
  }, [matches, graph, flow])

  useEffect(() => {
    foldedRef.current = folded
  }, [folded])

  useEffect(() => {
    let cancelled = false
    const { graph: shown, containers } = fold(graph, folded)
    const byId = new Map(shown.nodes.map((n) => [n.id, n]))
    const onToggle = (id: string) =>
      setFolded((prev) => {
        const next = new Set(prev)
        if (next.has(id)) next.delete(id)
        else next.add(id)
        return next
      })
    layoutGraph(toElk(shown, containers, vertical ? 'DOWN' : 'RIGHT'))
      .then((root) => {
        if (cancelled) return
        const nodes: Node<BoxData>[] = positions(root, folded).map((p) => ({
          id: p.id,
          type: 'box',
          position: { x: p.x, y: p.y },
          parentId: p.parent ?? undefined,
          width: p.width,
          height: p.height,
          style: { width: p.width, height: p.height },
          zIndex: p.container ? 0 : 1,
          data: {
            node: byId.get(p.id)!,
            container: p.container,
            canFold: containers.has(p.id),
            folded: p.folded,
            faded: false,
            selected: false,
            match: false,
            vertical,
            onToggle,
            onOpen,
          },
        }))
        const routed = routes(root)
        const edges: Edge[] = shown.edges.flatMap((e) => {
          const route = routed.get(e.id)
          if (!route) return []
          return [
            {
              id: e.id,
              source: e.from,
              target: e.to,
              type: 'routed',
              zIndex: 2,
              markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 },
              data: { style: e.style ?? 'solid', tone: e.tone, points: route.points, label: route.label, text: e.label },
            },
          ]
        })
        setLaid({ nodes, edges, shown })
        setError(null)
        const target = fitTo.current
        fitTo.current = null
        requestAnimationFrame(() =>
          target?.length
            ? flow.fitView({
                nodes: target.filter((id) => byId.has(id)).map((id) => ({ id })),
                padding: 0.4,
                duration: 200,
                maxZoom: 1.2,
              })
            : flow.fitView({ padding: 0.12, duration: 200 }),
        )
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err))
      })
    return () => {
      cancelled = true
    }
  }, [graph, folded, vertical, flow, onOpen])

  // Hover and selection only restyle; they never lay the graph out again.
  const view = useMemo(() => {
    if (!laid) return null
    const near = hover ? neighbours(laid.shown, hover) : null
    const found = matches.length ? new Set(matches) : null
    const dense = laid.shown.edges.length > DENSE_LIMIT
    const nodes = laid.nodes.map((n) => ({
      ...n,
      data: {
        ...n.data,
        faded: near
          ? !near.has(n.id) && !n.data.container
          : found
            ? !found.has(n.id) && !n.data.container
            : false,
        selected: n.id === selected,
        match: Boolean(found?.has(n.id)),
      },
    }))
    const edges = laid.edges.map((e) => {
      const d = e.data as RoutedData & { style: EdgeStyle; tone?: NodeTone }
      const lit = near ? e.source === hover || e.target === hover : true
      // A dense map keeps its lines faint until a box is hovered, so the boxes stay readable.
      const rest = dense && !near ? 0.45 : 1
      const color = d.tone ? toneColor(d.tone) : EDGE_COLOR
      return {
        ...e,
        markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16, color },
        animated: Boolean(near && lit && hover),
        style: {
          stroke: color,
          strokeWidth: d.style === 'thick' ? 3 : 1.8,
          strokeDasharray: DASH[d.style],
          opacity: lit ? rest : 0.2,
        },
        // Many edges: labels only for the hovered box's lines (and they took no room in the layout).
        data: { ...d, show: laid.shown.edges.length <= LABEL_LIMIT || Boolean(near && lit) },
      }
    })
    return { nodes, edges }
  }, [laid, hover, selected, matches])

  if (error) return <Alert color="red">The graph couldn't be laid out: {error}</Alert>
  return (
    <Box h={height} pos="relative" style={{ border: '1px solid var(--mantine-color-default-border)', borderRadius: 8 }}>
      {!view && (
        <Box pos="absolute" top="45%" left="50%">
          <Loader size="sm" />
        </Box>
      )}
      {view && (
        <ReactFlow
          nodes={view.nodes}
          edges={view.edges}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          colorMode={scheme}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          // A double click opens a node; d3's double-click zoom would swallow it.
          zoomOnDoubleClick={false}
          minZoom={0.1}
          maxZoom={2}
          proOptions={{ hideAttribution: true }}
          onNodeClick={(_, n) => onSelect?.(n.id)}
          onNodeMouseEnter={(_, n) => setHover(n.id)}
          onNodeMouseLeave={() => setHover(null)}
          fitView
        >
          <Background gap={20} size={1} />
          <Controls showInteractive={false} />
          <Panel position="top-left">
            <TextInput
              size="xs"
              w={200}
              aria-label="Find in the map"
              placeholder="Find a box"
              leftSection={<IconSearch size={12} />}
              value={query}
              onChange={(e) => setQuery(e.currentTarget.value)}
              rightSection={
                query ? (
                  <Text size="xs" c="dimmed">
                    {matches.length}
                  </Text>
                ) : null
              }
            />
          </Panel>
          {onFull && (
            <Panel position="top-right">
              <FullScreenButton onClick={onFull} />
            </Panel>
          )}
          {minimap && <MiniMap pannable zoomable />}
        </ReactFlow>
      )}
    </Box>
  )
}

export default function GraphView(props: GraphViewProps & { nested?: boolean }) {
  const { nested, title, onSelect, onOpen, ...rest } = props
  const [full, setFull] = useState(false)
  // A click in the full screen copy shows its target behind it, so it closes first. Stable, because
  // a new `onOpen` lays the graph out again.
  const select = useCallback(
    (id: string) => {
      setFull(false)
      onSelect?.(id)
    },
    [onSelect],
  )
  const open = useCallback(
    (id: string) => {
      setFull(false)
      onOpen?.(id)
    },
    [onOpen],
  )
  return (
    <>
      <ReactFlowProvider>
        <Inner {...rest} onSelect={onSelect} onOpen={onOpen} onFull={nested ? undefined : () => setFull(true)} />
      </ReactFlowProvider>
      {!nested && (
        <FullScreenModal opened={full} onClose={() => setFull(false)} title={title}>
          <GraphView {...rest} nested height={FULL_HEIGHT} onSelect={onSelect && select} onOpen={onOpen && open} />
        </FullScreenModal>
      )}
    </>
  )
}
