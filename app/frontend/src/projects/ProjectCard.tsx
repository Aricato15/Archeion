import { Anchor, Badge, Card, Group, Stack, Text, Tooltip } from '@mantine/core'
import { IconAlertTriangle } from '@tabler/icons-react'
import { Link } from 'react-router'
import { useDesignIndex } from '../api/queries'
import type { Project } from '../api/types'
import { StageBadge } from '../design/DesignTab'
import { projectUrl } from '../docs/links'

const STATUS_COLOR: Record<string, string> = {
  active: 'green',
  planned: 'blue',
  paused: 'yellow',
  archived: 'gray',
}

export function StatusPill({ status }: { status: string }) {
  return (
    <Badge size="xs" variant="light" color={STATUS_COLOR[status] ?? 'gray'}>
      {status}
    </Badge>
  )
}

export function ProjectLink({ id, projects }: { id: string; projects: Map<string, Project> }) {
  return (
    <Anchor component={Link} to={projectUrl(id)} size="sm">
      {projects.get(id)?.title ?? id}
    </Anchor>
  )
}

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`

/** "3 modules · 1 sub-project": a project's children by type (ADR 0016). */
function childrenSummary(project: Project, projects: Map<string, Project>): string | null {
  if (project.type === 'group') return plural(project.members.length, 'member')
  const modules = project.children.filter((c) => projects.get(c)?.type === 'module').length
  const nested = project.children.length - modules
  const parts = [modules ? plural(modules, 'module') : null, nested ? plural(nested, 'sub-project') : null]
  return parts.filter(Boolean).join(' · ') || null
}

export function ProjectCard({ project, projects }: { project: Project; projects: Map<string, Project> }) {
  const kids = childrenSummary(project, projects)
  const design = useDesignIndex().data?.find((d) => d.project === project.id)
  return (
    <Card withBorder radius="md" padding="sm" component={Link} to={projectUrl(project.id)}>
      <Stack gap={4}>
        <Group justify="space-between" wrap="nowrap">
          <Text fw={600} truncate>
            {project.title}
          </Text>
          <Group gap={4} wrap="nowrap">
            {project.path && !project.available && (
              <Tooltip label={`${project.path} isn't on this machine`}>
                <IconAlertTriangle size={14} color="var(--mantine-color-orange-6)" />
              </Tooltip>
            )}
            {design && (
              <Tooltip label={`Design '${design.slug}'`}>
                <span>
                  <StageBadge stage={design.stage} size="xs" />
                </span>
              </Tooltip>
            )}
            <StatusPill status={project.status} />
          </Group>
        </Group>
        <Text size="xs" c="dimmed">
          {[project.type === 'module' || project.type === 'group' ? project.type : null, project.kind, project.ports.length ? `:${project.ports.join(', :')}` : null].filter(Boolean).join(' · ') ||
            project.id}
        </Text>
        {project.summary && (
          <Text size="sm" lineClamp={2}>
            {project.summary}
          </Text>
        )}
        {(kids || project.depends_on.length > 0) && (
          <Text size="xs" c="dimmed">
            {kids}
            {kids && project.depends_on.length > 0 && ' · '}
            {project.depends_on.length > 0 &&
              `uses ${project.depends_on.map((d) => projects.get(d)?.title ?? d).join(', ')}`}
          </Text>
        )}
      </Stack>
    </Card>
  )
}
