import {
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Code,
  Group,
  Loader,
  NavLink,
  SimpleGrid,
  Stack,
  Table,
  Tabs,
  Text,
  Title,
} from '@mantine/core'
import { IconExternalLink, IconFileText, IconMessagePlus } from '@tabler/icons-react'
import { useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import { isNotFound } from '../api/client'
import { useDoc, useFeedbackList, useRegistry, useTree } from '../api/queries'
import { REGISTRY, type Project, type SourceId } from '../api/types'
import { docUrl } from '../docs/links'
import { MarkdownView } from '../docs/MarkdownView'
import { FeedbackCard } from '../feedback/FeedbackCard'
import { FeedbackForm, type FeedbackDraft } from '../feedback/FeedbackForm'
import { flattenFiles } from '../lib/format'
import { ProjectCard, ProjectLink, StatusPill } from './ProjectCard'
import { RegistryMap } from './RegistryMap'

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

function Facts({ project, projects }: { project: Project; projects: Map<string, Project> }) {
  const rows: [string, React.ReactNode][] = [
    ['Status', <StatusPill key="s" status={project.status} />],
    ['Path', project.path ? <Code key="p">{project.path}</Code> : <Text key="p" c="dimmed" size="sm">none (not on this machine)</Text>],
  ]
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
  rows.push(['Depends on', list('deps', project.depends_on)])
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

export function ProjectPage() {
  const id = useParams().id ?? ''
  const [params, setParams] = useSearchParams()
  const tab = params.get('tab') ?? 'notes'
  const registry = useRegistry()
  const projects = useMemo(() => new Map((registry.data?.projects ?? []).map((p) => [p.id, p])), [registry.data])
  const project = projects.get(id)
  const notes = useDoc(REGISTRY, project?.page ?? '', Boolean(project))
  const available = Boolean(project?.available)
  const tree = useTree(id, available && tab === 'docs')
  const feedback = useFeedbackList({ source: id }, available)
  const [draft, setDraft] = useState<FeedbackDraft | null>(null)

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
            {project.parent && (
              <Badge variant="outline" size="sm">
                sub-project
              </Badge>
            )}
          </Group>
          {project.summary && <Text c="dimmed">{project.summary}</Text>}
        </Stack>
        <Group gap="xs">
          {available && (
            <Button
              size="xs"
              leftSection={<IconMessagePlus size={14} />}
              onClick={() => setDraft({ kind: 'prompt', source: id, pickDoc: true })}
            >
              Prompt for {project.id}
            </Button>
          )}
          <Button
            size="xs"
            variant="default"
            component={Link}
            to={docUrl(REGISTRY, project.page)}
            leftSection={<IconFileText size={14} />}
          >
            Registry page
          </Button>
        </Group>
      </Group>

      {project.path && !available && (
        <Alert color="orange">
          <Code>{project.path}</Code> isn't on this machine (or is outside the workspace), so its own docs and
          feedback aren't available. The registry page still works.
        </Alert>
      )}

      <SimpleGrid cols={{ base: 1, md: 2 }}>
        <Card withBorder radius="md">
          <Facts project={project} projects={projects} />
        </Card>
        <Card withBorder radius="md">
          <RegistryMap registry={registry.data} focus={project.id} direction="TB" />
        </Card>
      </SimpleGrid>

      {project.children.length > 0 && (
        <Stack gap="xs">
          <Title order={4}>Sub-projects</Title>
          <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
            {project.children.map((c) => {
              const child = projects.get(c)
              return child ? <ProjectCard key={c} project={child} projects={projects} /> : null
            })}
          </SimpleGrid>
        </Stack>
      )}

      <Tabs value={tab} onChange={(v) => setParams(v && v !== 'notes' ? { tab: v } : {}, { replace: true })} keepMounted={false}>
        <Tabs.List>
          <Tabs.Tab value="notes">Cross-project notes</Tabs.Tab>
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
                From <Anchor component={Link} to={docUrl(REGISTRY, project.page)} size="xs">registry/{project.page}</Anchor> (private):
                what this project means to the rest of the system. Its own facts stay in its own docs (the other
                tabs).
              </Text>
              <MarkdownView content={notes.data.content} docPath={project.page} source={REGISTRY} />
            </Stack>
          ) : (
            <Loader size="sm" />
          )}
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
    </Stack>
  )
}
