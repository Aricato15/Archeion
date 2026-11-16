import '@xyflow/react/dist/style.css'
import { ActionIcon, Alert, Box, Loader, Text, useComputedColorScheme } from '@mantine/core'
import { IconChevronDown, IconChevronRight } from '@tabler/icons-react'
import {
  Background,
  Controls,
  type Edge,
  Handle,
  MarkerType,
  MiniMap,
  type Node,
  type NodeProps,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
} from '@xyflow/react'
import { memo, useEffect, useMemo, useState } from 'react'
import {
  type EdgeStyle,
  fold,
  type Graph,
  type GraphNode,
  HEADER,
  neighbours,
  type NodeTone,
  positions,
  toElk,
} from './graph'
import { layoutGraph } from './layout'

/**
 * An interactive nested graph (ADR 0015): React Flow draws it, ELK lays it out in a worker.
 * Containers fold and unfold, hovering a node highlights what it's linked to, a click selects
 * and a double click opens. Colours follow the Mantine light and dark theme.
 */

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
  vertical: boolean
  onToggle: (id: string) => void
  onOpen?: (id: string) => void
}

const Box_ = memo(function BoxNode({ data }: NodeProps<Node<BoxData>>) {
  const { node, container, canFold, folded, faded, selected, vertical, onToggle, onOpen } = data
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
    outline: selected ? '2px solid var(--mantine-color-blue-filled)' : undefined,
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

const nodeTypes = { box: Box_ }

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
}

function Inner({ graph: given, direction = 'LR', height = 460, selected, onSelect, onOpen, initialFolded, minimap }: GraphViewProps) {
  const scheme = useComputedColorScheme('light')
  const flow = useReactFlow()
  const [folded, setFolded] = useState(() => new Set(initialFolded ?? []))
  const [hover, setHover] = useState<string | null>(null)
  const [laid, setLaid] = useState<{ nodes: Node<BoxData>[]; edges: Edge[]; shown: Graph } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const vertical = direction === 'TB'
  // Laid out again only when the graph's content changes, not each time a parent re-renders it.
  const sig = JSON.stringify(given)
  const graph = useMemo(() => JSON.parse(sig) as Graph, [sig])

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
            vertical,
            onToggle,
            onOpen,
          },
        }))
        const edges: Edge[] = shown.edges.map((e) => ({
          id: e.id,
          source: e.from,
          target: e.to,
          label: e.label,
          type: 'smoothstep',
          zIndex: 2,
          markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 },
          labelStyle: { fontSize: 11 },
          labelBgStyle: { fill: 'var(--mantine-color-body)' },
          data: { style: e.style ?? 'solid', tone: e.tone },
        }))
        setLaid({ nodes, edges, shown })
        setError(null)
        requestAnimationFrame(() => flow.fitView({ padding: 0.12, duration: 200 }))
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
    const nodes = laid.nodes.map((n) => ({
      ...n,
      data: {
        ...n.data,
        faded: near ? !near.has(n.id) && !n.data.container : false,
        selected: n.id === selected,
      },
    }))
    const edges = laid.edges.map((e) => {
      const d = e.data as { style: EdgeStyle; tone?: NodeTone }
      const lit = near ? e.source === hover || e.target === hover : true
      const color = d.tone ? toneColor(d.tone) : undefined
      return {
        ...e,
        animated: Boolean(near && lit && hover),
        style: {
          stroke: color,
          strokeWidth: d.style === 'thick' ? 2.5 : 1.4,
          strokeDasharray: DASH[d.style],
          opacity: lit ? 1 : 0.15,
        },
        labelStyle: { ...e.labelStyle, opacity: lit ? 1 : 0.2 },
      }
    })
    return { nodes, edges }
  }, [laid, hover, selected])

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
          {minimap && <MiniMap pannable zoomable />}
        </ReactFlow>
      )}
    </Box>
  )
}

export default function GraphView(props: GraphViewProps) {
  return (
    <ReactFlowProvider>
      <Inner {...props} />
    </ReactFlowProvider>
  )
}
