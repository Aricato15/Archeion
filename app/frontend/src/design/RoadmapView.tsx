import { Alert, Badge, Button, Card, Group, Loader, SegmentedControl, SimpleGrid, Stack, Text, Title } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { useState } from 'react'
import { useDesignRoadmap } from '../api/queries'
import type { ChecklistItem } from '../api/design'

const COLUMNS = [
  { key: 'now', title: 'Now', color: 'green' },
  { key: 'next', title: 'Next', color: 'blue' },
  { key: 'later', title: 'Later', color: 'gray' },
  { key: 'done', title: 'Done', color: 'teal' },
] as const

function ItemCard({ item, onOpen }: { item: ChecklistItem; onOpen: (id: string) => void }) {
  return (
    <Card withBorder padding="xs" radius="sm">
      <Stack gap={4}>
        <Text size="sm" fw={500}>
          {item.title}
        </Text>
        <Group gap={6}>
          <Badge size="xs" variant="outline" color="gray">
            {item.kind}
          </Badge>
          {item.priority && (
            <Badge size="xs" variant="light" color={item.priority === 'high' ? 'red' : 'gray'}>
              {item.priority}
            </Badge>
          )}
          {item.phase && (
            <Badge size="xs" variant="light" color="violet">
              {item.phase}
            </Badge>
          )}
          <Text size="xs" c="blue" style={{ cursor: 'pointer' }} onClick={() => onOpen(item.id)}>
            {item.id}
          </Text>
        </Group>
        {item.note && (
          <Text size="xs" c="dimmed">
            {item.note}
          </Text>
        )}
      </Stack>
    </Card>
  )
}

/** The roadmap of a design (ADR 0029), generated from its confirmed checklist items. Read-only: a change is made
 * on the checklist and confirmed there. */
export function RoadmapView(props: {
  project: string
  slug: string
  revision: number | null
  onOpenItem: (id: string) => void
}) {
  const { project, slug, revision, onOpenItem } = props
  const rm = useDesignRoadmap(project, slug, revision)
  const [layout, setLayout] = useState<'columns' | 'timeline'>('columns')
  if (rm.isPending) return <Loader size="sm" />
  if (rm.error) return <Alert color="red">{rm.error.message}</Alert>
  const data = rm.data
  const empty = COLUMNS.every((c) => data[c.key].length === 0)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(data.markdown)
      notifications.show({ message: 'Roadmap copied as Markdown.', color: 'green' })
    } catch {
      notifications.show({ message: "Couldn't copy. Use `design checklist roadmap` in the terminal.", color: 'red' })
    }
  }

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <SegmentedControl
          size="xs"
          value={layout}
          onChange={(v) => setLayout(v as 'columns' | 'timeline')}
          data={[
            { value: 'columns', label: 'Now / Next / Later' },
            { value: 'timeline', label: 'By phase' },
          ]}
        />
        <Button size="compact-xs" variant="default" onClick={copy} disabled={empty}>
          Copy as Markdown
        </Button>
      </Group>
      {revision === null && data.pending > 0 && (
        <Alert color="yellow" variant="light">
          {data.pending} change{data.pending === 1 ? '' : 's'} on the checklist {data.pending === 1 ? "isn't" : "aren't"} in this roadmap until
          you confirm {data.pending === 1 ? 'it' : 'them'}.
        </Alert>
      )}
      {empty ? (
        <Text c="dimmed" size="sm">
          The roadmap is built from the confirmed checklist, and nothing on it is decided yet. Items you have decided on, are
          working on or have finished show up here.
        </Text>
      ) : layout === 'columns' ? (
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }}>
          {COLUMNS.map((c) => (
            <Card key={c.key} withBorder padding="md" radius="md" style={{ borderTop: `3px solid var(--mantine-color-${c.color}-6)` }}>
              <Title order={5} mb="sm">
                {c.title}
              </Title>
              <Stack gap="xs">
                {data[c.key].length === 0 ? (
                  <Text size="sm" c="dimmed">
                    Nothing yet.
                  </Text>
                ) : (
                  data[c.key].map((i) => <ItemCard key={i.id} item={i} onOpen={onOpenItem} />)
                )}
              </Stack>
            </Card>
          ))}
        </SimpleGrid>
      ) : (
        <Stack gap="md">
          {data.phases.map((p) => (
            <Stack key={p.phase ?? 'none'} gap="xs">
              <Title order={5}>{p.phase ?? 'No phase yet'}</Title>
              {p.items.map((i) => (
                <Group key={i.id} gap="xs" wrap="nowrap">
                  <Badge size="sm" variant="light" color={{ idea: 'gray', decided: 'blue', doing: 'orange', done: 'green', dropped: 'red' }[i.status]}>
                    {i.status}
                  </Badge>
                  <ItemCard item={i} onOpen={onOpenItem} />
                </Group>
              ))}
            </Stack>
          ))}
        </Stack>
      )}
    </Stack>
  )
}
