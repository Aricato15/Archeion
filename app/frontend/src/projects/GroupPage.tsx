import { Alert, Anchor, Card, Group, Loader, SimpleGrid, Stack, Text, Title } from '@mantine/core'
import { useMemo } from 'react'
import { Link, Navigate, useParams } from 'react-router'
import { useDoc, useRegistry } from '../api/queries'
import { REGISTRY } from '../api/types'
import { docUrl, projectUrl } from '../docs/links'
import { MarkdownView } from '../docs/MarkdownView'
import { ProjectCard } from './ProjectCard'
import { RegistryMap } from './RegistryMap'

/** A group (a system of related projects): its page, its generated map, its members. */
export function GroupPage() {
  const id = useParams().id ?? ''
  const registry = useRegistry()
  const group = registry.data?.groups.find((g) => g.id === id)
  const page = useDoc(REGISTRY, group?.page ?? '', Boolean(group?.page))
  const projects = useMemo(() => new Map((registry.data?.projects ?? []).map((p) => [p.id, p])), [registry.data])

  if (registry.isPending) return <Loader />
  if (!registry.data || !group) return <Alert color="yellow">There's no group named {id}.</Alert>
  // A group with a home is a project page with members (ADR 0027).
  if (group.home) return <Navigate to={projectUrl(group.home)} replace />

  const members = group.projects.filter((pid) => !projects.get(pid)?.parent).sort()
  return (
    <Stack maw={1200}>
      <Group justify="space-between" align="baseline">
        <Title order={2}>{group.title}</Title>
        {group.page ? (
          <Anchor component={Link} to={docUrl(REGISTRY, group.page)} size="sm">
            Edit or comment on {group.page}
          </Anchor>
        ) : (
          <Text size="sm" c="orange">
            No page yet: create registry/groups/{id}.md
          </Text>
        )}
      </Group>
      <Card withBorder radius="md">
        <RegistryMap registry={registry.data} group={id} />
      </Card>
      <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
        {members.map((pid) => {
          const p = projects.get(pid)
          return p ? <ProjectCard key={pid} project={p} projects={projects} /> : null
        })}
      </SimpleGrid>
      {page.data && (
        <Card withBorder radius="md">
          <MarkdownView content={page.data.content} docPath={group.page} source={REGISTRY} />
        </Card>
      )}
    </Stack>
  )
}
