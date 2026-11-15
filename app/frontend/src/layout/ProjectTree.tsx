import { Group, NavLink } from '@mantine/core'
import { IconAlertTriangle, IconBox, IconChevronRight, IconPuzzle, IconStack2 } from '@tabler/icons-react'
import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router'
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
  const navigate = useNavigate()
  const children = project.children.map((c) => projects.get(c)).filter((c): c is Project => Boolean(c))
  const active = current === project.id
  const inside = children.some((c) => c.id === current)
  const [opened, setOpened] = useState(active || inside)
  // Opening a project (or one of its modules) from anywhere unfolds it here.
  const [wasHere, setWasHere] = useState(active || inside)
  if (wasHere !== (active || inside)) {
    setWasHere(active || inside)
    if (active || inside) setOpened(true)
  }

  const warning =
    project.path && !project.available ? <IconAlertTriangle size={12} color="var(--mantine-color-orange-6)" /> : undefined
  const common = {
    component: Link,
    to: projectUrl(project.id),
    label: project.title,
    // Projects (their own repository) and modules (part of one) look different (ADR 0016).
    leftSection: project.type === 'module' ? <IconPuzzle size={16} data-type="module" /> : <IconBox size={16} />,
    active,
    childrenOffset: 14,
    py: 4,
    c: project.status === 'archived' || project.status === 'paused' ? 'dimmed' : undefined,
  } as const

  if (children.length === 0) return <NavLink {...common} rightSection={warning} onClick={onNavigate} />

  // A project with modules or sub-projects is a page of its own too. Mantine's NavLink turns a parent into a
  // toggle (it prevents the link), so the label opens the page and unfolds it, and the chevron
  // only folds and unfolds.
  return (
    <NavLink
      {...common}
      opened={opened}
      disableRightSectionRotation
      rightSection={
        <Group gap={4} wrap="nowrap">
          {warning}
          <IconChevronRight
            size={14}
            data-toggle
            aria-hidden
            style={{ transform: opened ? 'rotate(90deg)' : undefined, transition: 'transform 150ms ease' }}
          />
        </Group>
      }
      onClick={(event) => {
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return
        if ((event.target as Element).closest('[data-toggle]')) {
          setOpened((o) => !o)
          return
        }
        setOpened(true)
        navigate(projectUrl(project.id))
        onNavigate()
      }}
      onKeyDown={(event) => {
        if (event.key === ' ') setOpened((o) => !o)
      }}
    >
      {children.map((c) => (
        <Item key={c.id} project={c} projects={projects} current={current} onNavigate={onNavigate} />
      ))}
    </NavLink>
  )
}

/** Projects in the sidebar: grouped by system, modules and sub-projects under their parent. */
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
