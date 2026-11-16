import {
  Alert,
  Anchor,
  Badge,
  Breadcrumbs,
  Button,
  Card,
  Code,
  Drawer,
  Group,
  List,
  Loader,
  NavLink,
  SegmentedControl,
  Select,
  SimpleGrid,
  Slider,
  Stack,
  Switch,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { IconMicroscope, IconSearch } from '@tabler/icons-react'
import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { useSnapshot, useSnapshots, useStudyDiff } from '../api/queries'
import { normalizeModel, type SnapshotRow, type StudyModel } from '../api/study'
import { REGISTRY, SELF, type Project, type StudyElementKind } from '../api/types'
import { docUrl } from '../docs/links'
import { MarkdownView } from '../docs/MarkdownView'
import { MermaidBlock } from '../docs/MermaidBlock'
import { FeedbackForm, type FeedbackDraft } from '../feedback/FeedbackForm'
import { Cites } from './Cites'
import { ComponentDetails } from './ComponentDetails'
import { StartStudyButton } from './StartStudy'
import { activity, componentMap, erDiagram, sequence, stateDiagram } from './mermaid'
import { componentGraph, foldedAtDepth } from './graph'
import { LazyGraph } from '../graph/LazyGraph'

const VIEWS = [
  ['overview', 'Overview'],
  ['components', 'Components'],
  ['flows', 'Flows'],
  ['logic', 'Logic'],
  ['data', 'Data'],
  ['states', 'States'],
  ['interfaces', 'Interfaces'],
  ['findings', 'Findings'],
  ['notes', 'Notes'],
  ['changes', 'Changes'],
] as const
type View = (typeof VIEWS)[number][0]

const SEVERITY_COLOR = { info: 'blue', warn: 'orange', risk: 'red' } as const

/** How far behind the project a snapshot is. */
export function Staleness({ row }: { row: Pick<SnapshotRow, 'commits_since' | 'dirty'> }) {
  return (
    <Group gap={4}>
      {row.commits_since === null ? (
        <Badge variant="light" color="gray" title="The studied commit isn't in the project's history here">
          age unknown
        </Badge>
      ) : row.commits_since === 0 ? (
        <Badge variant="light" color="green">
          current
        </Badge>
      ) : (
        <Badge variant="light" color="orange">
          {row.commits_since} commit{row.commits_since === 1 ? '' : 's'} behind
        </Badge>
      )}
      {row.dirty && (
        <Badge variant="outline" color="gray" title="The study saw uncommitted changes">
          uncommitted code
        </Badge>
      )}
    </Group>
  )
}

export function StudyTab({ project }: { project: Project }) {
  const [params, setParams] = useSearchParams()
  const snapshots = useSnapshots(project.id)
  // The latest saved snapshot is shown first; a draft (ADR 0020) only when there's nothing else.
  const latestId = (snapshots.data?.find((s) => !s.draft) ?? snapshots.data?.[0])?.id ?? null
  const snapId = params.get('snap') ?? latestId
  const snap = useSnapshot(project.id, snapId)
  const [draft, setDraft] = useState<FeedbackDraft | null>(null)
  const view = (params.get('view') as View | null) ?? 'overview'

  const set = (changes: Record<string, string | null>) =>
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        for (const [k, v] of Object.entries(changes)) {
          if (v === null) next.delete(k)
          else next.set(k, v)
        }
        return next
      },
      { replace: true },
    )

  const model = useMemo(() => normalizeModel(snap.data?.model), [snap.data])

  if (snapshots.isPending) return <Loader size="sm" />
  if (snapshots.isError) return <Alert color="red">{snapshots.error.message}</Alert>
  if (!snapshots.data?.length) {
    return (
      <Stack gap="sm" align="flex-start">
        <Text>
          No study of {project.id} yet. A study reads the project's code and draws its components, flows, data
          and states here (ADR 0019).
        </Text>
        <Text size="sm" c="dimmed">
          Start it here as a conversation with Claude, or run <Code>/study {project.id}</Code> in Archeion's terminal
          session.
        </Text>
        <StartStudyButton project={project.id} />
      </Stack>
    )
  }

  const row = snapshots.data.find((s) => s.id === snapId) ?? snapshots.data[0]
  const inProgress = snapshots.data.find((s) => s.draft)
  const counts = row.counts
  const countOf: Partial<Record<View, number>> = {
    components: counts.components,
    flows: counts.flows,
    logic: counts.activities,
    data: counts.entities,
    states: counts.states,
    interfaces: counts.exposes + counts.calls,
    findings: counts.findings,
  }

  const ask = (element: string, kind: StudyElementKind) =>
    setDraft({
      kind: 'prompt',
      source: SELF,
      anchor: { study: { project: project.id, snapshot: row.id, element, kind } },
    })

  return (
    <Stack gap="sm">
      <Group justify="space-between" align="flex-end">
        <Group gap="sm" align="flex-end">
          <Select
            label="Snapshot"
            size="xs"
            w={240}
            allowDeselect={false}
            value={row.id}
            onChange={(v) => set({ snap: v === latestId ? null : v })}
            data={snapshots.data.map((s) => ({
              value: s.id,
              label: s.draft
                ? `Draft (in progress)${s.valid ? '' : ' ⚠'}`
                : `${s.date} · ${(s.commit ?? '').slice(0, 7)}${s.id === latestId ? ' (latest)' : ''}${s.valid ? '' : ' ⚠'}`,
            }))}
          />
          <Staleness row={row} />
        </Group>
        <Group gap="xs">
          <Anchor
            component={Link}
            size="xs"
            to={docUrl(REGISTRY, `studies/${project.id}/${row.id}/notes.md`)}
            hidden={!row.notes}
          >
            notes in the registry
          </Anchor>
          {row.thread && !row.draft && (
            <Anchor component={Link} size="xs" to={`/feedback/${row.thread}`}>
              its conversation
            </Anchor>
          )}
          {!inProgress && <StartStudyButton project={project.id} refresh variant="default" />}
        </Group>
      </Group>

      {inProgress && (
        <Alert color="blue" icon={<IconMicroscope size={18} />} title="A study is in progress">
          <Group justify="space-between" gap="xs">
            <Text size="sm">
              Claude keeps its work so far as a draft between rounds.{' '}
              {inProgress.thread ? (
                <>
                  Answer its questions in{' '}
                  <Anchor component={Link} to={`/feedback/${inProgress.thread}`} size="sm">
                    the conversation (#{inProgress.thread})
                  </Anchor>
                  , and say when it's done.
                </>
              ) : (
                "Say when it's done in its conversation."
              )}
            </Text>
            {row.id !== inProgress.id && (
              <Button size="xs" variant="light" onClick={() => set({ snap: inProgress.id })}>
                View the draft
              </Button>
            )}
          </Group>
        </Alert>
      )}

      {!row.valid && (
        <Alert color="orange" title="This snapshot doesn't validate">
          {row.problems.join('; ')}
        </Alert>
      )}

      <SegmentedControl
        size="xs"
        value={view}
        onChange={(v) => set({ view: v === 'overview' ? null : v, item: null, focus: null })}
        data={VIEWS.map(([value, text]) => ({
          value,
          label: countOf[value] !== undefined ? `${text} ${countOf[value]}` : text,
          disabled:
            (countOf[value] === 0 && value !== 'components') ||
            (value === 'notes' && !row.notes) ||
            (value === 'changes' && snapshots.data.length < 2),
        }))}
        style={{ alignSelf: 'flex-start', flexWrap: 'wrap' }}
      />

      {snap.isPending && <Loader size="sm" />}
      {snap.isError && <Alert color="red">{snap.error.message}</Alert>}
      {model && (
        <StudyView
          view={view}
          model={model}
          project={project}
          snapshots={snapshots.data}
          current={row}
          notes={snap.data?.notes_text ?? ''}
          params={params}
          set={set}
          ask={ask}
        />
      )}
      <FeedbackForm draft={draft} onClose={() => setDraft(null)} />
    </Stack>
  )
}

type ViewProps = {
  model: StudyModel
  project: Project
  snapshots: SnapshotRow[]
  current: SnapshotRow
  notes: string
  params: URLSearchParams
  set: (changes: Record<string, string | null>) => void
  ask: (element: string, kind: StudyElementKind) => void
}

function StudyView({ view, ...props }: ViewProps & { view: View }) {
  switch (view) {
    case 'components':
      return <ComponentsView {...props} />
    case 'flows':
      return <FlowsView {...props} />
    case 'logic':
      return <LogicView {...props} />
    case 'data':
      return <DataView {...props} />
    case 'states':
      return <StatesView {...props} />
    case 'interfaces':
      return <InterfacesView {...props} />
    case 'findings':
      return <FindingsView {...props} />
    case 'notes':
      return <MarkdownView content={props.notes} docPath={`studies/${props.project.id}/${props.current.id}/notes.md`} source={REGISTRY} />
    case 'changes':
      return <ChangesView {...props} />
    default:
      return <OverviewView {...props} />
  }
}

// --- overview ---------------------------------------------------------------------------------

function OverviewView({ model, set }: ViewProps) {
  const m = model.meta
  const cards: [string, string, number][] = [
    ['components', 'Components', model.components.length],
    ['flows', 'Flows', model.flows.length],
    ['logic', 'Activities', model.activities.length],
    ['data', 'Entities', model.entities.length],
    ['states', 'State machines', model.states.length],
    ['interfaces', 'Endpoints exposed', model.interfaces.exposes.length],
    ['interfaces', 'Outgoing calls', model.interfaces.calls.length],
    ['findings', 'Findings', model.findings.length],
  ]
  const risks = model.findings.filter((f) => f.severity !== 'info')
  return (
    <Stack gap="md">
      {m.summary && <Text>{m.summary}</Text>}
      <Group gap={4}>
        {(m.stack ?? []).map((s) => (
          <Badge key={s} variant="outline">
            {s}
          </Badge>
        ))}
      </Group>
      <Text size="sm" c="dimmed">
        Studied {m.date} at commit <Code>{m.commit.slice(0, 10)}</Code>
        {m.coverage?.files_read !== undefined &&
          ` · read ${m.coverage.files_read}${m.coverage.files_total ? ` of ${m.coverage.files_total}` : ''} files`}
        {m.refreshed_from && ` · refreshed from ${m.refreshed_from}`}
        {m.coverage?.note && ` · ${m.coverage.note}`}
      </Text>
      <SimpleGrid cols={{ base: 2, sm: 4 }}>
        {cards.map(([view, title, n]) => (
          <Card
            key={title}
            withBorder
            padding="sm"
            radius="md"
            style={{ cursor: n ? 'pointer' : undefined, opacity: n ? 1 : 0.5 }}
            onClick={() => n && set({ view })}
          >
            <Text size="xl" fw={600}>
              {n}
            </Text>
            <Text size="xs" c="dimmed">
              {title}
            </Text>
          </Card>
        ))}
      </SimpleGrid>
      {risks.length > 0 && (
        <Stack gap={4}>
          <Title order={5}>Findings to look at</Title>
          {risks.slice(0, 5).map((f) => (
            <Group key={f.id} gap="xs" wrap="nowrap">
              <Badge size="sm" color={SEVERITY_COLOR[f.severity]}>
                {f.severity}
              </Badge>
              <Text size="sm">{f.title}</Text>
            </Group>
          ))}
        </Stack>
      )}
      {model.questions.length > 0 && (
        <Stack gap={4}>
          <Title order={5}>Open questions</Title>
          <List size="sm">
            {model.questions.map((q) => (
              <List.Item key={q}>{q}</List.Item>
            ))}
          </List>
        </Stack>
      )}
    </Stack>
  )
}

// --- components ------------------------------------------------------------------------------

function ComponentsView({ model, params, set, ask }: ViewProps) {
  const [depth, setDepth] = useState(2)
  const [showImports, setShowImports] = useState(false)
  const [query, setQuery] = useState('')
  const [mode, setMode] = useState<'graph' | 'diagram'>('graph')
  const focus = params.get('focus')
  const selected = params.get('item')
  const byId = new Map(model.components.map((c) => [c.id, c]))
  const hideKinds = showImports ? [] : ['imports']
  const code = mode === 'diagram' ? componentMap(model, { focus, depth, hideKinds }) : ''
  const graph = componentGraph(model, { focus, hideKinds })
  const hasKids = new Set(model.components.map((c) => c.parent).filter(Boolean))
  const trail: string[] = []
  for (let cur = focus ? byId.get(focus) : undefined; cur; cur = cur.parent ? byId.get(cur.parent) : undefined) {
    trail.unshift(cur.id)
    if (trail.length > 20) break
  }
  const q = query.trim().toLowerCase()
  const listed = model.components.filter(
    (c) => !q || c.name.toLowerCase().includes(q) || c.id.toLowerCase().includes(q) || c.kind.includes(q),
  )
  if (model.components.length === 0) return <Text c="dimmed">This study has no components.</Text>

  return (
    <Stack gap="sm">
      <Group justify="space-between">
        <Breadcrumbs>
          <Anchor component="button" type="button" size="sm" onClick={() => set({ focus: null })}>
            Whole project
          </Anchor>
          {trail.map((id) => (
            <Anchor key={id} component="button" type="button" size="sm" onClick={() => set({ focus: id })}>
              {byId.get(id)?.name ?? id}
            </Anchor>
          ))}
        </Breadcrumbs>
        <Group gap="md">
          <Group gap={6}>
            <Text size="xs" c="dimmed">
              Depth
            </Text>
            <Slider w={100} size="sm" min={0} max={4} step={1} value={depth} onChange={setDepth} label={null} />
          </Group>
          <Switch size="xs" label="Imports" checked={showImports} onChange={(e) => setShowImports(e.currentTarget.checked)} />
          <SegmentedControl
            size="xs"
            value={mode}
            onChange={(v) => setMode(v as 'graph' | 'diagram')}
            data={[
              { value: 'graph', label: 'Interactive' },
              { value: 'diagram', label: 'Mermaid' },
            ]}
          />
        </Group>
      </Group>
      <Card withBorder radius="md">
        {mode === 'graph' ? (
          graph.nodes.length ? (
            <LazyGraph
              key={`${focus ?? ''}|${depth}|${showImports}`}
              graph={graph}
              height={520}
              minimap
              selected={selected}
              initialFolded={foldedAtDepth(graph, depth)}
              onSelect={(id) => set({ item: id })}
              onOpen={(id) => (hasKids.has(id) ? set({ focus: id, item: null }) : set({ item: id }))}
            />
          ) : (
            <Text c="dimmed">Nothing inside to draw.</Text>
          )
        ) : code ? (
          <MermaidBlock code={code} />
        ) : (
          <Text c="dimmed">Nothing inside to draw.</Text>
        )}
        <Text size="xs" c="dimmed" mt="xs">
          Boxes inside boxes are parts of a component: fold them with their arrow. Click a box for its details,
          double-click to look inside it, hover to light up what it's linked to. Solid arrows are calls, thick ones
          database writes and SQL, dashed ones HTTP and events, dotted ones imports. Dashed boxes sit outside the
          part you're looking at.
        </Text>
      </Card>
      <TextInput
        size="xs"
        placeholder="Find a component"
        leftSection={<IconSearch size={14} />}
        value={query}
        onChange={(e) => setQuery(e.currentTarget.value)}
        w={280}
      />
      <Table striped highlightOnHover verticalSpacing={4}>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Component</Table.Th>
            <Table.Th>Kind</Table.Th>
            <Table.Th>Part of</Table.Th>
            <Table.Th>Summary</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {listed.map((c) => (
            <Table.Tr key={c.id} style={{ cursor: 'pointer' }} onClick={() => set({ item: c.id })}>
              <Table.Td>
                <Text size="sm" fw={500}>
                  {c.name}
                </Text>
              </Table.Td>
              <Table.Td>
                <Badge size="sm" variant="light">
                  {c.kind}
                </Badge>
              </Table.Td>
              <Table.Td>
                <Text size="sm">{c.parent ? (byId.get(c.parent)?.name ?? c.parent) : ''}</Text>
              </Table.Td>
              <Table.Td>
                <Text size="sm" lineClamp={2}>
                  {c.summary}
                </Text>
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
      <Drawer opened={Boolean(selected)} onClose={() => set({ item: null })} position="right" size="md" title="Component">
        {selected && (
          <ComponentDetails
            model={model}
            id={selected}
            onSelect={(id) => set({ item: id })}
            onFocus={(id) => set({ focus: id, item: null })}
            onAsk={(id) => ask(id, 'component')}
          />
        )}
      </Drawer>
    </Stack>
  )
}

// --- lists of diagrams: flows, logic, states -------------------------------------------------

function Picker<T extends { id: string; title: string }>({
  items,
  selected,
  onSelect,
}: {
  items: T[]
  selected: string
  onSelect: (id: string) => void
}) {
  return (
    <Stack gap={0}>
      {items.map((it) => (
        <NavLink key={it.id} label={it.title} active={it.id === selected} onClick={() => onSelect(it.id)} />
      ))}
    </Stack>
  )
}

function DiagramList<T extends { id: string; title: string; summary?: string; cites?: import('../api/study').Cite[] }>({
  items,
  params,
  set,
  ask,
  what,
  draw,
  extra,
}: Pick<ViewProps, 'params' | 'set' | 'ask'> & {
  items: T[]
  what: StudyElementKind
  draw: (item: T) => string
  extra?: (item: T) => React.ReactNode
}) {
  const current = items.find((i) => i.id === params.get('item')) ?? items[0]
  if (!current) return <Text c="dimmed">None in this study.</Text>
  return (
    <SimpleGrid cols={{ base: 1, md: 4 }} spacing="md">
      <Card withBorder radius="md" padding="xs" style={{ gridColumn: 'span 1' }}>
        <Picker items={items} selected={current.id} onSelect={(id) => set({ item: id })} />
      </Card>
      <Stack gap="sm" style={{ gridColumn: 'span 3' }}>
        <Group justify="space-between">
          <Title order={4}>{current.title}</Title>
          <Button size="xs" variant="default" onClick={() => ask(current.id, what)}>
            Ask Claude about this
          </Button>
        </Group>
        {extra?.(current)}
        {current.summary && <Text size="sm">{current.summary}</Text>}
        <Card withBorder radius="md">
          <MermaidBlock code={draw(current)} />
        </Card>
        <Cites cites={current.cites} />
      </Stack>
    </SimpleGrid>
  )
}

function FlowsView({ model, ...rest }: ViewProps) {
  return (
    <DiagramList
      {...rest}
      items={model.flows}
      what="flow"
      draw={(f) => sequence(f, model.components)}
      extra={(f) =>
        f.trigger && (
          <Text size="sm" c="dimmed">
            Starts with <Code>{f.trigger}</Code>
          </Text>
        )
      }
    />
  )
}

function LogicView({ model, ...rest }: ViewProps) {
  return <DiagramList {...rest} items={model.activities} what="activity" draw={activity} />
}

function StatesView({ model, ...rest }: ViewProps) {
  const entities = new Map(model.entities.map((e) => [e.id, e.name]))
  return (
    <DiagramList
      {...rest}
      items={model.states}
      what="state machine"
      draw={stateDiagram}
      extra={(m) =>
        m.entity && (
          <Text size="sm" c="dimmed">
            The lifecycle of <Code>{entities.get(m.entity) ?? m.entity}</Code>
          </Text>
        )
      }
    />
  )
}

// --- data -------------------------------------------------------------------------------------

function DataView({ model }: ViewProps) {
  const stores = new Map(model.components.map((c) => [c.id, c.name]))
  const code = useMemo(() => erDiagram(model.entities), [model])
  return (
    <Stack gap="md">
      <Card withBorder radius="md">
        <MermaidBlock code={code} />
      </Card>
      <SimpleGrid cols={{ base: 1, md: 2 }}>
        {model.entities.map((e) => (
          <Card key={e.id} withBorder radius="md" padding="sm">
            <Group gap="xs" mb={4}>
              <Text fw={600}>{e.name}</Text>
              {e.store && (
                <Badge size="sm" variant="light">
                  {stores.get(e.store) ?? e.store}
                </Badge>
              )}
            </Group>
            {e.summary && (
              <Text size="sm" mb={4}>
                {e.summary}
              </Text>
            )}
            <Table verticalSpacing={2} fz="xs">
              <Table.Tbody>
                {e.fields.map((f) => (
                  <Table.Tr key={f.name}>
                    <Table.Td>
                      <Code>{f.name}</Code>
                    </Table.Td>
                    <Table.Td>{f.type}</Table.Td>
                    <Table.Td>
                      {[f.pk && 'PK', f.fk && `FK → ${f.fk}`, f.nullable && 'nullable'].filter(Boolean).join(' · ')}
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
            <Cites cites={e.cites} />
          </Card>
        ))}
      </SimpleGrid>
    </Stack>
  )
}

// --- interfaces --------------------------------------------------------------------------------

function InterfacesView({ model, set }: ViewProps) {
  const names = new Map(model.components.map((c) => [c.id, c.name]))
  const comp = (id?: string) =>
    id ? (
      <Anchor component="button" type="button" size="sm" onClick={() => set({ view: 'components', item: id })}>
        {names.get(id) ?? id}
      </Anchor>
    ) : null
  return (
    <Stack gap="md">
      <Title order={5}>Exposes</Title>
      {model.interfaces.exposes.length === 0 ? (
        <Text c="dimmed" size="sm">
          Nothing exposed.
        </Text>
      ) : (
        <Table striped verticalSpacing={4}>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Kind</Table.Th>
              <Table.Th>Endpoint</Table.Th>
              <Table.Th>Handled by</Table.Th>
              <Table.Th>Summary</Table.Th>
              <Table.Th>Source</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {model.interfaces.exposes.map((x) => (
              <Table.Tr key={x.id}>
                <Table.Td>{x.kind}</Table.Td>
                <Table.Td>
                  <Code>{[x.method, x.path ?? x.name].filter(Boolean).join(' ')}</Code>
                </Table.Td>
                <Table.Td>{comp(x.handler)}</Table.Td>
                <Table.Td>
                  <Text size="sm">{x.summary}</Text>
                </Table.Td>
                <Table.Td>
                  <Cites cites={x.cites} title="" />
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
      <Title order={5}>Calls</Title>
      {model.interfaces.calls.length === 0 ? (
        <Text c="dimmed" size="sm">
          No outgoing calls.
        </Text>
      ) : (
        <Table striped verticalSpacing={4}>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Kind</Table.Th>
              <Table.Th>Target</Table.Th>
              <Table.Th>Endpoint</Table.Th>
              <Table.Th>From</Table.Th>
              <Table.Th>Source</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {model.interfaces.calls.map((x) => (
              <Table.Tr key={x.id}>
                <Table.Td>{x.kind}</Table.Td>
                <Table.Td>
                  {x.target_project ? (
                    <Anchor component={Link} to={`/projects/${encodeURIComponent(x.target_project)}?tab=study`} size="sm">
                      {x.target_project}
                    </Anchor>
                  ) : (
                    <Code>{x.target_url ?? (x.port ? `port ${x.port}` : '?')}</Code>
                  )}
                </Table.Td>
                <Table.Td>
                  <Code>{[x.method, x.path].filter(Boolean).join(' ')}</Code>
                </Table.Td>
                <Table.Td>{comp(x.from)}</Table.Td>
                <Table.Td>
                  <Cites cites={x.cites} title="" />
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Stack>
  )
}

// --- findings ----------------------------------------------------------------------------------

function FindingsView({ model, ask }: ViewProps) {
  const order = { risk: 0, warn: 1, info: 2 }
  const sorted = [...model.findings].sort((a, b) => order[a.severity] - order[b.severity])
  return (
    <Stack gap="sm">
      {sorted.map((f) => (
        <Card key={f.id} withBorder radius="md" padding="sm">
          <Group justify="space-between" wrap="nowrap">
            <Group gap="xs">
              <Badge color={SEVERITY_COLOR[f.severity]}>{f.severity}</Badge>
              <Text fw={500}>{f.title}</Text>
              {f.rule && (
                <Badge variant="outline" size="sm">
                  {f.rule}
                </Badge>
              )}
            </Group>
            <Button size="xs" variant="subtle" onClick={() => ask(f.id, 'finding')}>
              Ask Claude
            </Button>
          </Group>
          {f.detail && (
            <Text size="sm" mt={4}>
              {f.detail}
            </Text>
          )}
          <Cites cites={f.cites} />
        </Card>
      ))}
    </Stack>
  )
}

// --- changes between snapshots -----------------------------------------------------------------

const SECTION_TITLES: Record<string, string> = {
  components: 'Components',
  relations: 'Relations',
  exposes: 'Exposed',
  calls: 'Outgoing calls',
  entities: 'Entities',
  flows: 'Flows',
  activities: 'Activities',
  states: 'State machines',
  findings: 'Findings',
}

function ChangesView({ project, snapshots, current, params, set }: ViewProps) {
  const older = snapshots.filter((s) => s.id !== current.id)
  const idx = snapshots.findIndex((s) => s.id === current.id)
  const fallback = snapshots[idx + 1]?.id ?? older[0]?.id ?? null
  const against = params.get('against') ?? fallback
  const diff = useStudyDiff(project.id, against, current.id)
  return (
    <Stack gap="sm">
      <Group gap="xs" align="flex-end">
        <Select
          label="Compare with"
          size="xs"
          w={240}
          allowDeselect={false}
          value={against}
          onChange={(v) => set({ against: v })}
          data={older.map((s) => ({ value: s.id, label: `${s.date} · ${(s.commit ?? '').slice(0, 7)}` }))}
        />
        <Text size="xs" c="dimmed">
          Matched by element id. Moved line numbers don't count as changes.
        </Text>
      </Group>
      {diff.isPending && against && <Loader size="sm" />}
      {diff.isError && <Alert color="red">{diff.error.message}</Alert>}
      {diff.data && (
        <SimpleGrid cols={{ base: 1, md: 2 }}>
          {Object.entries(diff.data.sections)
            .filter(([, s]) => s.added.length + s.removed.length + s.changed.length > 0)
            .map(([name, s]) => (
              <Card key={name} withBorder radius="md" padding="sm">
                <Text fw={600} mb={4}>
                  {SECTION_TITLES[name] ?? name}
                </Text>
                <List size="sm" spacing={2}>
                  {s.added.map((e) => (
                    <List.Item key={`a-${e.id}`} icon={<Badge size="xs" color="green">added</Badge>}>
                      {e.label}
                    </List.Item>
                  ))}
                  {s.removed.map((e) => (
                    <List.Item key={`r-${e.id}`} icon={<Badge size="xs" color="red">removed</Badge>}>
                      {e.label}
                    </List.Item>
                  ))}
                  {s.changed.map((e) => (
                    <List.Item key={`c-${e.id}`} icon={<Badge size="xs" color="blue">changed</Badge>}>
                      {e.label}{' '}
                      <Text span size="xs" c="dimmed">
                        ({e.fields?.join(', ')})
                      </Text>
                    </List.Item>
                  ))}
                </List>
              </Card>
            ))}
        </SimpleGrid>
      )}
      {diff.data &&
        Object.values(diff.data.sections).every((s) => s.added.length + s.removed.length + s.changed.length === 0) && (
          <Text c="dimmed">No differences.</Text>
        )}
    </Stack>
  )
}
