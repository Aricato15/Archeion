import { ActionIcon, Alert, Anchor, Badge, Card, Group, List, Loader, Select, SimpleGrid, Stack, Text, Title } from '@mantine/core'
import { IconChevronLeft, IconChevronRight } from '@tabler/icons-react'
import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { useRegistry, useRoadmap } from '../api/queries'
import { SELF, type RoadmapDoc, type RoadmapItem, type SourceId } from '../api/types'
import { docUrl, projectUrl } from '../docs/links'
import { MarkdownView } from '../docs/MarkdownView'

const COLUMNS = [
  { key: 'now', title: 'Now', color: 'green' },
  { key: 'next', title: 'Next', color: 'blue' },
  { key: 'later', title: 'Later', color: 'gray' },
] as const

function Column(props: { title: string; color: string; items: RoadmapItem[]; source: SourceId; docPath: string; date?: string | null }) {
  const { title, color, items, source, docPath, date } = props
  return (
    <Card withBorder radius="md" padding="md" style={{ borderTop: `3px solid var(--mantine-color-${color}-6)` }}>
      <Group gap="xs" mb="sm">
        <Title order={5}>{title}</Title>
        {date && (
          <Badge variant="light" color="gray">
            {date}
          </Badge>
        )}
      </Group>
      {items.length === 0 ? (
        <Text c="dimmed" size="sm">
          Nothing yet.
        </Text>
      ) : (
        <Stack gap="sm">
          {items.map((item, i) => (
            <Card key={i} withBorder padding="xs" radius="sm">
              <MarkdownView content={item.text} docPath={docPath} source={source} compact />
            </Card>
          ))}
        </Stack>
      )}
    </Card>
  )
}

function Board({ roadmap, source }: { roadmap: RoadmapDoc; source: SourceId }) {
  // Three cards at all times. The strip is the released versions (oldest first), then Now, Next, Later;
  // the arrows slide the three-card window back over older versions and forward again.
  const [back, setBack] = useState(0)
  if (!roadmap.structured) {
    return (
      <Text size="sm" c="dimmed">
        <Anchor component={Link} to={docUrl(source, roadmap.path)} size="sm">
          {roadmap.path}
        </Anchor>{' '}
        has no Now / Next / Later sections, so there's nothing to lay out. Open it to read it.
      </Text>
    )
  }
  const strip = [
    ...[...(roadmap.releases ?? [])].reverse().map((r) => ({ key: `v${r.version}`, title: r.version, color: 'teal', items: r.items, date: r.date })),
    ...COLUMNS.map((c) => ({ key: c.key, title: c.title, color: c.color, items: roadmap[c.key], date: null as string | null })),
  ]
  const maxBack = strip.length - 3
  const start = maxBack - Math.min(back, maxBack)
  return (
    <Stack gap="sm">
      {maxBack > 0 && (
        <Group justify="space-between">
          <ActionIcon variant="light" aria-label="Older versions" disabled={back >= maxBack} onClick={() => setBack((n) => Math.min(n + 1, maxBack))}>
            <IconChevronLeft size={18} />
          </ActionIcon>
          <ActionIcon variant="light" aria-label="Newer versions" disabled={back === 0} onClick={() => setBack((n) => Math.max(n - 1, 0))}>
            <IconChevronRight size={18} />
          </ActionIcon>
        </Group>
      )}
      <SimpleGrid cols={{ base: 1, md: 3 }}>
        {strip.slice(start, start + 3).map((c) => (
          <Column key={c.key} title={c.title} color={c.color} items={c.items} date={c.date} source={source} docPath={roadmap.path} />
        ))}
      </SimpleGrid>
    </Stack>
  )
}

/** The cross-project roadmap, then each project's own (filterable by group or project). */
export function RoadmapPage() {
  const roadmap = useRoadmap()
  const registry = useRegistry()
  const [params, setParams] = useSearchParams()
  const filter = params.get('show') ?? 'all'
  const projects = useMemo(() => new Map((registry.data?.projects ?? []).map((p) => [p.id, p])), [registry.data])

  if (roadmap.isPending) return <Loader />
  if (roadmap.isError) return <Alert color="red">{roadmap.error.message}</Alert>
  const { cross } = roadmap.data
  const groupOf = (id: string) => registry.data?.groups.find((g) => g.projects.includes(id))?.id ?? null
  const shown = roadmap.data.projects.filter((p) => {
    if (filter === 'all') return true
    if (filter === 'cross') return false
    if (filter.startsWith('group:')) return groupOf(p.project) === filter.slice(6)
    return p.project === filter
  })
  const withRoadmap = shown.filter((p) => p.roadmap)
  const without = shown.filter((p) => !p.roadmap)

  const options = [
    { value: 'all', label: 'Everything' },
    { value: 'cross', label: 'Cross-project only' },
    ...(registry.data?.groups ?? []).map((g) => ({ value: `group:${g.id}`, label: `Group: ${g.title}` })),
    ...roadmap.data.projects.map((p) => ({ value: p.project, label: p.title })),
  ]

  return (
    <Stack>
      <Group justify="space-between" align="baseline">
        <Title order={2}>Roadmap</Title>
        <Select
          w={260}
          data={options}
          value={filter}
          onChange={(v) => setParams(v && v !== 'all' ? { show: v } : {}, { replace: true })}
          allowDeselect={false}
          searchable
        />
      </Group>

      {(filter === 'all' || filter === 'cross') && (
        <Stack gap="xs">
          <Group justify="space-between" align="baseline">
            <Title order={3}>Cross-project</Title>
            {cross && (
              <Text size="sm" c="dimmed">
                {cross.updated && `Last updated ${cross.updated} · `}
                <Anchor component={Link} to={docUrl(SELF, cross.path)} size="sm">
                  Open {cross.path}
                </Anchor>
              </Text>
            )}
          </Group>
          {cross ? <Board roadmap={cross} source={SELF} /> : <Text c="dimmed">No docs/roadmap/roadmap.md yet.</Text>}
          {cross && cross.plans.length > 0 && (
            <>
              <Title order={5} mt="sm">
                Plans
              </Title>
              <List size="sm">
                {cross.plans.map((p) => (
                  <List.Item key={p.path}>
                    <Anchor component={Link} to={docUrl(SELF, p.path)} size="sm">
                      {p.title}
                    </Anchor>
                    {p.date && (
                      <Text span c="dimmed" size="sm">
                        {' '}
                        · {p.date}
                      </Text>
                    )}
                  </List.Item>
                ))}
              </List>
            </>
          )}
        </Stack>
      )}

      {withRoadmap.map((p) => (
        <Stack key={p.project} gap="xs">
          <Group justify="space-between" align="baseline">
            <Title order={3}>
              <Anchor component={Link} to={projectUrl(p.project)} inherit>
                {p.title}
              </Anchor>
            </Title>
            <Text size="sm" c="dimmed">
              {p.roadmap?.updated && `Last updated ${p.roadmap.updated} · `}
              {projects.get(p.project)?.parent && `part of ${projects.get(p.project)?.parent} · `}
              <Anchor component={Link} to={docUrl(p.project, p.roadmap!.path)} size="sm">
                Open {p.roadmap!.path}
              </Anchor>
            </Text>
          </Group>
          <Board roadmap={p.roadmap!} source={p.project} />
        </Stack>
      ))}

      {without.length > 0 && filter !== 'cross' && (
        <Text size="sm" c="dimmed">
          No roadmap of their own (docs/roadmap/roadmap.md, docs/roadmap.md or ROADMAP.md):{' '}
          {without.map((p, i) => (
            <span key={p.project}>
              {i > 0 && ', '}
              <Anchor component={Link} to={projectUrl(p.project)} size="sm">
                {p.title}
              </Anchor>
            </span>
          ))}
          .
        </Text>
      )}
    </Stack>
  )
}
