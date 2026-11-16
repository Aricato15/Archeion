import { Group, SegmentedControl, Stack, Text } from '@mantine/core'
import { useState } from 'react'
import { useNavigate } from 'react-router'
import { useSystemLinks } from '../api/queries'
import type { Registry } from '../api/types'
import { MermaidBlock } from '../docs/MermaidBlock'
import { LazyGraph } from '../graph/LazyGraph'
import { buildGraph, buildMermaid, GROUP_PREFIX, type MapOptions } from './map'

/**
 * A map generated from the registry frontmatter (see map.ts), drawn interactively (ADR 0015):
 * click a box to open its page, hover to light up its links, fold groups and parents. Where
 * projects have been studied (ADR 0019), arrows show the calls found in their code. The
 * Mermaid version stays one click away, for copying.
 */
export function RegistryMap({ registry, height = 480, ...opts }: { registry: Registry; height?: number } & MapOptions) {
  const navigate = useNavigate()
  const links = useSystemLinks()
  const [mode, setMode] = useState<'graph' | 'mermaid'>('graph')
  const graph = buildGraph(registry, opts, links.data)
  if (graph.nodes.length === 0) return <Text c="dimmed">Nothing to draw yet.</Text>
  const open = (id: string) =>
    navigate(id.startsWith(GROUP_PREFIX) ? `/groups/${encodeURIComponent(id.slice(GROUP_PREFIX.length))}` : `/projects/${encodeURIComponent(id)}`)
  const studied = (links.data?.studied.length ?? 0) > 0
  return (
    <Stack gap={4}>
      <Group justify="space-between">
        <Text size="xs" c="dimmed">
          {studied
            ? 'Blue arrows are confirmed by the code, orange ones are in the code only, dotted ones never called.'
            : 'Click a box to open it. Study a project to see the calls behind its arrows.'}
        </Text>
        <SegmentedControl
          size="xs"
          value={mode}
          onChange={(v) => setMode(v as 'graph' | 'mermaid')}
          data={[
            { value: 'graph', label: 'Interactive' },
            { value: 'mermaid', label: 'Mermaid' },
          ]}
        />
      </Group>
      {mode === 'graph' ? (
        <LazyGraph
          graph={graph}
          direction={opts.direction ?? 'LR'}
          height={height}
          selected={opts.focus ?? null}
          onSelect={open}
          onOpen={open}
          minimap={graph.nodes.length > 12}
        />
      ) : (
        <MermaidBlock code={buildMermaid(registry, opts)} />
      )}
    </Stack>
  )
}
