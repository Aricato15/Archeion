import { Alert, Anchor, Card, Loader, SimpleGrid, Stack, Text, Title } from '@mantine/core'
import GithubSlugger from 'github-slugger'
import { Link } from 'react-router'
import { useDiagrams } from '../api/queries'
import { docUrl } from '../docs/links'
import { MermaidBlock } from '../docs/MermaidBlock'

export function DiagramsPage() {
  const diagrams = useDiagrams()
  if (diagrams.isPending) return <Loader />
  if (diagrams.isError) return <Alert color="red">{diagrams.error.message}</Alert>
  return (
    <Stack>
      <Title order={2}>Diagrams</Title>
      <Text c="dimmed" size="sm">
        Every Mermaid diagram under docs/, linked to the doc and section it lives in.
      </Text>
      {diagrams.data.length === 0 && <Text c="dimmed">No diagrams yet.</Text>}
      <SimpleGrid cols={{ base: 1, lg: 2 }}>
        {diagrams.data.map((d) => (
          <Card key={`${d.path}#${d.index}`} withBorder radius="md" padding="md">
            <Text size="sm" mb="xs">
              <Anchor component={Link} to={`${docUrl(d.path)}?line=${d.line}`}>
                {d.path}
              </Anchor>
              {d.heading && (
                <Text span c="dimmed" size="sm">
                  {' '}
                  ›{' '}
                  <Anchor component={Link} to={docUrl(d.path, `#${new GithubSlugger().slug(d.heading)}`)} c="dimmed">
                    {d.heading}
                  </Anchor>
                </Text>
              )}
            </Text>
            <MermaidBlock code={d.source} />
          </Card>
        ))}
      </SimpleGrid>
    </Stack>
  )
}
