import {
  Alert,
  Badge,
  Button,
  Card,
  Code,
  Group,
  List,
  Loader,
  Modal,
  SegmentedControl,
  Select,
  Stack,
  Table,
  Text,
  Textarea,
  TextInput,
  Title,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconCheck, IconCompass, IconSend } from '@tabler/icons-react'
import { useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import {
  useApproveDesign,
  useCreateFeedback,
  useBuiltVsDesigned,
  useDesign,
  useDesignImpact,
  useDesignApproval,
  useDesignPreflight,
  useDesigns,
  useHandoffDesign,
  useResponder,
  useSetDesignStage,
} from '../api/queries'
import {
  asStudyModel,
  STAGES,
  WORKING_STAGES,
  type DesignFull,
  type DesignRow,
  type DesignStage,
  type Impact,
  type PreflightProblem,
} from '../api/design'
import { REGISTRY, SELF } from '../api/types'
import { docUrl } from '../docs/links'
import { MarkdownView } from '../docs/MarkdownView'
import { MermaidBlock } from '../docs/MermaidBlock'
import { Checklist } from './Checklist'
import { RoadmapView } from './RoadmapView'
import { LazyGraph } from '../graph/LazyGraph'
import { componentGraph } from '../study/graph'
import { SequenceView } from '../study/SequenceView'
import { ViewSwitch } from '../study/ViewSwitch'
import { componentMap, erDiagram, sequence } from '../study/mermaid'

const VIEWS = [
  ['brief', 'Brief'],
  ['architecture', 'Architecture'],
  ['plan', 'Plan'],
  ['checklist', 'Checklist'],
  ['roadmap', 'Roadmap'],
  ['decisions', 'Decisions'],
  ['questions', 'Open questions'],
  ['impact', 'Impact on others'],
  ['built', 'Built vs designed'],
  ['revisions', 'Revisions'],
] as const
type View = (typeof VIEWS)[number][0]

const STAGE_COLOR: Record<DesignStage, string> = {
  brief: 'gray',
  architecture: 'blue',
  plan: 'violet',
  approved: 'green',
  'handed off': 'teal',
}

export function StageBadge({ stage, size = 'sm' }: { stage: DesignStage; size?: 'xs' | 'sm' }) {
  return (
    <Badge size={size} variant="light" color={STAGE_COLOR[stage] ?? 'gray'}>
      {stage}
    </Badge>
  )
}

const SEVERITY_COLOR = { block: 'red', warn: 'orange', info: 'blue' } as const

function Problems({ problems }: { problems: PreflightProblem[] }) {
  if (problems.length === 0) return null
  return (
    <Stack gap="xs">
      {problems.map((p) => (
        <Alert key={p.code} color={SEVERITY_COLOR[p.severity]} variant="light" py="xs">
          <Text size="sm">{p.message}</Text>
          {p.fix && (
            <Text size="xs" c="dimmed" mt={2}>
              Fix: <Code>{p.fix}</Code>. Claude offers this itself when you ask it to design.
            </Text>
          )}
        </Alert>
      ))}
    </Stack>
  )
}

/** A document that holds only its headings counts as not written yet. */
const isBlank = (text: string | undefined) => !text || text.replace(/^#.*$/gm, '').trim().length === 0

/** Starts a design conversation (ADR 0022): a thread for Archeion anchored to the task. */
export function StartDesignButton({
  project,
  slug,
  existing,
  variant = 'filled',
}: {
  project: string
  slug: string
  existing: string[]
  variant?: 'filled' | 'default'
}) {
  const [open, setOpen] = useState(false)
  const [purpose, setPurpose] = useState('')
  const [name, setName] = useState(slug)
  const create = useCreateFeedback()
  const responder = useResponder()
  const navigate = useNavigate()
  const onDemand = responder.data?.enabled ?? false
  const chosen = name.trim().toLowerCase()
  const valid = /^[a-z0-9][a-z0-9-]{0,39}$/.test(chosen)
  const first = existing.length === 0

  const submit = () => {
    const ask = first || existing.includes(chosen) ? `Design ${project}.` : `Design ${project}: a new design '${chosen}'.`
    const body = purpose.trim() ? `${ask}\n\n${purpose.trim()}` : ask
    create.mutate(
      { kind: 'prompt', source: SELF, body, anchor: { task: { type: 'design', project, slug: chosen } } },
      {
        onSuccess: (item) => {
          setOpen(false)
          setPurpose('')
          notifications.show({
            color: 'green',
            title: 'Design started',
            message: onDemand
              ? 'On-demand Claude picks it up in a moment. Its questions and the first draft arrive in this thread.'
              : "It's in Archeion's inbox. Run /inbox there, or switch on On-demand Claude in Settings.",
          })
          navigate(`/feedback/${item.id}`)
        },
      },
    )
  }

  return (
    <>
      <Button size="xs" variant={variant} leftSection={<IconCompass size={14} />} onClick={() => setOpen(true)}>
        {first ? `Ask Claude to design ${project}` : 'Ask Claude to design'}
      </Button>
      <Modal opened={open} onClose={() => setOpen(false)} title={`Design ${project}`}>
        <Stack gap="sm">
          <Text size="sm">
            This starts a conversation with Claude in a thread. It checks the project's setup, reads the registry and the
            neighbouring projects, drafts the brief and asks what it needs. You answer in the thread and move the design
            through brief, architecture and plan yourself.
          </Text>
          {!first && (
            <TextInput
              label="Which design?"
              description={`Existing: ${existing.join(', ')}. A new name starts another design, for one feature.`}
              value={name}
              onChange={(e) => setName(e.currentTarget.value)}
              error={valid ? undefined : 'Lowercase letters, digits and dashes'}
            />
          )}
          <Textarea
            label="What should it be? (optional)"
            placeholder="e.g. a small service that keeps the invoices and serves them to the web app"
            autosize
            minRows={3}
            value={purpose}
            onChange={(e) => setPurpose(e.currentTarget.value)}
          />
          {!onDemand && (
            <Alert color="gray" variant="light">
              On-demand Claude is off, so the thread waits for <code>/inbox</code> in Archeion's terminal. Switch it on in{' '}
              <Link to="/settings#on-demand">Settings</Link> to have each round answered as soon as you reply.
            </Alert>
          )}
          {create.error && <Alert color="red">{create.error.message}</Alert>}
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={submit} loading={create.isPending} disabled={!valid}>
              Start
            </Button>
          </Group>
        </Stack>
      </Modal>
    </>
  )
}

function ApproveModal({
  project,
  slug,
  opened,
  onClose,
}: {
  project: string
  slug: string
  opened: boolean
  onClose: () => void
}) {
  const approval = useDesignApproval(project, slug, opened)
  const approve = useApproveDesign(project, slug)
  const data = approval.data
  return (
    <Modal opened={opened} onClose={onClose} title="Approve this design">
      <Stack gap="sm">
        {approval.isPending && <Loader size="sm" />}
        {data && data.problems.length > 0 && (
          <Alert color="red" variant="light" title="It can't be approved yet">
            <List size="sm">
              {data.problems.map((p) => (
                <List.Item key={p}>{p}</List.Item>
              ))}
            </List>
          </Alert>
        )}
        {data && data.problems.length === 0 && (
          <>
            <Text size="sm">
              This freezes the design as <b>revision {data.next_revision}</b>. Later edits go on the working copy and
              never change a revision.
            </Text>
            {data.changes.length > 0 ? (
              <>
                <Text size="sm">It also changes these lines in the project's registry page ({data.page}):</Text>
                <Table withTableBorder fz="sm">
                  <Table.Tbody>
                    {data.changes.map((c) => (
                      <Table.Tr key={c.key}>
                        <Table.Td>
                          <Code>{c.key}</Code>
                        </Table.Td>
                        <Table.Td c="dimmed">
                          {Array.isArray(c.old) ? (c.old.length ? `[${c.old.join(', ')}]` : 'not set') : String(c.old ?? 'not set')}
                        </Table.Td>
                        <Table.Td>
                          <Code>{c.value}</Code>
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </>
            ) : (
              <Text size="sm" c="dimmed">
                The registry page needs no changes.
              </Text>
            )}
          </>
        )}
        {approve.error && <Alert color="red">{approve.error.message}</Alert>}
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            Cancel
          </Button>
          <Button
            leftSection={<IconCheck size={14} />}
            disabled={!data || data.problems.length > 0}
            loading={approve.isPending}
            onClick={() =>
              approve.mutate(undefined, {
                onSuccess: () => {
                  notifications.show({ color: 'green', title: 'Design approved', message: `Revision ${data?.next_revision} is frozen.` })
                  onClose()
                },
              })
            }
          >
            Approve
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}

function Handoff({ row }: { row: DesignRow }) {
  const pre = useDesignPreflight(row.project, 'handoff', row.slug)
  const handoff = useHandoffDesign(row.project, row.slug)
  const navigate = useNavigate()
  const blocked = pre.data ? !pre.data.ok : true
  const latest = row.revisions[0]
  return (
    <Stack gap="xs">
      {pre.data && <Problems problems={pre.data.problems.filter((p) => p.severity !== 'info')} />}
      {handoff.error && <Alert color="red">{handoff.error.message}</Alert>}
      <Group gap="xs">
        <Button
          size="xs"
          leftSection={<IconSend size={14} />}
          disabled={blocked}
          loading={handoff.isPending}
          onClick={() =>
            handoff.mutate(undefined, {
              onSuccess: (item) => {
                notifications.show({
                  color: 'green',
                  title: 'Handoff requested',
                  message: `Archeion's inbox delivers revision ${latest?.number} to the project. Then run /archeion:consume-design in its session.`,
                })
                navigate(`/feedback/${item.id}`)
              },
            })
          }
        >
          Hand off revision {latest?.number} to the project
        </Button>
        {latest?.handoff && (
          <Text size="xs" c="dimmed">
            {latest.handoff.consumed
              ? 'The project consumed it.'
              : latest.handoff.thread
                ? 'Requested. Waiting for the project to consume it.'
                : ''}
            {latest.handoff.thread && (
              <>
                {' '}
                <Link to={`/feedback/${latest.handoff.thread}`}>Thread</Link>
              </>
            )}
          </Text>
        )}
      </Group>
    </Stack>
  )
}

function Doc({ text, path, empty }: { text: string | undefined; path: string; empty: string }) {
  if (isBlank(text)) {
    return (
      <Text c="dimmed" size="sm">
        {empty}
      </Text>
    )
  }
  return (
    <Stack gap="xs">
      <MarkdownView content={text ?? ''} docPath={path} source={REGISTRY} compact />
      <Text size="xs" c="dimmed">
        <Link to={docUrl(REGISTRY, path)}>Open this document</Link> to comment on a passage; the comment reaches Claude in
        Archeion's inbox.
      </Text>
    </Stack>
  )
}

function Architecture({ design, base }: { design: DesignFull; base: string }) {
  const model = useMemo(() => asStudyModel(design.model), [design.model])
  const structure = design.model?.structure
  const hasModel = model && (model.components.length > 0 || model.flows.length > 0 || model.entities.length > 0)
  return (
    <Stack gap="lg">
      <Doc text={design.files['architecture.md'] } path={`${base}/architecture.md`} empty="No architecture written yet." />
      {design.model_problems.length > 0 && (
        <Alert color="red" variant="light" title="The model has problems">
          <List size="sm">
            {design.model_problems.map((p) => (
              <List.Item key={p}>{p}</List.Item>
            ))}
          </List>
        </Alert>
      )}
      {model && hasModel && (
        <>
          {model.components.length > 0 && (
            <Stack gap="xs">
              <Title order={4}>Components</Title>
              <ViewSwitch
                interactive={<LazyGraph graph={componentGraph(model)} title="Components" height={520} minimap />}
                mermaid={<MermaidBlock code={componentMap(model)} title="Components" />}
              />
            </Stack>
          )}
          {model.flows.map((f) => (
            <Stack key={f.id} gap="xs">
              <Title order={4}>{f.title}</Title>
              {f.summary && <Text size="sm">{f.summary}</Text>}
              <ViewSwitch
                interactive={<SequenceView flow={f} components={model.components} />}
                mermaid={<MermaidBlock code={sequence(f, model.components)} title={f.title} />}
              />
            </Stack>
          ))}
          {model.entities.length > 0 && (
            <Stack gap="xs">
              <Title order={4}>Data</Title>
              <MermaidBlock code={erDiagram(model.entities)} title="Data" />
            </Stack>
          )}
          {(model.interfaces.exposes.length > 0 || model.interfaces.calls.length > 0) && (
            <Stack gap="xs">
              <Title order={4}>Interfaces</Title>
              <Table withTableBorder fz="sm">
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Direction</Table.Th>
                    <Table.Th>Interface</Table.Th>
                    <Table.Th>Notes</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {model.interfaces.exposes.map((x) => (
                    <Table.Tr key={x.id}>
                      <Table.Td>exposes</Table.Td>
                      <Table.Td>
                        <Code>{[x.method, x.path ?? x.name].filter(Boolean).join(' ')}</Code>
                      </Table.Td>
                      <Table.Td>{x.summary}</Table.Td>
                    </Table.Tr>
                  ))}
                  {model.interfaces.calls.map((x) => (
                    <Table.Tr key={x.id}>
                      <Table.Td>calls {x.target_project ?? ''}</Table.Td>
                      <Table.Td>
                        <Code>{[x.method, x.path ?? x.target_url].filter(Boolean).join(' ')}</Code>
                      </Table.Td>
                      <Table.Td>{x.summary}</Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Stack>
          )}
        </>
      )}
      {structure && (structure.ports?.length || structure.depends_on?.length || structure.group || structure.kind) && (
        <Stack gap="xs">
          <Title order={4}>What approval records in the registry</Title>
          <Table withTableBorder fz="sm">
            <Table.Tbody>
              {structure.ports?.length ? (
                <Table.Tr>
                  <Table.Td>ports</Table.Td>
                  <Table.Td>{structure.ports.join(', ')}</Table.Td>
                </Table.Tr>
              ) : null}
              {structure.depends_on?.length ? (
                <Table.Tr>
                  <Table.Td>depends on</Table.Td>
                  <Table.Td>{structure.depends_on.join(', ')}</Table.Td>
                </Table.Tr>
              ) : null}
              {structure.group && (
                <Table.Tr>
                  <Table.Td>group</Table.Td>
                  <Table.Td>{structure.group}</Table.Td>
                </Table.Tr>
              )}
              {structure.kind && (
                <Table.Tr>
                  <Table.Td>kind</Table.Td>
                  <Table.Td>{structure.kind}</Table.Td>
                </Table.Tr>
              )}
            </Table.Tbody>
          </Table>
        </Stack>
      )}
    </Stack>
  )
}

function SendToNeighbour({ impact }: { impact: Impact }) {
  const create = useCreateFeedback()
  const [sent, setSent] = useState(false)
  if (!impact.neighbour || !impact.suggestion) return null
  return (
    <Button
      size="compact-xs"
      variant="default"
      disabled={sent}
      loading={create.isPending}
      onClick={() =>
        create.mutate(
          { kind: 'prompt', source: impact.neighbour, body: impact.suggestion ?? '' },
          {
            onSuccess: () => {
              setSent(true)
              notifications.show({ color: 'green', title: 'Sent', message: `It's in ${impact.neighbour}'s inbox.` })
            },
          },
        )
      }
    >
      {sent ? 'Sent' : `Send to ${impact.neighbour}`}
    </Button>
  )
}

function ImpactView({ project, slug }: { project: string; slug: string }) {
  const impact = useDesignImpact(project, slug)
  if (impact.isPending) return <Loader size="sm" />
  if (impact.error) return <Alert color="red">{impact.error.message}</Alert>
  const items = impact.data ?? []
  if (items.length === 0) {
    return (
      <Text size="sm" c="dimmed">
        Nothing in this design asks anything of the other projects, or conflicts with them.
      </Text>
    )
  }
  return (
    <Stack gap="xs">
      <Text size="sm" c="dimmed">
        What the design needs from the other projects. Nothing here edits them: an item goes to their own inbox, where you
        or their session decide.
      </Text>
      {items.map((i, n) => (
        <Alert key={`${i.kind}-${n}`} color={SEVERITY_COLOR[i.severity]} variant="light" py="xs">
          <Group justify="space-between" wrap="nowrap" align="flex-start">
            <Text size="sm">{i.message}</Text>
            <SendToNeighbour impact={i} />
          </Group>
        </Alert>
      ))}
    </Stack>
  )
}

function BuiltView({ project, slug }: { project: string; slug: string }) {
  const built = useBuiltVsDesigned(project, slug)
  if (built.isPending) return <Loader size="sm" />
  if (built.error) return <Alert color="red">{built.error.message}</Alert>
  const data = built.data
  if (!data?.studied) {
    return (
      <Text size="sm" c="dimmed">
        This project hasn't been studied, so there's nothing built to compare with. Run a study on the Study tab once there is
        code.
      </Text>
    )
  }
  const names: Record<string, string> = {
    components: 'Components',
    exposes: 'Endpoints it exposes',
    calls: 'Calls it makes',
    entities: 'Tables',
  }
  return (
    <Stack gap="md">
      <Text size="sm" c="dimmed">
        The working copy against the study {data.studied}, matched by name. Still to build is in the design but not in the
        code; extra is in the code but not in the design.
      </Text>
      <Table withTableBorder fz="sm">
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Section</Table.Th>
            <Table.Th>Both</Table.Th>
            <Table.Th>Still to build</Table.Th>
            <Table.Th>Extra in the code</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {Object.entries(data.sections).map(([key, s]) => (
            <Table.Tr key={key}>
              <Table.Td>{names[key] ?? key}</Table.Td>
              <Table.Td>{s.both}</Table.Td>
              <Table.Td>{s.designed_only.join(', ') || '-'}</Table.Td>
              <Table.Td>{s.built_only.join(', ') || '-'}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Stack>
  )
}

function DesignView({ row, slugs }: { row: DesignRow; slugs: string[] }) {
  const [view, setView] = useState<View>('brief')
  const [revision, setRevision] = useState<number | null>(null)
  const [approving, setApproving] = useState(false)
  const design = useDesign(row.project, row.slug, revision)
  const setStage = useSetDesignStage(row.project, row.slug)
  const pre = useDesignPreflight(row.project, 'design', row.slug)
  const d = design.data
  const rev = revision === null ? null : row.revisions.find((r) => r.number === revision)
  const base = rev
    ? `designs/${row.project}/${row.slug}/revisions/${rev.id}`
    : `designs/${row.project}/${row.slug}`
  const decisions = Object.keys(d?.files ?? {})
    .filter((k) => k.startsWith('decisions/'))
    .sort()
  const working = revision === null
  const approved = row.stage === 'approved' || row.stage === 'handed off'

  return (
    <Stack gap="md">
      <Group justify="space-between" align="flex-start">
        <Stack gap={4}>
          <Group gap="xs">
            <StageBadge stage={row.stage} />
            {!approved && <Badge variant="outline" color="gray" size="sm">draft</Badge>}
            {row.changed_since_revision && (
              <Badge variant="light" color="orange" size="sm" title="The working copy differs from its latest revision">
                changed since revision {row.revision}
              </Badge>
            )}
            {!row.valid && (
              <Badge variant="light" color="red" size="sm" title={row.problems.join('; ')}>
                model has problems
              </Badge>
            )}
            {row.thread && (
              <Text size="xs">
                <Link to={`/feedback/${row.thread}`}>Conversation</Link>
              </Text>
            )}
          </Group>
          {row.summary && <Text size="sm">{row.summary}</Text>}
        </Stack>
        <Group gap="xs">
          <StartDesignButton project={row.project} slug={row.slug} existing={slugs} variant="default" />
        </Group>
      </Group>

      <Problems problems={(pre.data?.problems ?? []).filter((p) => p.severity !== 'info' || !approved)} />

      <Group gap="md" align="center">
        <Text size="sm" fw={500}>
          Stage
        </Text>
        <SegmentedControl
          size="xs"
          value={(WORKING_STAGES as readonly string[]).includes(row.stage) ? row.stage : ''}
          data={WORKING_STAGES.map((s) => ({ value: s, label: s }))}
          onChange={(v) => setStage.mutate(v)}
          disabled={setStage.isPending}
        />
        <Button size="xs" leftSection={<IconCheck size={14} />} onClick={() => setApproving(true)}>
          Approve
        </Button>
        <Text size="xs" c="dimmed">
          {STAGES.indexOf(row.stage) < 3 ? 'You decide when it moves on. Claude only proposes.' : ''}
        </Text>
      </Group>
      {setStage.error && <Alert color="red">{setStage.error.message}</Alert>}
      <ApproveModal project={row.project} slug={row.slug} opened={approving} onClose={() => setApproving(false)} />

      {row.revision && <Handoff row={row} />}

      <Group gap="md">
        <SegmentedControl size="xs" value={view} onChange={(v) => setView(v as View)} data={VIEWS.map(([v, l]) => ({
            value: v,
            label:
              v === 'checklist' && row.checklist.pending > 0 ? (
                <Group gap={4} wrap="nowrap" justify="center">
                  {l}
                  <Badge size="xs" color="yellow" circle>
                    {row.checklist.pending}
                  </Badge>
                </Group>
              ) : (
                l
              ),
          }))} />
        {row.revisions.length > 0 && view !== 'revisions' && (
          <Select
            size="xs"
            w={190}
            allowDeselect={false}
            value={revision === null ? 'working' : String(revision)}
            onChange={(v) => setRevision(v === 'working' || v === null ? null : Number(v))}
            data={[
              { value: 'working', label: 'Working copy' },
              ...row.revisions.map((r) => ({ value: String(r.number), label: `Revision ${r.number} (${r.date})` })),
            ]}
          />
        )}
        {!working && (
          <Text size="xs" c="dimmed">
            A frozen revision: it never changes.
          </Text>
        )}
      </Group>

      {design.isPending && <Loader size="sm" />}
      {design.error && <Alert color="red">{design.error.message}</Alert>}
      {d && view === 'brief' && (
        <Doc text={d.files['brief.md'] } path={`${base}/brief.md`} empty="No brief yet. Ask Claude to design, and answer its questions." />
      )}
      {d && view === 'architecture' && <Architecture design={d} base={base} />}
      {d && view === 'plan' && (
        <Doc text={d.files['plan.md'] } path={`${base}/plan.md`} empty="No plan written yet." />
      )}
      {view === 'checklist' && <Checklist project={row.project} slug={row.slug} revision={revision} thread={row.thread} />}
      {view === 'roadmap' && (
        <RoadmapView project={row.project} slug={row.slug} revision={revision} onOpenItem={() => setView('checklist')} />
      )}
      {d && view === 'decisions' &&
        (decisions.length === 0 ? (
          <Text c="dimmed" size="sm">
            No decisions recorded yet. They're written in ADR shape, for the project's own docs.
          </Text>
        ) : (
          <Stack gap="lg">
            {decisions.map((k) => (
              <Card key={k} withBorder padding="sm">
                <Doc text={d.files[k] } path={`${base}/${k}`} empty="" />
              </Card>
            ))}
          </Stack>
        ))}
      {d && view === 'questions' && (
        <Doc text={d.files['questions.md'] } path={`${base}/questions.md`} empty="Nothing open." />
      )}
      {view === 'impact' && <ImpactView project={row.project} slug={row.slug} />}
      {view === 'built' && <BuiltView project={row.project} slug={row.slug} />}
      {view === 'revisions' &&
        (row.revisions.length === 0 ? (
          <Text c="dimmed" size="sm">
            No revision yet. Approving freezes one.
          </Text>
        ) : (
          <Table withTableBorder fz="sm">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Revision</Table.Th>
                <Table.Th>Date</Table.Th>
                <Table.Th>Handoff</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {row.revisions.map((r) => (
                <Table.Tr key={r.id}>
                  <Table.Td>{r.number}</Table.Td>
                  <Table.Td>{r.date}</Table.Td>
                  <Table.Td>
                    {r.handoff ? (r.handoff.consumed ? 'consumed by the project' : 'requested') : 'not handed off'}
                  </Table.Td>
                  <Table.Td>
                    <Button
                      size="compact-xs"
                      variant="subtle"
                      onClick={() => {
                        setRevision(r.number)
                        setView('brief')
                      }}
                    >
                      View
                    </Button>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        ))}
    </Stack>
  )
}

/** The project page's Design tab (ADR 0022): a design's stage, documents and diagrams, with the user's moves. */
export function DesignTab({ project }: { project: string }) {
  const designs = useDesigns(project)
  const [params, setParams] = useSearchParams()
  const rows = designs.data ?? []
  const slugs = rows.map((r) => r.slug)
  const wanted = params.get('design')
  const row = rows.find((r) => r.slug === wanted) ?? rows[0]
  const pre = useDesignPreflight(project, 'design', row?.slug ?? 'main')

  if (designs.isPending) return <Loader size="sm" />
  if (designs.error) return <Alert color="red">{designs.error.message}</Alert>

  if (!row) {
    return (
      <Stack gap="md" maw={720}>
        <Text size="sm">
          A design says what this project is for and how it should be built, with the other projects in view. Claude drafts
          it with you in a conversation, you move it through brief, architecture and plan, approve it, and hand it to the
          project to build.
        </Text>
        <Problems problems={pre.data?.problems ?? []} />
        <div>
          <StartDesignButton project={project} slug="main" existing={[]} />
        </div>
      </Stack>
    )
  }

  return (
    <Stack gap="md">
      {rows.length > 1 && (
        <Group gap="xs">
          <Text size="sm" fw={500}>
            Design
          </Text>
          <SegmentedControl
            size="xs"
            value={row.slug}
            onChange={(v) => setParams((p) => { const next = new URLSearchParams(p); next.set('design', v); return next }, { replace: true })}
            data={rows.map((r) => ({ value: r.slug, label: r.slug }))}
          />
        </Group>
      )}
      <DesignView key={row.slug} row={row} slugs={slugs} />
    </Stack>
  )
}
