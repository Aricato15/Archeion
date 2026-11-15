import {
  Alert,
  Anchor,
  Badge,
  Blockquote,
  Button,
  Card,
  Group,
  Loader,
  Paper,
  Stack,
  Text,
  Textarea,
  Title,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconArrowBackUp, IconCheck, IconPencil, IconSend, IconTrash } from '@tabler/icons-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import {
  useCreateFeedback,
  useDeleteFeedback,
  useFeedbackItem,
  usePatchFeedback,
  useReopenFeedback,
} from '../api/queries'
import { SELF, type FeedbackItem } from '../api/types'
import { describeAnchor } from '../docs/anchors'
import { MarkdownView } from '../docs/MarkdownView'
import { formatDate } from '../lib/format'
import { OriginBadge, ProjectBadge, StatusBadge } from './FeedbackCard'
import { KIND_LABEL, docLink } from './labels'

/** One message in a thread: what you wrote and, once answered, Claude's reply. */
function Message({ item, highlight, onDeleted }: { item: FeedbackItem; highlight: boolean; onDeleted: () => void }) {
  const patch = usePatchFeedback()
  const remove = useDeleteFeedback()
  const [editing, setEditing] = useState(false)
  const [body, setBody] = useState(item.body)
  const error = patch.error ?? remove.error
  const docPath = item.doc_path ?? 'README.md'

  return (
    <Card
      withBorder
      padding="md"
      radius="md"
      style={highlight ? { borderColor: 'var(--mantine-primary-color-filled)' } : undefined}
    >
      <Stack gap="xs">
        <Group justify="space-between">
          <Group gap="xs">
            <Anchor component={Link} to={`/feedback/${item.id}`} fw={700} size="sm">
              #{item.id}
            </Anchor>
            <Text size="sm" fw={600}>
              You
            </Text>
            {(item.status === 'open' || item.status === 'in_progress') && <StatusBadge item={item} />}
          </Group>
          <Text size="xs" c="dimmed">
            {formatDate(item.created_at)}
          </Text>
        </Group>
        {editing ? (
          <Stack gap="xs">
            <Textarea autosize minRows={3} value={body} onChange={(e) => setBody(e.currentTarget.value)} />
            <Group gap="xs">
              <Button
                size="xs"
                loading={patch.isPending}
                disabled={!body.trim()}
                onClick={() => patch.mutate({ id: item.id, body: body.trim() }, { onSuccess: () => setEditing(false) })}
              >
                Save
              </Button>
              <Button size="xs" variant="default" onClick={() => setEditing(false)}>
                Cancel
              </Button>
            </Group>
          </Stack>
        ) : (
          <MarkdownView content={item.body} docPath={docPath} source={item.source} compact />
        )}
        {item.reply && (
          <Paper withBorder p="sm" radius="md" bg="var(--mantine-color-green-light)">
            <Text size="xs" fw={700} c="green" mb={4}>
              Claude replied {item.answered_at ? formatDate(item.answered_at) : ''}
            </Text>
            <MarkdownView content={item.reply} docPath={docPath} source={item.source} compact />
          </Paper>
        )}
        {item.status === 'in_progress' && (
          <Group gap="xs">
            <Text size="sm" c="yellow">
              Claude is working on this (claimed {formatDate(item.claimed_at)}).
            </Text>
            <Button size="xs" variant="default" onClick={() => patch.mutate({ id: item.id, status: 'open' })}>
              Release the claim
            </Button>
          </Group>
        )}
        {item.status === 'open' && !editing && (
          <Group gap="xs">
            <Button size="xs" variant="default" leftSection={<IconPencil size={14} />} onClick={() => setEditing(true)}>
              Edit
            </Button>
            <Button
              size="xs"
              color="red"
              variant="subtle"
              leftSection={<IconTrash size={14} />}
              loading={remove.isPending}
              onClick={() => {
                if (window.confirm(`Delete message #${item.id}?`)) remove.mutate(item.id, { onSuccess: onDeleted })
              }}
            >
              Delete
            </Button>
          </Group>
        )}
        {error && <Alert color="red">{error.message}</Alert>}
      </Stack>
    </Card>
  )
}

/** Answer Claude in the same thread. The backend hands Claude the whole conversation (ADR 0018). */
function ReplyBox({ last }: { last: FeedbackItem }) {
  const create = useCreateFeedback()
  const [body, setBody] = useState('')

  if (last.status === 'open') {
    return (
      <Text size="sm" c="dimmed">
        Claude hasn't picked up your last message yet. To add to it, edit it above.
      </Text>
    )
  }
  if (last.status === 'in_progress') {
    return (
      <Text size="sm" c="dimmed">
        Claude is working on this. You can reply once it answers.
      </Text>
    )
  }

  const send = () => {
    if (!body.trim()) return
    create.mutate(
      { body: body.trim(), parent_id: last.id },
      {
        onSuccess: (item) => {
          setBody('')
          const where = item.source === SELF ? 'Archeion' : item.source
          notifications.show({
            color: 'green',
            title: 'Reply sent',
            message: `It's in ${where}'s inbox with the conversation so far.`,
          })
        },
      },
    )
  }

  return (
    <Stack gap="xs">
      <Textarea
        label="Reply"
        description={
          last.status === 'resolved'
            ? 'This thread is resolved. Replying reopens it.'
            : 'Claude gets the whole conversation with your reply. Markdown is fine.'
        }
        placeholder="Answer Claude, or ask for more"
        rows={4}
        resize="vertical"
        value={body}
        onChange={(e) => setBody(e.currentTarget.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) send()
        }}
      />
      {create.isError && (
        <Text c="red" size="sm">
          {create.error.message}
        </Text>
      )}
      <Group justify="space-between">
        <Text size="xs" c="dimmed">
          Ctrl+Enter to send
        </Text>
        <Button leftSection={<IconSend size={16} />} onClick={send} loading={create.isPending} disabled={!body.trim()}>
          Send reply
        </Button>
      </Group>
    </Stack>
  )
}

/**
 * What you do with Claude's answer, for the whole thread (ADR 0018): resolve it (every message),
 * or reopen it, which adds a "Reopened" message for Claude that you can edit to say more.
 */
function ThreadActions({ last, single }: { last: FeedbackItem; single: boolean }) {
  const patch = usePatchFeedback()
  const reopen = useReopenFeedback()
  const status = last.status
  if (status === 'in_progress') return null
  const error = patch.error ?? reopen.error
  return (
    <Stack gap="xs">
      <Group gap="xs">
        {status !== 'resolved' && (
          <Button
            size="xs"
            leftSection={<IconCheck size={14} />}
            loading={patch.isPending}
            onClick={() => patch.mutate({ id: last.id, status: 'resolved' })}
          >
            {status === 'open' && single ? 'Dismiss' : 'Resolve thread'}
          </Button>
        )}
        {status !== 'open' && (
          <Button
            size="xs"
            variant="default"
            leftSection={<IconArrowBackUp size={14} />}
            title="Back to Claude's inbox, as a new message you can edit to say more"
            loading={reopen.isPending}
            onClick={() => reopen.mutate(last.id)}
          >
            Reopen thread
          </Button>
        )}
      </Group>
      {error && <Alert color="red">{error.message}</Alert>}
    </Stack>
  )
}

export function ThreadPage() {
  const id = Number(useParams().id)
  const query = useFeedbackItem(id)
  const navigate = useNavigate()

  if (query.isPending) return <Loader />
  if (query.isError) return <Alert color="yellow">Feedback #{Number.isFinite(id) ? id : '?'} wasn't found.</Alert>

  const { item, thread } = query.data
  const first = thread[0] ?? item
  const last = thread[thread.length - 1] ?? item
  // A thread's status is its latest message's, and resolving closes all of it (ADR 0018).
  const link = docLink(first)
  const onDeleted = (deleted: FeedbackItem) => () => {
    if (deleted.id === first.id) navigate('/feedback')
    else if (deleted.id === item.id) navigate(`/feedback/${first.id}`, { replace: true })
  }

  return (
    <Stack maw={900}>
      <Group justify="space-between" align="flex-start">
        <Stack gap={4}>
          <Group gap="xs">
            <Title order={2}>Thread #{first.id}</Title>
            <Badge variant="outline" size="sm">
              {KIND_LABEL[first.kind]}
            </Badge>
            <StatusBadge item={last} />
            {first.source !== SELF && <ProjectBadge id={first.source} />}
            {first.origin && <OriginBadge id={first.origin} />}
          </Group>
          <Text size="xs" c="dimmed">
            {thread.length} {thread.length === 1 ? 'message' : 'messages'} · started {formatDate(first.created_at)}
          </Text>
        </Stack>
        <Anchor component={Link} to="/feedback" size="sm">
          All feedback
        </Anchor>
      </Group>
      {first.doc_path && link && (
        <Text size="sm">
          <Anchor component={Link} to={link}>
            {first.doc_path}
          </Anchor>{' '}
          · {describeAnchor(first.anchor)}
          {first.doc_rev && (
            <Text span size="xs" c="dimmed">
              {' '}
              (written at {first.doc_rev.slice(0, 8)})
            </Text>
          )}
        </Text>
      )}
      {first.anchor?.quote && (
        <Blockquote p="xs" style={{ whiteSpace: 'pre-wrap' }}>
          <Text size="sm">{first.anchor.quote}</Text>
        </Blockquote>
      )}
      {thread.map((t) => (
        <Message
          key={`${t.id}:${t.updated_at}`}
          item={t}
          highlight={thread.length > 1 && t.id === item.id && t.id !== first.id}
          onDeleted={onDeleted(t)}
        />
      ))}
      <ThreadActions last={last} single={thread.length === 1} />
      <ReplyBox key={last.id} last={last} />
    </Stack>
  )
}
