import {
  Accordion,
  Alert,
  Badge,
  Button,
  Card,
  Grid,
  Group,
  Loader,
  Select,
  Stack,
  Switch,
  Text,
  Textarea,
  Title,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconFileTypePdf, IconMessageCircle, IconSparkles } from '@tabler/icons-react'
import { useMemo, useState, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router'
import { useCreateFeedback, useResponder } from '../api/queries'
import {
  useApproveReportPlan,
  useDiscardReportPlan,
  useFollowBuild,
  useReportCatalog,
  useReportPlan,
  useReportPreflight,
  useSaveReportPlan,
  type CatalogEntry,
  type ReportOptions,
  type ReportPlan,
  type ReportPreset,
} from '../api/reports'
import { SELF } from '../api/types'
import { MarkdownView } from '../docs/MarkdownView'
import { BuildBanner } from './BuildBanner'
import { DEFAULT_OPTIONS, defaultSelection } from './config'
import { SectionChecklist } from './SectionChecklist'
import { SortableSections } from './SortableSections'

const isAuthored = (id: string) => id.startsWith('authored:')

/**
 * The guided report (ADR 0025): you describe what you need, Claude plans the report in a thread,
 * and you review its plan here (reorder, drop sections) before it is built. Claude writes only the
 * sections marked as its own, each citing the sections it drew on.
 */
export function GuidedReport({
  project,
  onClose,
  planOnly = false,
}: {
  project: string
  onClose: () => void
  /** The Reports tab shows only a pending plan (and its build), not the form to ask for one. */
  planOnly?: boolean
}) {
  const plan = useReportPlan(project)
  // The build is followed here, not in the plan view: approving turns the plan into a preset, so
  // the plan (and the view of it) is gone by the time the PDF is ready.
  const [jobId, setJobId] = useState<string | null>(null)
  const job = useFollowBuild(project, jobId)
  if (plan.isPending) return planOnly ? null : <Loader size="sm" />
  if (plan.isError) return <Alert color="red">{plan.error.message}</Alert>
  const wrap = (node: ReactNode) => (planOnly ? <Card withBorder>{node}</Card> : node)
  if (plan.data) return wrap(<ReviewPlan project={project} found={plan.data} job={job} onStarted={setJobId} />)
  if (planOnly && jobId === null) return null
  return wrap(
    <Stack>
      {jobId !== null && (
        <>
          {job?.status === 'running' && (
            <Alert color="blue" icon={<Loader size="xs" />}>
              Building the PDF…
            </Alert>
          )}
          <BuildBanner project={project} job={job} />
          {job?.status !== 'running' && (
            <Text size="sm" c="dimmed">
              {planOnly
                ? "It's saved in the list below."
                : "It's saved under this project's Reports tab. To make another, describe it below."}
            </Text>
          )}
        </>
      )}
      {!planOnly && <AskClaude project={project} onClose={onClose} />}
    </Stack>,
  )
}

function AskClaude({ project, onClose }: { project: string; onClose: () => void }) {
  const [prompt, setPrompt] = useState('')
  const [outline, setOutline] = useState('')
  const create = useCreateFeedback()
  const responder = useResponder()
  const catalog = useReportCatalog(project)
  const navigate = useNavigate()
  const onDemand = responder.data?.enabled ?? false

  // Which sections Claude may use. Until the reader changes it, all of them.
  const entries = catalog.data ?? []
  const everything = defaultSelection(entries)
  const [chosen, setChosen] = useState<string[] | null>(null)
  const scope = chosen ?? everything
  const narrowed = scope.length < everything.length

  const submit = () => {
    const parts = [`Write a report of ${project}.`, `What I need:\n${prompt.trim()}`]
    if (outline.trim()) parts.push(`The structure I'd like:\n${outline.trim()}`)
    if (narrowed)
      parts.push(
        `Use only these sections (catalog ids), and don't read or cite any others:\n${scope.map((id) => `- ${id}`).join('\n')}`,
      )
    create.mutate(
      {
        kind: 'prompt',
        source: SELF,
        body: parts.join('\n\n'),
        anchor: { task: { type: 'report', project } },
      },
      {
        onSuccess: (item) => {
          notifications.show({
            color: 'green',
            title: 'Report requested',
            message: onDemand
              ? "On-demand Claude picks it up in a moment. Its plan and questions arrive in this thread, and the plan shows up here."
              : "It's in Archeion's inbox. Run /inbox there, or switch on On-demand Claude in Settings.",
          })
          onClose()
          navigate(`/feedback/${item.id}`)
        },
      },
    )
  }

  return (
    <Stack>
      <Text size="sm" c="dimmed">
        Claude reads {project}'s sources and drafts a plan: the sections, in order, with a summary and any other
        sections you ask for written by Claude and labeled as such. You review the plan here and build the PDF when
        you're happy. The facts, docs and diagrams are never rewritten.
      </Text>
      <Textarea
        label="What do you need?"
        description="Who reads it, what it is for, what to stress or leave out."
        placeholder="e.g. A one-page-ish overview for the executive team: what it does, how healthy it is, and the risks."
        autosize
        minRows={3}
        maxRows={8}
        maxLength={4000}
        value={prompt}
        onChange={(e) => setPrompt(e.currentTarget.value)}
        required
        data-autofocus
      />
      <Textarea
        label="The structure you'd like (optional)"
        description="An outline in your own words. Claude follows it."
        placeholder={'1. Overview\n2. How it connects to the rest\n3. Data and risks'}
        autosize
        minRows={3}
        maxRows={8}
        maxLength={4000}
        value={outline}
        onChange={(e) => setOutline(e.currentTarget.value)}
      />
      <Accordion variant="contained">
        <Accordion.Item value="scope">
          <Accordion.Control>
            Which sections can Claude use?{' '}
            <Text span size="sm" c="dimmed">
              {catalog.isPending ? '' : narrowed ? `${scope.length} of ${everything.length} chosen` : 'all of them'}
            </Text>
          </Accordion.Control>
          <Accordion.Panel>
            <Text size="sm" c="dimmed" mb="xs">
              Claude plans only from the sections you tick, and cites them. It still writes its own sections (such as the
              summary), but only from these.
            </Text>
            {catalog.isPending ? (
              <Loader size="sm" />
            ) : (
              <SectionChecklist entries={entries} selection={scope} onChange={setChosen} height={260} />
            )}
          </Accordion.Panel>
        </Accordion.Item>
      </Accordion>
      {!onDemand && (
        <Alert color="gray" variant="light">
          On-demand Claude is off, so the request waits for <code>/inbox</code> in Archeion's terminal. Switch it on in{' '}
          <Link to="/settings#on-demand" onClick={onClose}>
            Settings
          </Link>{' '}
          to have each round answered as soon as it arrives.
        </Alert>
      )}
      {create.error && <Alert color="red">{create.error.message}</Alert>}
      <Group justify="flex-end">
        <Button
          leftSection={<IconSparkles size={16} />}
          onClick={submit}
          loading={create.isPending}
          disabled={!prompt.trim() || scope.length === 0}
        >
          Ask Claude to plan the report
        </Button>
      </Group>
    </Stack>
  )
}

function ReviewPlan({
  project,
  found,
  job,
  onStarted,
}: {
  project: string
  found: ReportPlan
  job: ReturnType<typeof useFollowBuild>
  onStarted: (id: string) => void
}) {
  const { plan, thread, updated } = found
  const catalog = useReportCatalog(project)
  const preflight = useReportPreflight(project)
  const save = useSaveReportPlan(project)
  const discard = useDiscardReportPlan(project)
  const approve = useApproveReportPlan(project)
  const building = approve.isPending || job?.status === 'running'

  const catalogById = useMemo(() => new Map((catalog.data ?? []).map((e) => [e.id, e])), [catalog.data])
  const authored = useMemo(
    () => plan.sections.filter((s): s is Extract<typeof s, { body: string }> => 'body' in s),
    [plan.sections],
  )
  const byId = useMemo(() => {
    const map = new Map<string, CatalogEntry>()
    for (const s of plan.sections) {
      const entry: CatalogEntry =
        'body' in s
          ? { id: s.id, group: 'overview', title: s.title, kind: 'text', available: true, reason: null, parent: null }
          : (catalogById.get(s.id) ?? {
              id: s.id,
              group: 'overview',
              title: s.id,
              kind: 'text',
              available: false,
              reason: null,
              parent: null,
            })
      map.set(s.id, entry)
    }
    return map
  }, [plan.sections, catalogById])

  const edit = (next: ReportPreset) =>
    save.mutate(next, {
      onError: (err) => notifications.show({ color: 'red', title: 'Not saved', message: err.message }),
    })
  const setSections = (ids: string[]) => {
    if (ids.length === 0) {
      notifications.show({ color: 'orange', title: 'A report needs a section', message: 'Discard the plan instead.' })
      return
    }
    // A section that isn't in the plan yet was ticked in the checklist: a plain catalog section.
    const by = new Map(plan.sections.map((s) => [s.id, s]))
    edit({ ...plan, sections: ids.map((id) => by.get(id) ?? { id }) })
  }
  const setOptions = (options: ReportOptions) => edit({ ...plan, options })
  const options = { ...DEFAULT_OPTIONS, ...plan.options }

  const build = () =>
    approve.mutate(undefined, {
      onSuccess: (started) => onStarted(started.id),
      onError: (err) => notifications.show({ color: 'red', title: 'Could not build the report', message: err.message }),
    })

  const gone = plan.sections.filter((s) => !('body' in s) && catalogById.size > 0 && !catalogById.get(s.id)?.available)

  return (
    <Stack>
      <Group justify="space-between" align="flex-start">
        <Stack gap={2}>
          <Title order={5}>{plan.title || plan.name}</Title>
          <Text size="xs" c="dimmed">
            Claude's plan, saved {updated.replace('T', ' ').replace('Z', ' UTC')}. Reorder or drop sections below, or ask
            for changes in the thread.
          </Text>
        </Stack>
        {thread !== null && (
          <Button
            size="xs"
            variant="default"
            component={Link}
            to={`/feedback/${thread}`}
            leftSection={<IconMessageCircle size={14} />}
          >
            Open the thread
          </Button>
        )}
      </Group>

      {(plan.prompt || plan.outline) && (
        <Accordion variant="contained">
          <Accordion.Item value="ask">
            <Accordion.Control>What you asked for</Accordion.Control>
            <Accordion.Panel>
              <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
                {plan.prompt}
              </Text>
              {plan.outline && (
                <Text size="sm" c="dimmed" mt="xs" style={{ whiteSpace: 'pre-wrap' }}>
                  {plan.outline}
                </Text>
              )}
            </Accordion.Panel>
          </Accordion.Item>
        </Accordion>
      )}

      {preflight.data && preflight.data.problems.length > 0 && (
        <Alert color="orange" title="A report can't be built yet">
          {preflight.data.problems.map((p) => (
            <Text key={p} size="sm">
              {p}
            </Text>
          ))}
        </Alert>
      )}
      {gone.length > 0 && (
        <Alert color="orange" title="Some sections lost their source">
          {gone.map((s) => s.id).join(', ')}: building will be refused until they're dropped or their source is back.
        </Alert>
      )}

      <Accordion variant="contained">
        <Accordion.Item value="add">
          <Accordion.Control>Add or remove sections</Accordion.Control>
          <Accordion.Panel>
            <Text size="sm" c="dimmed" mb="xs">
              Tick a section to add it to the plan (at the end, or after its map), untick it to take it out. What Claude
              wrote stays until you ask for it to change in the thread.
            </Text>
            <SectionChecklist
              entries={catalog.data ?? []}
              selection={plan.sections.map((s) => s.id)}
              onChange={setSections}
              height={240}
            />
          </Accordion.Panel>
        </Accordion.Item>
      </Accordion>

      <Grid gap="md">
        <Grid.Col span={{ base: 12, md: 7 }}>
          <Group justify="space-between" mb="xs">
            <Title order={6}>Sections, in order</Title>
            <Badge variant="light">{plan.sections.length} sections</Badge>
          </Group>
          <SortableSections
            selection={plan.sections.map((s) => s.id)}
            byId={byId}
            onChange={setSections}
            authored={new Set(plan.sections.filter((s) => isAuthored(s.id)).map((s) => s.id))}
          />
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 5 }}>
          <Title order={6} mb="xs">
            Written by Claude
          </Title>
          {authored.length === 0 ? (
            <Text size="sm" c="dimmed">
              Nothing: this plan only uses sections as they are.
            </Text>
          ) : (
            <Accordion variant="separated" multiple>
              {authored.map((s) => (
                <Accordion.Item key={s.id} value={s.id}>
                  <Accordion.Control>{s.title}</Accordion.Control>
                  <Accordion.Panel>
                    <MarkdownView content={s.body} docPath="README.md" compact />
                    <Text size="xs" c="dimmed" mt="xs">
                      Sources: {s.cites.map((c) => catalogById.get(c)?.title ?? c).join('; ')}
                    </Text>
                  </Accordion.Panel>
                </Accordion.Item>
              ))}
            </Accordion>
          )}
        </Grid.Col>
      </Grid>

      <Group>
        <Select
          label="Page size"
          data={['A4', 'Letter']}
          allowDeselect={false}
          value={options.page_size}
          onChange={(v) => v && setOptions({ ...options, page_size: v as ReportOptions['page_size'] })}
          w={110}
        />
        <Select
          label="Orientation"
          data={[
            { value: 'portrait', label: 'Portrait' },
            { value: 'landscape', label: 'Landscape' },
          ]}
          allowDeselect={false}
          value={options.orientation}
          onChange={(v) => v && setOptions({ ...options, orientation: v as ReportOptions['orientation'] })}
          w={130}
        />
        <Switch
          mt="lg"
          label="Cover page"
          checked={options.cover}
          onChange={(e) => setOptions({ ...options, cover: e.currentTarget.checked })}
        />
        <Switch
          mt="lg"
          label="Contents"
          checked={options.toc}
          onChange={(e) => setOptions({ ...options, toc: e.currentTarget.checked })}
        />
      </Group>

      <BuildBanner project={project} job={job} />

      <Group justify="space-between">
        <Button
          variant="subtle"
          color="red"
          loading={discard.isPending}
          disabled={building}
          onClick={() => {
            if (window.confirm('Discard this plan? Claude would have to plan the report again.')) discard.mutate()
          }}
        >
          Discard plan
        </Button>
        <Button
          leftSection={<IconFileTypePdf size={16} />}
          onClick={build}
          loading={building}
          disabled={building || save.isPending || gone.length > 0 || preflight.data?.ok === false}
        >
          {job?.status === 'running' ? 'Building the PDF…' : 'Approve and build'}
        </Button>
      </Group>
    </Stack>
  )
}
