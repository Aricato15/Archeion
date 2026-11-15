import { Alert, Anchor, Badge, Card, Group, Loader, Select, SimpleGrid, Stack, Text, Title } from '@mantine/core'
import GithubSlugger from 'github-slugger'
import { Link, useSearchParams } from 'react-router'
import { useDiagrams, useSources } from '../api/queries'
import { SELF } from '../api/types'
import { docUrl } from '../docs/links'
import { MermaidBlock } from '../docs/MermaidBlock'

export function DiagramsPage() {
  const [params, setParams] = useSearchParams()
  const source = params.get('source') ?? undefined
  const diagrams = useDiagrams(source)
  const sources = useSources()
  return (
    <Stack>
      <Group justify="space-between" align="baseline">
        <Title order={2}>Diagrams</Title>
        <Select
          placeholder="Every project"
          clearable
          searchable
          w={220}
          value={source ?? null}
          onChange={(v) => setParams(v ? { source: v } : {}, { replace: true })}
          data={(sources.data ?? []).map((s) => ({ value: s.id, label: s.title }))}
        />
      </Group>
      <Text c="dimmed" size="sm">
        Every Mermaid diagram in Archeion's docs and in each registered project's own docs, linked to where it lives.
        The project maps generated from the registry are on the Projects page.
      </Text>
      {diagrams.isPending && <Loader />}
      {diagrams.isError && <Alert color="red">{diagrams.error.message}</Alert>}
      {diagrams.data?.length === 0 && <Text c="dimmed">No diagrams yet.</Text>}
      <SimpleGrid cols={{ base: 1, lg: 2 }}>
        {diagrams.data?.map((d) => (
          <Card key={`${d.source}:${d.path}#${d.index}`} withBorder radius="md" padding="md">
            <Group gap="xs" mb="xs">
              {d.source !== SELF && (
                <Badge variant="dot" color="grape" size="sm">
                  {d.source}
                </Badge>
              )}
              <Text size="sm">
                <Anchor component={Link} to={`${docUrl(d.source, d.path)}?line=${d.line}`}>
                  {d.path}
                </Anchor>
                {d.heading && (
                  <Text span c="dimmed" size="sm">
                    {' '}
                    ›{' '}
                    <Anchor
                      component={Link}
                      to={docUrl(d.source, d.path, `#${new GithubSlugger().slug(d.heading)}`)}
                      c="dimmed"
                    >
                      {d.heading}
                    </Anchor>
                  </Text>
                )}
              </Text>
            </Group>
            <MermaidBlock code={d.code} />
          </Card>
        ))}
      </SimpleGrid>
    </Stack>
  )
}
