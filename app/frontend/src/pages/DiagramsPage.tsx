import { Alert, Anchor, Badge, Card, Group, Loader, Select, SimpleGrid, Stack, Text, Title } from '@mantine/core'
import GithubSlugger from 'github-slugger'
import { Link, useSearchParams } from 'react-router'
import { useDiagrams, useSources } from '../api/queries'
import { SELF } from '../api/types'
import { docUrl } from '../docs/links'
import { MermaidBlock } from '../docs/MermaidBlock'
import { DIAGRAM_KINDS, diagramKind } from './diagramKind'

export function DiagramsPage() {
  const [params, setParams] = useSearchParams()
  const source = params.get('source') ?? undefined
  const kind = params.get('kind')
  const diagrams = useDiagrams(source)
  const sources = useSources()
  const shown = diagrams.data?.filter((d) => !kind || diagramKind(d.code) === kind)
  return (
    <Stack>
      <Group justify="space-between" align="baseline">
        <Title order={2}>Diagrams</Title>
        <Group gap="xs">
        <Select
          placeholder="Every kind"
          clearable
          w={180}
          value={kind}
          onChange={(v) => {
            const next = new URLSearchParams(params)
            if (v) next.set('kind', v)
            else next.delete('kind')
            setParams(next, { replace: true })
          }}
          data={Object.entries(DIAGRAM_KINDS).map(([value, label]) => ({ value, label }))}
        />
        <Select
          placeholder="Every project"
          clearable
          searchable
          w={220}
          value={source ?? null}
          onChange={(v) => {
            const next = new URLSearchParams(params)
            if (v) next.set('source', v)
            else next.delete('source')
            setParams(next, { replace: true })
          }}
          data={(sources.data ?? []).map((s) => ({ value: s.id, label: s.title }))}
        />
        </Group>
      </Group>
      <Text c="dimmed" size="sm">
        Every Mermaid diagram in Archeion's docs and in each registered project's own docs, linked to where it lives.
        The project maps generated from the registry are on the Projects page, and each project's code study draws its
        own diagrams on its Study tab.
      </Text>
      {diagrams.isPending && <Loader />}
      {diagrams.isError && <Alert color="red">{diagrams.error.message}</Alert>}
      {shown?.length === 0 && <Text c="dimmed">{kind ? 'No diagrams of this kind.' : 'No diagrams yet.'}</Text>}
      <SimpleGrid cols={{ base: 1, lg: 2 }}>
        {shown?.map((d) => (
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
