import { Alert, Anchor, Card, Code, Group, List, Loader, SimpleGrid, Stack, Text, Title } from '@mantine/core'
import { IconAlertTriangle, IconFolderPlus } from '@tabler/icons-react'
import { useMemo } from 'react'
import { Link } from 'react-router'
import { useRegistry } from '../api/queries'
import { REGISTRY, locationOf, type Project, type Registry } from '../api/types'
import { docUrl, projectUrl } from '../docs/links'
import { ProjectCard } from './ProjectCard'
import { DriftAlert } from './Drift'
import { RegistryMap } from './RegistryMap'

export const SCAN_CMD = 'powershell -NoProfile -ExecutionPolicy Bypass -File scripts/archeion.ps1 projects scan --write'

export function RegistryWarnings({ registry }: { registry: Registry }) {
  if (registry.warnings.length === 0) return null
  return (
    <Alert color="orange" icon={<IconAlertTriangle size={18} />} title="Registry problems">
      <List size="sm">
        {registry.warnings.map((w, i) => (
          <List.Item key={i}>
            {w.page ? (
              <Anchor component={Link} to={docUrl(REGISTRY, w.page)} size="sm">
                registry/{w.page}
              </Anchor>
            ) : (
              <Text span size="sm" fw={500}>
                Settings
              </Text>
            )}
            : {w.message}
          </List.Item>
        ))}
      </List>
    </Alert>
  )
}

export function Unregistered({ registry }: { registry: Registry }) {
  if (registry.unregistered.length === 0) return null
  return (
    <Alert color="blue" icon={<IconFolderPlus size={18} />} title={`${registry.unregistered.length} unregistered folder(s)`}>
      <Text size="sm">
        These folders in your roots look like projects or modules but have no registry page yet:{' '}
        {registry.unregistered.map((u) => locationOf(u)).join(', ')}.
      </Text>
      <Text size="sm" mt="xs">
        Register them on the{' '}
        <Anchor component={Link} to="/settings" size="sm">
          Settings
        </Anchor>{' '}
        page, or create stub pages from the repo root (it never overwrites a page; add <Code>--only &lt;name&gt;</Code> to pick
        some, or <Code>--root &lt;name&gt;</Code> for one root), then fill in <Code>group</Code> and{' '}
        <Code>depends_on</Code>:
      </Text>
      <Code block mt={4}>
        {SCAN_CMD}
      </Code>
    </Alert>
  )
}

function Cards({ ids, projects }: { ids: string[]; projects: Map<string, Project> }) {
  return (
    <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
      {ids.map((id) => {
        const p = projects.get(id)
        return p ? <ProjectCard key={id} project={p} projects={projects} /> : null
      })}
    </SimpleGrid>
  )
}

/** Top-level projects only: modules and sub-projects show on their parent's page. */
const tops = (ids: string[], projects: Map<string, Project>) =>
  ids.filter((id) => !projects.get(id)?.parent).sort()

export function ProjectsPage() {
  const registry = useRegistry()
  const projects = useMemo(() => new Map((registry.data?.projects ?? []).map((p) => [p.id, p])), [registry.data])
  if (registry.isPending) return <Loader />
  if (registry.isError) return <Alert color="red">{registry.error.message}</Alert>
  const reg = registry.data
  const homes = new Set(reg.groups.flatMap((g) => (g.home ? [g.home] : [])))
  const standalone = tops(
    reg.projects.filter((p) => !homes.has(p.id) && !reg.groups.some((g) => g.projects.includes(p.id))).map((p) => p.id),
    projects,
  )

  return (
    <Stack>
      <Group justify="space-between" align="baseline">
        <Title order={2}>Projects</Title>
        <Text size="sm" c="dimmed">
          {reg.projects.length} registered · {reg.groups.length} group(s) · pages in the private{' '}
          <Anchor component={Link} to={docUrl(REGISTRY, 'projects/README.md')} size="sm">
            registry/projects/
          </Anchor>
        </Text>
      </Group>
      <RegistryWarnings registry={reg} />
      <Unregistered registry={reg} />
      <DriftAlert />
      {reg.projects.length > 0 && (
        <Card withBorder radius="md">
          <Text size="xs" c="dimmed" mb="xs">
            Generated from each page's frontmatter: groups are boxes, modules (rounded) and sub-projects sit inside their parent, arrows are{' '}
            <Code>depends_on</Code>.
          </Text>
          <RegistryMap registry={reg} />
        </Card>
      )}
      {reg.groups.map((g) => (
        <Stack key={g.id} gap="xs">
          <Group gap="xs" align="baseline">
            <Title order={3}>
              <Anchor component={Link} to={g.home ? projectUrl(g.home) : `/groups/${encodeURIComponent(g.id)}`} inherit>
                {g.title}
              </Anchor>
            </Title>
            {g.summary && (
              <Text size="sm" c="dimmed">
                {g.summary}
              </Text>
            )}
          </Group>
          <Cards ids={tops(g.projects, projects)} projects={projects} />
        </Stack>
      ))}
      {standalone.length > 0 && (
        <Stack gap="xs">
          <Title order={3}>Standalone</Title>
          <Cards ids={standalone} projects={projects} />
        </Stack>
      )}
    </Stack>
  )
}
