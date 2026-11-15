import { Text } from '@mantine/core'
import { useMemo } from 'react'
import type { Registry } from '../api/types'
import { MermaidBlock } from '../docs/MermaidBlock'
import { buildMermaid, type MapOptions } from './map'

/** A diagram generated from the registry frontmatter (see map.ts). */
export function RegistryMap({ registry, ...opts }: { registry: Registry } & MapOptions) {
  const code = useMemo(() => buildMermaid(registry, opts), [registry, opts.group, opts.focus, opts.direction]) // eslint-disable-line react-hooks/exhaustive-deps
  if (!code) return <Text c="dimmed">Nothing to draw yet.</Text>
  return <MermaidBlock code={code} />
}
