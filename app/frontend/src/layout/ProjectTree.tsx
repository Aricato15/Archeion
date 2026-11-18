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
    leftSection:
      project.type === 'module' ? (
        <IconPuzzle size={16} data-type="module" />
      ) : project.type === 'group' ? (
        <IconStack2 size={16} data-type="group" />
      ) : (
        <IconBox size={16} />
      ),
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

/** A group in the sidebar: its label opens the group's overview and unfolds the members; the chevron only folds. */
function GroupItem({
  group,
  members,
  projects,
  current,
  onNavigate,
}: {
  group: Registry['groups'][number]
  members: Project[]
  projects: Map<string, Project>
  current: string | null
  onNavigate: () => void
}) {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const to = group.home ? projectUrl(group.home) : `/groups/${encodeURIComponent(group.id)}`
  const active = group.home ? current === group.home : pathname === `/groups/${encodeURIComponent(group.id)}`
  const [opened, setOpened] = useState(true)
  return (
    <NavLink
      component={Link}
      to={to}
      label={group.title}
      leftSection={<IconStack2 size={16} />}
      active={active}
      opened={opened}
      disableRightSectionRotation
      childrenOffset={14}
      py={4}
      rightSection={
        <IconChevronRight
          size={14}
          data-toggle
          aria-hidden
          style={{ transform: opened ? 'rotate(90deg)' : undefined, transition: 'transform 150ms ease' }}
        />
      }
      onClick={(event) => {
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return
        if ((event.target as Element).closest('[data-toggle]')) {
          setOpened((o) => !o)
          return
        }
        setOpened(true)
        navigate(to)
        onNavigate()
      }}
      onKeyDown={(event) => {
        if (event.key === ' ') setOpened((o) => !o)
      }}
    >
      {members.map((p) => (
        <Item key={p.id} project={p} projects={projects} current={current} onNavigate={onNavigate} />
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
  // A group with a home is its group's header (ADR 0027), so it isn't listed as a project of its own.
  const homes = new Set(registry.groups.flatMap((g) => (g.home ? [g.home] : [])))
  const roots = registry.projects.filter((p) => !p.parent && !homes.has(p.id)).sort((a, b) => a.title.localeCompare(b.title))
  const grouped = registry.groups
    .map((g) => ({
      group: g,
      // Pages directly under the home count as members too.
      members: [
        ...roots.filter((p) => p.group === g.id),
        ...(g.home ? (projects.get(g.home)?.children ?? []).flatMap((c) => (projects.get(c) ? [projects.get(c) as Project] : [])) : []),
      ].filter((p, i, all) => all.findIndex((q) => q.id === p.id) === i),
    }))
    .filter((x) => x.members.length > 0 || x.group.home)
  const standalone = roots.filter((p) => !p.group || !registry.groups.some((g) => g.id === p.group))

  return (
    <>
      {grouped.map(({ group, members }) => (
        <GroupItem key={group.id} group={group} members={members} projects={projects} current={current} onNavigate={onNavigate} />
      ))}
      {standalone.map((p) => (
        <Item key={p.id} project={p} projects={projects} current={current} onNavigate={onNavigate} />
      ))}
    </>
  )
}
