import '@xyflow/react/dist/style.css'
import { Alert, Box, Group, Loader, Text, useComputedColorScheme } from '@mantine/core'
import { IconKey, IconLink } from '@tabler/icons-react'
import {
  Background,
  Controls,
  type Edge,
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
import { memo, useCallback, useEffect, useMemo, useState } from 'react'
import { FULL_HEIGHT, FullScreenButton, FullScreenModal } from '../lib/FullScreen'
import type { StudyEntity } from '../api/study'
import { layoutGraph } from '../graph/layout'
import { buildSchema, HEADER_H, ROW_H, type Table, TABLE_W, tableHeight } from './schema'

/**
 * A study's data as a relational schema (ADR 0019): each table a box listing its columns, each
 * foreign key a line from its column to the column it references. Inferred keys are dashed.
 * Laid out by ELK, drawn by React Flow: zoom, pan, minimap, and hover a table to light up its
 * relations. Clicking a table calls `onOpen` (the Data view scrolls to its card).
 */

type TableData = { table: Table; storeName?: string; faded: boolean; onOpen?: (id: string) => void }

const handleStyle = { opacity: 0, width: 6, height: 6 }

const TableNode = memo(function TableNode({ data }: NodeProps<Node<TableData>>) {
  const { table, storeName, faded, onOpen } = data
  return (
    <div
      data-table={table.id}
      style={{
        width: TABLE_W,
        borderRadius: 8,
        border: '1px solid var(--mantine-color-default-border)',
        background: 'var(--mantine-color-body)',
        boxShadow: 'var(--mantine-shadow-xs)',
        opacity: faded ? 0.25 : 1,
        transition: 'opacity 120ms',
        overflow: 'hidden',
        cursor: onOpen ? 'pointer' : 'default',
      }}
    >
      <Group
        h={HEADER_H}
        px={8}
        gap={6}
        wrap="nowrap"
        justify="space-between"
        style={{ background: 'var(--mantine-color-orange-light)', borderBottom: '1px solid var(--mantine-color-default-border)' }}
      >
        <Text size="sm" fw={700} truncate>
          {table.name}
        </Text>
        {storeName && (
          <Text size="xs" c="dimmed" truncate>
            {storeName}
          </Text>
        )}
      </Group>
      {table.columns.length === 0 && (
        <Text size="xs" c="dimmed" px={8} h={ROW_H} lh={`${ROW_H}px`}>
          no columns recorded
        </Text>
      )}
      {table.columns.map((c) => (
        <div
          key={c.name}
          style={{
            position: 'relative',
            height: ROW_H,
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '0 8px',
            borderBottom: '1px solid var(--mantine-color-default-border)',
          }}
        >
          <Handle id={`${c.name}:in`} type="target" position={Position.Left} style={handleStyle} isConnectable={false} />
          <Handle id={`${c.name}:out`} type="source" position={Position.Right} style={handleStyle} isConnectable={false} />
          <span style={{ width: 14, display: 'inline-flex' }}>
            {c.pk ? (
              <IconKey size={13} color="var(--mantine-color-yellow-filled)" aria-label="primary key" />
            ) : c.fk ? (
              <IconLink size={13} color="var(--mantine-color-blue-filled)" aria-label="foreign key" />
            ) : null}
          </span>
          <Text size="xs" fw={c.pk ? 700 : 400} truncate style={{ flex: 1 }}>
            {c.name}
          </Text>
          <Text size="xs" c="dimmed" ff="monospace" truncate maw={90}>
            {c.type}
            {c.nullable ? '?' : ''}
          </Text>
        </div>
      ))}
    </div>
  )
})

const nodeTypes = { table: TableNode }

function Inner({
  entities,
  storeNames,
  onOpen,
  height,
  onFull,
}: {
  entities: StudyEntity[]
  storeNames: Map<string, string>
  onOpen?: (id: string) => void
  height: number | string
  onFull?: () => void
}) {
  const scheme = useComputedColorScheme('light')
  const flow = useReactFlow()
  const { tables, links } = useMemo(() => buildSchema(entities), [entities])
  const [positions, setPositions] = useState<Map<string, { x: number; y: number }> | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [hover, setHover] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    layoutGraph({
      id: '__root__',
      layoutOptions: {
        'elk.algorithm': 'layered',
        'elk.direction': 'RIGHT',
        'elk.layered.spacing.nodeNodeBetweenLayers': '90',
        'elk.spacing.nodeNode': '40',
        'elk.edgeRouting': 'ORTHOGONAL',
      },
      children: tables.map((t) => ({ id: t.id, width: TABLE_W, height: tableHeight(t) })),
      // Referenced tables to the right of the ones that point at them.
      edges: links.filter((l) => l.from !== l.to).map((l) => ({ id: l.id, sources: [l.from], targets: [l.to] })),
    })
      .then((root) => {
        if (cancelled) return
        setPositions(new Map((root.children ?? []).map((c) => [c.id, { x: c.x ?? 0, y: c.y ?? 0 }])))
        setError(null)
        requestAnimationFrame(() => flow.fitView({ padding: 0.1, duration: 200 }))
      })
      .catch((err: unknown) => !cancelled && setError(err instanceof Error ? err.message : String(err)))
    return () => {
      cancelled = true
    }
  }, [tables, links, flow])

  const related = useMemo(() => {
    if (!hover) return null
    const ids = new Set([hover])
    for (const l of links) {
      if (l.from === hover) ids.add(l.to)
      if (l.to === hover) ids.add(l.from)
    }
    return ids
  }, [hover, links])

  if (error) return <Alert color="red">The schema couldn't be laid out: {error}</Alert>
  if (!positions) return <Loader size="sm" />

  const nodes: Node<TableData>[] = tables.map((t) => ({
    id: t.id,
    type: 'table',
    position: positions.get(t.id) ?? { x: 0, y: 0 },
    width: TABLE_W,
    height: tableHeight(t),
    data: {
      table: t,
      storeName: t.store ? storeNames.get(t.store) : undefined,
      faded: related ? !related.has(t.id) : false,
      onOpen,
    },
  }))
  const edges: Edge[] = links.map((l) => {
    const lit = !hover || l.from === hover || l.to === hover
    return {
      id: l.id,
      source: l.from,
      sourceHandle: `${l.fromColumn}:out`,
      target: l.to,
      targetHandle: `${l.toColumn}:in`,
      type: 'smoothstep',
      animated: Boolean(hover && lit),
      label: hover && lit ? `${l.fromColumn} → ${l.toColumn}${l.inferred ? ' (inferred)' : ''}` : undefined,
      labelStyle: { fontSize: 11 },
      labelBgStyle: { fill: 'var(--mantine-color-body)' },
      markerEnd: { type: MarkerType.ArrowClosed, width: 14, height: 14 },
      style: {
        stroke: l.inferred ? 'var(--mantine-color-gray-6)' : 'var(--mantine-color-blue-filled)',
        strokeWidth: 1.6,
        strokeDasharray: l.inferred ? '6 4' : undefined,
        opacity: lit ? 1 : 0.12,
      },
    }
  })

  return (
    <Box h={height} style={{ border: '1px solid var(--mantine-color-default-border)', borderRadius: 8 }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        colorMode={scheme}
        nodesDraggable
        nodesConnectable={false}
        elementsSelectable={false}
        zoomOnDoubleClick={false}
        minZoom={0.1}
        maxZoom={2.5}
        proOptions={{ hideAttribution: true }}
        onNodeClick={(_, n) => onOpen?.(n.id)}
        onNodeDrag={(_, n) => setPositions((prev) => new Map(prev).set(n.id, n.position))}
        onNodeMouseEnter={(_, n) => setHover(n.id)}
        onNodeMouseLeave={() => setHover(null)}
        fitView
      >
        <Background gap={20} size={1} />
        <Controls showInteractive={false} />
        {onFull && (
          <Panel position="top-right">
            <FullScreenButton onClick={onFull} />
          </Panel>
        )}
        {tables.length > 4 && <MiniMap pannable zoomable />}
      </ReactFlow>
    </Box>
  )
}

export default function SchemaView(props: {
  entities: StudyEntity[]
  storeNames: Map<string, string>
  onOpen?: (id: string) => void
  height?: number | string
  nested?: boolean
}) {
  const { nested, onOpen, ...rest } = props
  const [full, setFull] = useState(false)
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
        <Inner {...rest} onOpen={onOpen} height={props.height ?? 560} onFull={nested ? undefined : () => setFull(true)} />
      </ReactFlowProvider>
      {!nested && (
        <FullScreenModal opened={full} onClose={() => setFull(false)} title="Data">
          <SchemaView {...rest} nested height={FULL_HEIGHT} onOpen={onOpen && open} />
        </FullScreenModal>
      )}
    </>
  )
}
