import {
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Code,
  Collapse,
  Group,
  Loader,
  NavLink,
  SegmentedControl,
  SimpleGrid,
  Stack,
  Table,
  Tabs,
  Text,
  Title,
} from '@mantine/core'
import { IconChevronDown, IconChevronUp, IconExternalLink, IconFileText, IconFileTypePdf, IconMessagePlus } from '@tabler/icons-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'
import { isNotFound } from '../api/client'
import { notifications } from '@mantine/notifications'
import {
  useDoc,
  useFeedbackList,
  useRegistry,
  useSetInboxEdits,
  useSetProjectType,
  useTree,
} from '../api/queries'
import { DEMO_REGISTRY, REGISTRY, locationOf, type Project, type SourceId } from '../api/types'
import { docUrl } from '../docs/links'
import { MarkdownView } from '../docs/MarkdownView'
import { FeedbackCard } from '../feedback/FeedbackCard'
import { FeedbackForm, type FeedbackDraft } from '../feedback/FeedbackForm'
import { flattenFiles } from '../lib/format'
import { ProjectCard, ProjectLink, StatusPill } from './ProjectCard'
import { DriftAlert } from './Drift'
import { RegistryMap } from './RegistryMap'
import { BreakDown } from './BreakDown'
import { PromoteGroup } from './PromoteGroup'
import { RemoveProject } from './RemoveProject'
import { DesignTab } from '../design/DesignTab'
import { StudyTab } from '../study/StudyTab'
import { GlossaryTab } from '../glossary/GlossaryTab'
import { ReportDialog } from '../report/ReportDialog'
import { ReportTab } from '../report/ReportTab'

/** One of the project's own files, read-only, with a link to the full doc view. */
function SourceDoc({ source, path }: { source: SourceId; path: string }) {
  const doc = useDoc(source, path)
  if (doc.isPending) return <Loader size="sm" />
  if (doc.isError) {
    return (
      <Text c="dimmed">
        {isNotFound(doc.error) ? `This project has no ${path}.` : doc.error.message}
      </Text>
    )
  }
  return (
    <Stack gap="xs">
      <Group justify="flex-end">
        <Anchor component={Link} to={docUrl(source, path)} size="sm">
          Open with comments and history <IconExternalLink size={12} />
        </Anchor>
      </Group>
      <MarkdownView content={doc.data.content} docPath={path} source={source} />
    </Stack>
  )
}

/** Project, module, or back to what the folder says (ADR 0016). Writes `type:` on the registry page. */
function TypeControl({ project }: { project: Project }) {
  const setType = useSetProjectType()
  if (project.type === 'group')
    return (
      <Text size="xs" c="dimmed">
        A group with a home (<Code>type: group</Code> on its registry page, ADR 0027).
      </Text>
    )
  const value = project.type_source === 'page' ? project.type : 'auto'
  return (
    <Stack gap={2} align="flex-start">
      <SegmentedControl
        size="xs"
        aria-label="Project or module"
        value={value}
        disabled={setType.isPending}
        data={[
          { value: 'auto', label: `Auto (${project.detected_type})` },
          { value: 'project', label: 'Project' },
          // A module is part of a project, so it needs a parent.
          { value: 'module', label: 'Module', disabled: !project.parent },
        ]}
        onChange={(v) =>
          setType.mutate(
            { id: project.id, type: v === 'auto' ? null : (v as 'project' | 'module') },
            {
              onError: (err) => notifications.show({ color: 'red', title: 'Not changed', message: err.message }),
            },
          )
        }
      />
      <Text size="xs" c="dimmed">
        {project.type_source === 'page' ? 'Set on its registry page.' : 'Detected: '}
        {project.type_source === 'detected' &&
          (project.type === 'module'
            ? `inside ${project.parent} and not a git repository of its own.`
            : project.parent
              ? 'a git repository of its own.'
              : 'a top-level folder.')}
      </Text>
    </Stack>
  )
}

/** Whether Archeion's /inbox may edit this project's files for its items (ADR 0017). Writes `inbox_edits:`. */
export function InboxEditsControl({ project }: { project: Project }) {
  const setEdits = useSetInboxEdits()
  const value = project.inbox_edits_source === 'page' ? (project.inbox_edits ? 'on' : 'off') : 'auto'
  const inherited = project.inbox_edits_source === 'owner' ? `as ${project.owner}` : 'allowed'
  return (
    <Stack gap={2} align="flex-start">
      <SegmentedControl
        size="xs"
        aria-label="Inbox edits"
        value={value}
        disabled={setEdits.isPending}
        data={[
          { value: 'auto', label: `Auto (${inherited})` },
          { value: 'on', label: 'Allowed' },
          { value: 'off', label: 'Not allowed' },
        ]}
        onChange={(v) =>
          setEdits.mutate(
            { id: project.id, value: v === 'auto' ? null : v === 'on' },
            {
              onError: (err) => notifications.show({ color: 'red', title: 'Not changed', message: err.message }),
            },
          )
        }
      />
      <Text size="xs" c="dimmed">
        {project.inbox_edits
          ? "Archeion's /inbox may edit this project's files to carry out its items."
          : "Archeion's /inbox only answers this project's items; its own session does the edits."}
      </Text>
    </Stack>
  )
}

function Facts({ project, projects }: { project: Project; projects: Map<string, Project> }) {
  const rows: [string, React.ReactNode][] = [
    ['Status', <StatusPill key="s" status={project.status} />],
    ['Path', project.path ? <Code key="p">{project.path}</Code> : <Text key="p" c="dimmed" size="sm">none (not on this machine)</Text>],
  ]
  rows.push(['Type', <TypeControl key="t" project={project} />])
  rows.push(['Inbox edits', <InboxEditsControl key="ie" project={project} />])
  if (project.root) rows.push(['Root', <Code key="r">{project.root}</Code>])
  if (project.kind) rows.push(['Kind', project.kind])
  if (project.group) {
    rows.push([
      'Group',
      <Anchor key="g" component={Link} to={`/groups/${encodeURIComponent(project.group)}`} size="sm">
        {project.group}
      </Anchor>,
    ])
  }
  if (project.parent) rows.push(['Part of', <ProjectLink key="pa" id={project.parent} projects={projects} />])
  if (project.ports.length) rows.push(['Ports', project.ports.join(', ')])
  const list = (key: string, ids: string[]) =>
    ids.length ? (
      <Group key={key} gap="xs">
        {ids.map((id) => (
          <ProjectLink key={id} id={id} projects={projects} />
        ))}
      </Group>
    ) : (
      <Text key={key} c="dimmed" size="sm">
        none
      </Text>
    )
  rows.push([
    'Depends on',
    project.depends_on_groups.length ? (
      <Group key="deps" gap="xs">
        {project.depends_on.map((id) => (
          <ProjectLink key={id} id={id} projects={projects} />
        ))}
        {project.depends_on_groups.map((id) => (
          <Anchor key={id} component={Link} to={`/groups/${encodeURIComponent(id)}`} size="sm">
            {id} (group)
          </Anchor>
        ))}
      </Group>
    ) : (
      list('deps', project.depends_on)
    ),
  ])
  rows.push(['Used by', list('used', project.used_by)])
  rows.push([
    'Verified',
    project.verified ?? (
      <Text key="v" c="orange" size="sm">
        never: check the frontmatter against the project and set verified
      </Text>
    ),
  ])
  return (
    <Table withRowBorders={false} verticalSpacing={4}>
      <Table.Tbody>
        {rows.map(([k, v]) => (
          <Table.Tr key={k}>
            <Table.Td w={110}>
              <Text size="sm" c="dimmed">
                {k}
              </Text>
            </Table.Td>
            <Table.Td>{typeof v === 'string' ? <Text size="sm">{v}</Text> : v}</Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  )
}

const APP_HEADER = 56
const SNAP_SHARE = 0.65

export function ProjectPage() {
  const id = useParams().id ?? ''
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const tab = params.get('tab') ?? 'notes'
  const registry = useRegistry()
  const projects = useMemo(() => new Map((registry.data?.projects ?? []).map((p) => [p.id, p])), [registry.data])
  const project = projects.get(id)
  const pageSource = project?.demo ? DEMO_REGISTRY : REGISTRY
  const notes = useDoc(pageSource, project?.page ?? '', Boolean(project))
  const available = Boolean(project?.available)
  const tree = useTree(id, available && tab === 'docs')
  const feedback = useFeedbackList({ source: id }, available)
  const [draft, setDraft] = useState<FeedbackDraft | null>(null)
  const [reportOpen, setReportOpen] = useState(false)
  // Fold the facts, map and sub-projects away so the tabs are the focus; remembered per browser.
  const [folded, setFolded] = useState(() => {
    try {
      return localStorage.getItem('archeion.project.folded') === '1'
    } catch {
      return false
    }
  })
  // Scrolling down until the tabs are above this share of the screen snaps them to the top. Scrolling up never
  // snaps, so you can still get back to the facts.
  const tabsRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    let last = window.scrollY
    let down = false
    let timer: number | undefined
    const onScroll = () => {
      down = window.scrollY > last
      last = window.scrollY
      window.clearTimeout(timer)
      timer = window.setTimeout(() => {
        const el = tabsRef.current
        if (!el || !down) return
        const top = el.getBoundingClientRect().top
        if (top > APP_HEADER + 4 && top < window.innerHeight * SNAP_SHARE) {
          window.scrollBy({ top: top - APP_HEADER, behavior: 'smooth' })
        }
      }, 150)
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => {
      window.clearTimeout(timer)
      window.removeEventListener('scroll', onScroll)
    }
  }, [])
  const toggleFolded = () =>
    setFolded((f) => {
      try {
        localStorage.setItem('archeion.project.folded', f ? '0' : '1')
      } catch {
        /* storage unavailable: the choice just isn't remembered */
      }
      return !f
    })

  if (registry.isPending) return <Loader />
  if (!registry.data || !project) {
    return <Alert color="yellow">There's no registered project named {id}. See Projects for the full list.</Alert>
  }

  const docFiles = tree.data ? flattenFiles(tree.data).filter((p) => p.startsWith(`${project.docs_dir}/`)) : []
  const waiting = (feedback.data ?? []).filter((i) => i.status === 'open' || i.status === 'in_progress').length
  const answered = (feedback.data ?? []).filter((i) => i.status === 'answered').length

  return (
    <Stack maw={1200}>
      <Group justify="space-between" align="flex-start">
        <Stack gap={2}>
          <Group gap="xs">
            <Title order={2}>{project.title}</Title>
            <StatusPill status={project.status} />
            {project.type === 'module' ? (
              <Badge variant="light" color="grape" size="sm">
                module{project.owner && <> of <ProjectLink id={project.owner} projects={projects} /></>}
              </Badge>
            ) : project.type === 'group' ? (
              <Badge variant="light" color="grape" size="sm">
                group
              </Badge>
            ) : (
              <Badge variant="outline" size="sm">
                {project.parent ? 'sub-project' : 'project'}
              </Badge>
            )}
            {project.demo && (
              <Badge variant="filled" color="teal" size="sm" title="Made-up data that ships with Archeion">
                example
              </Badge>
            )}
            {project.needs_restudy && (
              <Badge variant="light" color="orange" size="sm" title="Promoted to a group after its last study">
                needs restudy
              </Badge>
            )}
          </Group>
          {project.summary && <Text c="dimmed">{project.summary}</Text>}
          {project.demo && (
            <Alert color="teal" variant="light" mt="xs" title="Example project">
              Made-up data for show and tell, read from Archeion's committed demo-example-data folder. It's demo
              data, so nothing you do here is changed, sent to Claude or stored in the database: comments,
              prompts, design conversations and edits are switched off.
            </Alert>
          )}
        </Stack>
        <Group gap="xs">
          {available && !project.demo && (
            <Button
              size="xs"
              leftSection={<IconMessagePlus size={14} />}
              onClick={() => setDraft({ kind: 'prompt', source: id, pickDoc: true })}
            >
              Prompt for {project.id}
            </Button>
          )}
          {!project.demo && (
          <Button
            size="xs"
            variant="default"
            leftSection={<IconFileTypePdf size={14} />}
            onClick={() => setReportOpen(true)}
          >
            Report
          </Button>
          )}
          {!project.demo && (
            <>
              <Button
                size="xs"
                variant="default"
                component={Link}
                to={docUrl(REGISTRY, project.page)}
                leftSection={<IconFileText size={14} />}
              >
                Registry page
              </Button>
              <PromoteGroup project={project} />
              <RemoveProject project={project} onRemoved={() => navigate('/projects')} />
            </>
          )}
        </Group>
      </Group>

      {project.path && !available && (
        <Alert color="orange">
          <Code>{locationOf(project)}</Code>{' '}
          {project.root
            ? `isn't available: the root '${project.root}' may not be granted on this machine (ARCHEION_ROOTS), or the folder is missing.`
            : "isn't on this machine (or is outside the workspace)."}{' '}
          Its own docs and feedback aren't available until then. The registry page still works.
        </Alert>
      )}

      <DriftAlert project={project.id} />

      <Group justify="flex-end">
        <Button
          size="compact-xs"
          variant="subtle"
          aria-expanded={!folded}
          leftSection={folded ? <IconChevronDown size={14} /> : <IconChevronUp size={14} />}
          onClick={toggleFolded}
        >
          {folded ? 'Show facts and map' : 'Hide facts and map'}
        </Button>
      </Group>

      <Collapse expanded={!folded}>
      <Stack>
      <SimpleGrid cols={{ base: 1, md: 2 }}>
        <Card withBorder radius="md">
          <Facts project={project} projects={projects} />
        </Card>
        <Card withBorder radius="md">
          <RegistryMap registry={registry.data} focus={project.id} direction="TB" />
        </Card>
      </SimpleGrid>

      {project.type === 'group' && (
        <Stack gap="xs">
          <Group justify="space-between">
            <Title order={4}>Members</Title>
            <BreakDown group={project} />
          </Group>
          {project.members.length === 0 ? (
            <Text size="sm" c="dimmed">
              None yet. A page joins this group with <Code>group: {project.id}</Code> or <Code>parent: {project.id}</Code>.
            </Text>
          ) : (
            <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
              {project.members
                .map((m) => projects.get(m))
                .filter((m): m is Project => Boolean(m) && !m?.parent)
                .sort((a, b) => a.id.localeCompare(b.id))
                .map((m) => (
                  <ProjectCard key={m.id} project={m} projects={projects} />
                ))}
            </SimpleGrid>
          )}
        </Stack>
      )}

      {(['module', 'project'] as const).map((type) => {
        const kids = project.children.map((c) => projects.get(c)).filter((c): c is Project => c?.type === type)
        if (kids.length === 0) return null
        return (
          <Stack key={type} gap="xs">
            <Title order={4}>{type === 'module' ? 'Modules' : 'Sub-projects'}</Title>
            <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
              {kids.map((child) => (
                <ProjectCard key={child.id} project={child} projects={projects} />
              ))}
            </SimpleGrid>
          </Stack>
        )
      })}
      </Stack>
      </Collapse>

      <Tabs ref={tabsRef} style={{ minHeight: `calc(100vh - ${APP_HEADER}px)` }} value={tab} onChange={(v) => setParams(v && v !== 'notes' ? { tab: v } : {}, { replace: true })} keepMounted={false}>
        <Tabs.List
          style={{
            position: 'sticky',
            top: APP_HEADER, // below the app header
            zIndex: 10,
            background: 'var(--mantine-color-body)',
          }}
        >
          <Tabs.Tab value="notes">Cross-project notes</Tabs.Tab>
          <Tabs.Tab value="study">Study</Tabs.Tab>
          <Tabs.Tab value="design">Design</Tabs.Tab>
          <Tabs.Tab value="glossary">Glossary</Tabs.Tab>
          <Tabs.Tab value="reports">Reports</Tabs.Tab>
          <Tabs.Tab value="readme" disabled={!available}>
            README
          </Tabs.Tab>
          <Tabs.Tab value="claude" disabled={!available}>
            CLAUDE.md
          </Tabs.Tab>
          <Tabs.Tab value="docs" disabled={!available}>
            Docs
          </Tabs.Tab>
          <Tabs.Tab
            value="feedback"
            disabled={!available}
            rightSection={
              waiting + answered > 0 ? (
                <Badge size="xs" circle color={answered ? 'green' : 'blue'}>
                  {waiting + answered}
                </Badge>
              ) : null
            }
          >
            Feedback
          </Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="notes" pt="md">
          {notes.data ? (
            <Stack gap="xs">
              <Text size="xs" c="dimmed">
                From <Anchor component={Link} to={docUrl(pageSource, project.page)} size="xs">{project.demo ? 'demo-example-data/registry/' : 'registry/'}{project.page}</Anchor>{project.demo ? '' : ' (private)'}:
                what this project means to the rest of the system. Its own facts stay in its own docs (the other
                tabs).
              </Text>
              <MarkdownView content={notes.data.content} docPath={project.page} source={pageSource} />
            </Stack>
          ) : (
            <Loader size="sm" />
          )}
        </Tabs.Panel>
        <Tabs.Panel value="study" pt="md">
          <StudyTab project={project} />
        </Tabs.Panel>
        <Tabs.Panel value="design" pt="md">
          <DesignTab project={project.id} />
        </Tabs.Panel>
        <Tabs.Panel value="glossary" pt="md">
          <GlossaryTab project={project.id} />
        </Tabs.Panel>
        <Tabs.Panel value="reports" pt="md">
          <ReportTab project={project.id} />
        </Tabs.Panel>
        <Tabs.Panel value="readme" pt="md">
          <SourceDoc source={id} path="README.md" />
        </Tabs.Panel>
        <Tabs.Panel value="claude" pt="md">
          <SourceDoc source={id} path="CLAUDE.md" />
        </Tabs.Panel>
        <Tabs.Panel value="docs" pt="md">
          {tree.isPending && <Loader size="sm" />}
          {tree.data && docFiles.length === 0 && (
            <Text c="dimmed">No Markdown under {project.docs_dir}/ in this project.</Text>
          )}
          {docFiles.map((f) => (
            <NavLink
              key={f}
              component={Link}
              to={docUrl(id, f)}
              label={f.slice(project.docs_dir.length + 1)}
              leftSection={<IconFileText size={16} />}
            />
          ))}
        </Tabs.Panel>
        <Tabs.Panel value="feedback" pt="md">
          <Stack gap="xs">
            <Text size="sm" c="dimmed">
              Items for {project.id} are picked up by <Code>/inbox</Code> in a Claude Code session inside the
              project (the CLI's <Code>--here</Code> finds them by folder).
            </Text>
            {feedback.data?.length === 0 && <Text c="dimmed">No feedback for this project yet.</Text>}
            {feedback.data?.map((item) => <FeedbackCard key={item.id} item={item} />)}
          </Stack>
        </Tabs.Panel>
      </Tabs>
      <FeedbackForm draft={draft} onClose={() => setDraft(null)} />
      <ReportDialog project={project.id} opened={reportOpen} onClose={() => setReportOpen(false)} />
    </Stack>
  )
}
