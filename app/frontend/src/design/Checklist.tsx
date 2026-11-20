import {
  Alert,
  Badge,
  Button,
  Card,
  Collapse,
  Group,
  Loader,
  SegmentedControl,
  Select,
  Stack,
  Switch,
  Text,
  Textarea,
  TextInput,
} from '@mantine/core'
import { useState } from 'react'
import {
  useChecklist,
  useConfirmChecklist,
  useCreateFeedback,
  useDecideChange,
  useDiscardChange,
  useFeedbackItem,
  useStageChecklist,
} from '../api/queries'
import {
  ITEM_KINDS,
  ITEM_PRIORITIES,
  ITEM_STATUSES,
  type Checklist as ChecklistData,
  type ChecklistChange,
  type ChecklistItem,
  type ItemKind,
  type ItemStatus,
} from '../api/design'

const STATUS_COLOR: Record<ItemStatus, string> = {
  idea: 'gray',
  decided: 'blue',
  doing: 'orange',
  done: 'green',
  dropped: 'red',
}
// The order the list is grouped in: what is being worked on first.
const STATUS_ORDER: ItemStatus[] = ['doing', 'decided', 'idea', 'done', 'dropped']
const MODE_KEY = 'archeion.checklist.mode'

type Mode = 'minimal' | 'rich'

function readMode(): Mode {
  try {
    return localStorage.getItem(MODE_KEY) === 'rich' ? 'rich' : 'minimal'
  } catch {
    return 'minimal'
  }
}

function writeMode(mode: Mode) {
  try {
    localStorage.setItem(MODE_KEY, mode)
  } catch {
    // The page works without it.
  }
}

const label = (v: unknown) => (Array.isArray(v) ? v.join(', ') || 'none' : v === null || v === '' ? 'none' : String(v))

/** What a staged change does, one line per field: "status: idea → decided". */
function ChangeDiff({ change, item }: { change: ChecklistChange; item: ChecklistItem | undefined }) {
  if (change.op === 'remove') return <Text size="sm">Remove this item.</Text>
  const fields = Object.entries(change.fields) as [keyof ChecklistItem, unknown][]
  return (
    <Stack gap={2}>
      {fields.map(([key, value]) => (
        <Text key={key} size="sm">
          <Text span c="dimmed">
            {key}:{' '}
          </Text>
          {change.op === 'update' && item ? (
            <>
              {label(item[key])} → <b>{label(value)}</b>
            </>
          ) : (
            <b>{label(value)}</b>
          )}
        </Text>
      ))}
    </Stack>
  )
}

function ChangeCard(props: {
  change: ChecklistChange
  item: ChecklistItem | undefined
  project: string
  slug: string
}) {
  const { change, item, project, slug } = props
  const decide = useDecideChange(project, slug)
  const discard = useDiscardChange(project, slug)
  const [text, setText] = useState('')
  const [commenting, setCommenting] = useState(false)
  const title = item?.title ?? (change.fields.title as string | undefined) ?? change.id
  const color = change.state === 'accepted' ? 'green' : change.state === 'rejected' ? 'red' : 'yellow'
  return (
    <Card withBorder padding="sm" radius="sm" style={{ borderLeft: `3px solid var(--mantine-color-${color}-6)` }}>
      <Stack gap="xs">
        <Group justify="space-between" align="flex-start">
          <Group gap="xs">
            <Badge size="sm" variant="light" color={change.by === 'claude' ? 'violet' : 'blue'}>
              {change.by === 'claude' ? 'Claude proposes' : 'You staged'}
            </Badge>
            <Badge size="sm" variant="outline" color="gray">
              {change.op}
            </Badge>
            <Text size="sm" fw={600}>
              {title}
            </Text>
          </Group>
          <Badge size="sm" color={color} variant="filled">
            {change.state}
          </Badge>
        </Group>
        <ChangeDiff change={change} item={item} />
        {change.reason && (
          <Text size="xs" c="dimmed">
            Why: {change.reason}
          </Text>
        )}
        {change.comments.map((c, i) => (
          <Text key={i} size="xs">
            <b>{c.by === 'claude' ? 'Claude' : 'You'}:</b> {c.text}
          </Text>
        ))}
        <Group gap="xs">
          <Button
            size="compact-xs"
            color="green"
            variant={change.state === 'accepted' ? 'filled' : 'light'}
            onClick={() => decide.mutate({ id: change.id, state: 'accepted' })}
          >
            Accept
          </Button>
          <Button
            size="compact-xs"
            color="red"
            variant={change.state === 'rejected' ? 'filled' : 'light'}
            onClick={() => decide.mutate({ id: change.id, state: 'rejected' })}
          >
            Reject
          </Button>
          <Button size="compact-xs" variant="subtle" onClick={() => setCommenting((v) => !v)}>
            Comment
          </Button>
          {change.by === 'user' && (
            <Button size="compact-xs" variant="subtle" color="gray" onClick={() => discard.mutate(change.id)}>
              Take back
            </Button>
          )}
        </Group>
        <Collapse expanded={commenting}>
          <Group align="flex-end" gap="xs">
            <Textarea
              size="xs"
              style={{ flex: 1 }}
              autosize
              minRows={1}
              placeholder="Tell Claude what to change. It reads this with your next message."
              value={text}
              onChange={(e) => setText(e.currentTarget.value)}
            />
            <Button
              size="xs"
              disabled={!text.trim()}
              onClick={() =>
                decide.mutate({ id: change.id, comment: text.trim() }, { onSuccess: () => { setText(''); setCommenting(false) } })
              }
            >
              Add
            </Button>
          </Group>
        </Collapse>
        {(decide.error || discard.error) && <Alert color="red">{(decide.error ?? discard.error)!.message}</Alert>}
      </Stack>
    </Card>
  )
}

function ItemRow(props: {
  item: ChecklistItem
  mode: Mode
  editable: boolean
  waiting: number
  onStatus: (s: ItemStatus) => void
}) {
  const { item, mode, editable, waiting, onStatus } = props
  const [open, setOpen] = useState(false)
  return (
    <Card withBorder padding="xs" radius="sm" data-testid={`item-${item.id}`}>
      <Group justify="space-between" wrap="nowrap" align="flex-start">
        <Group gap="xs" wrap="nowrap" align="flex-start" style={{ minWidth: 0 }}>
          <Text size="sm" c="dimmed" w={34} style={{ flexShrink: 0 }}>
            {item.id}
          </Text>
          <Stack gap={2} style={{ minWidth: 0 }}>
            <Text size="sm" fw={500} td={item.status === 'done' || item.status === 'dropped' ? 'line-through' : undefined}>
              {item.title}
              {waiting > 0 && (
                <Badge ml="xs" size="xs" color="yellow" variant="light">
                  {waiting} waiting
                </Badge>
              )}
            </Text>
            {mode === 'rich' && (
              <>
                <Group gap={6}>
                  <Badge size="xs" variant="outline" color="gray">
                    {item.kind}
                  </Badge>
                  {item.priority && (
                    <Badge size="xs" variant="light" color={item.priority === 'high' ? 'red' : 'gray'}>
                      {item.priority}
                    </Badge>
                  )}
                  {item.phase && (
                    <Badge size="xs" variant="light" color="violet">
                      {item.phase}
                    </Badge>
                  )}
                  {item.depends_on.length > 0 && (
                    <Text size="xs" c="dimmed">
                      needs {item.depends_on.join(', ')}
                    </Text>
                  )}
                  {item.refs.length > 0 && (
                    <Text size="xs" c="dimmed">
                      about {item.refs.join(', ')}
                    </Text>
                  )}
                </Group>
                {item.note && <Text size="sm">{item.note}</Text>}
                {item.history.length > 0 && (
                  <>
                    <Text size="xs" c="blue" style={{ cursor: 'pointer' }} onClick={() => setOpen((v) => !v)}>
                      {open ? 'Hide history' : `History (${item.history.length})`}
                    </Text>
                    <Collapse expanded={open}>
                      <Stack gap={2}>
                        {item.history.map((h, i) => (
                          <Text key={i} size="xs" c="dimmed">
                            {h.at.slice(0, 10)} · {h.by} · {h.change}
                            {h.reason ? ` (${h.reason})` : ''}
                          </Text>
                        ))}
                      </Stack>
                    </Collapse>
                  </>
                )}
              </>
            )}
          </Stack>
        </Group>
        {editable ? (
          <Select
            size="xs"
            w={110}
            allowDeselect={false}
            aria-label={`Status of ${item.title}`}
            value={item.status}
            data={ITEM_STATUSES.map((s) => ({ value: s, label: s }))}
            onChange={(v) => v && v !== item.status && onStatus(v as ItemStatus)}
          />
        ) : (
          <Badge color={STATUS_COLOR[item.status]} variant="light">
            {item.status}
          </Badge>
        )}
      </Group>
    </Card>
  )
}

function AddItem({ onAdd }: { onAdd: (title: string, kind: ItemKind, status: ItemStatus) => void }) {
  const [title, setTitle] = useState('')
  const [kind, setKind] = useState<ItemKind>('idea')
  const [status, setStatus] = useState<ItemStatus>('idea')
  return (
    <Group gap="xs" align="flex-end">
      <TextInput
        size="xs"
        style={{ flex: 1, minWidth: 200 }}
        label="Add an item"
        placeholder="A feature, an idea, a decision..."
        value={title}
        onChange={(e) => setTitle(e.currentTarget.value)}
      />
      <Select size="xs" w={110} aria-label="Kind" allowDeselect={false} value={kind} data={[...ITEM_KINDS]} onChange={(v) => v && setKind(v as ItemKind)} />
      <Select size="xs" w={110} aria-label="Status" allowDeselect={false} value={status} data={[...ITEM_STATUSES]} onChange={(v) => v && setStatus(v as ItemStatus)} />
      <Button
        size="xs"
        disabled={!title.trim()}
        onClick={() => {
          onAdd(title.trim(), kind, status)
          setTitle('')
        }}
      >
        Stage
      </Button>
    </Group>
  )
}

/** The checklist of a design (ADR 0029): the agreed features, ideas and decisions. Claude proposes, you
 * accept, reject or comment, and Confirm applies what you accepted. */
export function Checklist(props: { project: string; slug: string; revision: number | null; thread: number | null }) {
  const { project, slug, revision, thread } = props
  const working = revision === null
  const list = useChecklist(project, slug, revision)
  const stage = useStageChecklist(project, slug)
  const confirm = useConfirmChecklist(project, slug)
  const [mode, setMode] = useState<Mode>(readMode)
  const [showDropped, setShowDropped] = useState(false)
  const [kind, setKind] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const threadItem = useFeedbackItem(thread ?? 0)
  const send = useCreateFeedback()

  if (list.isPending) return <Loader size="sm" />
  if (list.error) return <Alert color="red">{list.error.message}</Alert>
  const data: ChecklistData = list.data
  const byId = new Map(data.items.map((i) => [i.id, i]))
  const accepted = data.pending.filter((c) => c.state === 'accepted').length
  const rejected = data.pending.filter((c) => c.state === 'rejected').length
  const waitingFor = (id: string) => data.pending.filter((c) => c.item === id && c.state === 'pending').length
  const hiddenDropped = !showDropped && mode === 'minimal'
  const items = data.items.filter(
    (i) => (!hiddenDropped || i.status !== 'dropped') && (!kind || i.kind === kind) && (!status || i.status === status),
  )
  const hasComments = data.pending.some((c) => c.comments.some((x) => x.by === 'user'))
  const lastMessage = threadItem.data?.thread.at(-1)

  const sendToClaude = () => {
    if (!lastMessage) return
    const lines = data.pending.map((c) => {
      const what = c.item ?? (c.fields.title as string | undefined) ?? c.id
      const notes = c.comments.map((x) => `    ${x.by}: ${x.text}`).join('\n')
      return `- ${c.id} (${c.op} ${what}): ${c.state}${notes ? `\n${notes}` : ''}`
    })
    send.mutate({
      body: `Checklist review. Please revise the staged changes below with my comments, and stage anything new.\n\n${lines.join('\n')}`,
      parent_id: lastMessage.id,
    })
  }

  return (
    <Stack gap="md">
      <Group justify="space-between" align="center">
        <Group gap="xs">
          <Text size="sm">
            <b>{data.counts.done}</b> done of <b>{data.counts.total}</b>
          </Text>
          {!working && (
            <Text size="xs" c="dimmed">
              Frozen with the revision.
            </Text>
          )}
        </Group>
        <Group gap="sm">
          {mode === 'minimal' && (
            <Switch size="xs" label="Show dropped" checked={showDropped} onChange={(e) => setShowDropped(e.currentTarget.checked)} />
          )}
          <SegmentedControl
            size="xs"
            value={mode}
            data={[
              { value: 'minimal', label: 'Minimal' },
              { value: 'rich', label: 'Rich' },
            ]}
            onChange={(v) => {
              setMode(v as Mode)
              writeMode(v as Mode)
            }}
          />
        </Group>
      </Group>

      {working && data.pending.length > 0 && (
        <Stack gap="xs">
          <Text fw={600} size="sm">
            Waiting for your review ({data.pending.length})
          </Text>
          {data.pending.map((c) => (
            <ChangeCard key={c.id} change={c} item={c.item ? byId.get(c.item) : undefined} project={project} slug={slug} />
          ))}
          <Group gap="xs">
            <Button size="xs" disabled={accepted + rejected === 0 || confirm.isPending} onClick={() => confirm.mutate()}>
              Confirm {accepted + rejected} decision{accepted + rejected === 1 ? '' : 's'}
            </Button>
            {thread && hasComments && (
              <Button size="xs" variant="light" disabled={!lastMessage || send.isPending} onClick={sendToClaude}>
                Send comments to Claude
              </Button>
            )}
            <Text size="xs" c="dimmed">
              Only accepted changes are applied; rejected ones are recorded; the rest keep waiting.
            </Text>
          </Group>
          {send.isSuccess && <Alert color="blue">Sent. Claude answers in the conversation.</Alert>}
          {(confirm.error || send.error) && <Alert color="red">{(confirm.error ?? send.error)!.message}</Alert>}
        </Stack>
      )}
      {working && stage.error && <Alert color="red">{stage.error.message}</Alert>}

      <Group gap="xs">
        <Select size="xs" w={130} clearable placeholder="Any kind" aria-label="Filter by kind" value={kind} data={[...ITEM_KINDS]} onChange={setKind} />
        <Select size="xs" w={130} clearable placeholder="Any status" aria-label="Filter by status" value={status} data={[...ITEM_STATUSES]} onChange={setStatus} />
        {mode === 'rich' && (
          <Text size="xs" c="dimmed">
            Priorities: {ITEM_PRIORITIES.join(', ')}. Claude sets the rest.
          </Text>
        )}
      </Group>

      {data.items.length === 0 ? (
        <Text c="dimmed" size="sm">
          Nothing on the checklist yet. As you and Claude settle on features, ideas and decisions, Claude proposes them here.
        </Text>
      ) : (
        STATUS_ORDER.map((s) => {
          const group = items.filter((i) => i.status === s)
          if (group.length === 0) return null
          return (
            <Stack key={s} gap="xs">
              <Group gap="xs">
                <Badge color={STATUS_COLOR[s]} variant="light">
                  {s}
                </Badge>
                <Text size="xs" c="dimmed">
                  {group.length}
                </Text>
              </Group>
              {group.map((item) => (
                <ItemRow
                  key={item.id}
                  item={item}
                  mode={mode}
                  editable={working}
                  waiting={waitingFor(item.id)}
                  onStatus={(st) => stage.mutate([{ op: 'update', item: item.id, fields: { status: st }, reason: 'changed in the viewer' }])}
                />
              ))}
            </Stack>
          )
        })
      )}

      {working && (
        <AddItem
          onAdd={(title, k, st) => stage.mutate([{ op: 'add', fields: { title, kind: k, status: st }, reason: 'added in the viewer' }])}
        />
      )}
    </Stack>
  )
}
