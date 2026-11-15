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
import { IconArrowBackUp, IconCheck, IconCornerDownRight, IconPencil, IconTrash } from '@tabler/icons-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { useDeleteFeedback, useFeedbackItem, usePatchFeedback } from '../api/queries'
import { SELF, type FeedbackItem, type FeedbackStatus } from '../api/types'
import { describeAnchor } from '../docs/anchors'
import { MarkdownView } from '../docs/MarkdownView'
import { formatDate } from '../lib/format'
import { ProjectBadge, StatusBadge } from './FeedbackCard'
import { FeedbackForm, type FeedbackDraft } from './FeedbackForm'
import { KIND_LABEL, docLink } from './labels'

function ItemView({ item, current }: { item: FeedbackItem; current: boolean }) {
  const patch = usePatchFeedback()
  const remove = useDeleteFeedback()
  const navigate = useNavigate()
  const [editing, setEditing] = useState(false)
  const [body, setBody] = useState(item.body)
  const link = docLink(item)
  const setStatus = (status: FeedbackStatus) => patch.mutate({ id: item.id, status })
  const error = patch.error ?? remove.error

  return (
    <Card withBorder padding="md" radius="md" style={current ? { borderColor: 'var(--mantine-primary-color-filled)' } : undefined}>
      <Stack gap="xs">
        <Group justify="space-between">
          <Group gap="xs">
            <Anchor component={Link} to={`/feedback/${item.id}`} fw={700}>
              #{item.id}
            </Anchor>
            <Badge variant="outline" size="sm">
              {KIND_LABEL[item.kind]}
            </Badge>
            <StatusBadge item={item} />
            {item.source !== SELF && <ProjectBadge id={item.source} />}
          </Group>
          <Text size="xs" c="dimmed">
            {formatDate(item.created_at)}
          </Text>
        </Group>
        {item.doc_path && link && (
          <Text size="sm">
            <Anchor component={Link} to={link}>
              {item.doc_path}
            </Anchor>{' '}
            · {describeAnchor(item.anchor)}
            {item.doc_rev && (
              <Text span size="xs" c="dimmed">
                {' '}
                (written at {item.doc_rev.slice(0, 8)})
              </Text>
            )}
          </Text>
        )}
        {item.anchor?.quote && (
          <Blockquote p="xs" style={{ whiteSpace: 'pre-wrap' }}>
            <Text size="sm">{item.anchor.quote}</Text>
          </Blockquote>
        )}
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
          <MarkdownView content={item.body} docPath={item.doc_path ?? 'README.md'} source={item.source} compact />
        )}
        {item.reply && (
          <Paper withBorder p="sm" radius="md" bg="var(--mantine-color-green-light)">
            <Text size="xs" fw={700} c="green" mb={4}>
              Claude replied {item.answered_at ? formatDate(item.answered_at) : ''}
            </Text>
            <MarkdownView content={item.reply} docPath={item.doc_path ?? 'README.md'} source={item.source} compact />
          </Paper>
        )}
        {item.status === 'in_progress' && (
          <Text size="sm" c="yellow">
            Claude is working on this (claimed {formatDate(item.claimed_at)}).
          </Text>
        )}
        {error && <Alert color="red">{error.message}</Alert>}
        <Group gap="xs">
          {item.status === 'answered' && (
            <Button size="xs" leftSection={<IconCheck size={14} />} onClick={() => setStatus('resolved')}>
              Resolve
            </Button>
          )}
          {(item.status === 'answered' || item.status === 'resolved') && (
            <Button size="xs" variant="default" leftSection={<IconArrowBackUp size={14} />} onClick={() => setStatus('open')}>
              Reopen
            </Button>
          )}
          {item.status === 'in_progress' && (
            <Button size="xs" variant="default" onClick={() => setStatus('open')}>
              Release the claim
            </Button>
          )}
          {item.status === 'open' && !editing && (
            <>
              <Button size="xs" variant="default" leftSection={<IconPencil size={14} />} onClick={() => setEditing(true)}>
                Edit
              </Button>
              <Button size="xs" variant="default" onClick={() => setStatus('resolved')}>
                Dismiss
              </Button>
              <Button
                size="xs"
                color="red"
                variant="subtle"
                leftSection={<IconTrash size={14} />}
                loading={remove.isPending}
                onClick={() => {
                  if (window.confirm(`Delete feedback #${item.id}?`))
                    remove.mutate(item.id, { onSuccess: () => current && navigate('/feedback') })
                }}
              >
                Delete
              </Button>
            </>
          )}
        </Group>
      </Stack>
    </Card>
  )
}

export function ThreadPage() {
  const id = Number(useParams().id)
  const query = useFeedbackItem(id)
  const [draft, setDraft] = useState<FeedbackDraft | null>(null)

  if (query.isPending) return <Loader />
  if (query.isError) return <Alert color="yellow">Feedback #{Number.isFinite(id) ? id : '?'} wasn't found.</Alert>

  const { item, thread } = query.data
  const last = thread[thread.length - 1] ?? item
  return (
    <Stack maw={900}>
      <Group justify="space-between">
        <Title order={2}>{thread.length > 1 ? `Thread (${thread.length})` : `Feedback #${item.id}`}</Title>
        <Anchor component={Link} to="/feedback" size="sm">
          All feedback
        </Anchor>
      </Group>
      {thread.map((t) => (
        <ItemView key={`${t.id}:${t.updated_at}`} item={t} current={t.id === item.id} />
      ))}
      <Button
        variant="light"
        w="fit-content"
        leftSection={<IconCornerDownRight size={16} />}
        onClick={() =>
          setDraft({ kind: last.kind, source: last.source, docPath: last.doc_path, anchor: last.anchor, parentId: last.id })
        }
      >
        Follow up
      </Button>
      <FeedbackForm draft={draft} onClose={() => setDraft(null)} />
    </Stack>
  )
}
