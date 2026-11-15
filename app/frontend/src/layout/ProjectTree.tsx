import { NavLink } from '@mantine/core'
import { IconAlertTriangle, IconBox, IconStack2 } from '@tabler/icons-react'
import { Link, useLocation } from 'react-router'
import type { Project, Registry } from '../api/types'
import { projectUrl } from '../docs/links'

function Item({
  project,
  projects,
  current,
  onNavigate,
}: {
  project: Project
  projects: Map<string, Project>
  current: string | null
  onNavigate: () => void
}) {
  const children = project.children.map((c) => projects.get(c)).filter((c): c is Project => Boolean(c))
  const active = current === project.id
  const inside = children.some((c) => c.id === current)
  return (
    <NavLink
      component={Link}
      to={projectUrl(project.id)}
      label={project.title}
      leftSection={<IconBox size={16} />}
      rightSection={
        project.path && !project.available ? <IconAlertTriangle size={12} color="var(--mantine-color-orange-6)" /> : undefined
      }
      active={active}
      defaultOpened={active || inside}
      childrenOffset={14}
      onClick={onNavigate}
      py={4}
      c={project.status === 'archived' || project.status === 'paused' ? 'dimmed' : undefined}
    >
      {children.length > 0
        ? children.map((c) => (
            <Item key={c.id} project={c} projects={projects} current={current} onNavigate={onNavigate} />
          ))
        : undefined}
    </NavLink>
  )
}

/** Projects in the sidebar: grouped by system, sub-projects under their parent. */
export function ProjectTree({ registry, onNavigate }: { registry: Registry; onNavigate: () => void }) {
  const { pathname } = useLocation()
  const projects = new Map(registry.projects.map((p) => [p.id, p]))
  let current: string | null = null
  const m = pathname.match(/^\/(?:projects|p)\/([^/]+)/)
  if (m) {
    try {
      current = decodeURIComponent(m[1])
    } catch {
      current = null
    }
  }
  const roots = registry.projects.filter((p) => !p.parent).sort((a, b) => a.title.localeCompare(b.title))
  const grouped = registry.groups
    .map((g) => ({ group: g, members: roots.filter((p) => p.group === g.id) }))
    .filter((x) => x.members.length > 0)
  const standalone = roots.filter((p) => !p.group || !registry.groups.some((g) => g.id === p.group))

  return (
    <>
      {grouped.map(({ group, members }) => (
        <NavLink
          key={group.id}
          label={group.title}
          leftSection={<IconStack2 size={16} />}
          defaultOpened
          childrenOffset={14}
          py={4}
        >
          <NavLink
            component={Link}
            to={`/groups/${encodeURIComponent(group.id)}`}
            label="Overview"
            py={2}
            c="dimmed"
            onClick={onNavigate}
            active={pathname === `/groups/${encodeURIComponent(group.id)}`}
          />
          {members.map((p) => (
            <Item key={p.id} project={p} projects={projects} current={current} onNavigate={onNavigate} />
          ))}
        </NavLink>
      ))}
      {standalone.map((p) => (
        <Item key={p.id} project={p} projects={projects} current={current} onNavigate={onNavigate} />
      ))}
    </>
  )
}
