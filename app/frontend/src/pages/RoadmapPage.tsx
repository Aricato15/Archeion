import { Alert, Anchor, Card, Group, List, Loader, SimpleGrid, Stack, Text, Title } from '@mantine/core'
import { Link } from 'react-router'
import { useRoadmap } from '../api/queries'
import type { RoadmapItem } from '../api/types'
import { docUrl } from '../docs/links'
import { MarkdownView } from '../docs/MarkdownView'

const COLUMNS = [
  { key: 'now', title: 'Now', color: 'green' },
  { key: 'next', title: 'Next', color: 'blue' },
  { key: 'later', title: 'Later', color: 'gray' },
] as const

function Column({ title, color, items, docPath }: { title: string; color: string; items: RoadmapItem[]; docPath: string }) {
  return (
    <Card withBorder radius="md" padding="md" style={{ borderTop: `3px solid var(--mantine-color-${color}-6)` }}>
      <Title order={4} mb="sm">
        {title}
      </Title>
      {items.length === 0 ? (
        <Text c="dimmed" size="sm">
          Nothing yet.
        </Text>
      ) : (
        <Stack gap="sm">
          {items.map((item, i) => (
            <Card key={i} withBorder padding="xs" radius="sm">
              <MarkdownView content={item.text} docPath={docPath} compact />
            </Card>
          ))}
        </Stack>
      )}
    </Card>
  )
}

export function RoadmapPage() {
  const roadmap = useRoadmap()
  if (roadmap.isPending) return <Loader />
  if (roadmap.isError) return <Alert color="red">{roadmap.error.message}</Alert>
  const data = roadmap.data
  return (
    <Stack>
      <Group justify="space-between" align="baseline">
        <Title order={2}>Roadmap</Title>
        <Text size="sm" c="dimmed">
          {data.updated && `Last updated ${data.updated} · `}
          <Anchor component={Link} to={docUrl(data.path)} size="sm">
            Open {data.path}
          </Anchor>
        </Text>
      </Group>
      <SimpleGrid cols={{ base: 1, md: 3 }}>
        {COLUMNS.map((c) => (
          <Column key={c.key} title={c.title} color={c.color} items={data[c.key]} docPath={data.path} />
        ))}
      </SimpleGrid>
      <Title order={3} mt="md">
        Plans
      </Title>
      {data.plans.length === 0 ? (
        <Text c="dimmed">No dated plans in docs/roadmap/ yet.</Text>
      ) : (
        <List>
          {data.plans.map((p) => (
            <List.Item key={p.path}>
              <Anchor component={Link} to={docUrl(p.path)}>
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
      )}
    </Stack>
  )
}
