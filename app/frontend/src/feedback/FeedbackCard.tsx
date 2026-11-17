import { Anchor, Badge, Card, Group, Stack, Text } from '@mantine/core'
import { IconMessages } from '@tabler/icons-react'
import { Link } from 'react-router'
import { REGISTRY, SELF, type FeedbackItem, type FeedbackThread } from '../api/types'
import { describeAnchor } from '../docs/anchors'
import { studyUrl } from '../study/links'
import { projectUrl } from '../docs/links'
import { timeAgo } from '../lib/format'
import { KIND_LABEL, STATUS_COLOR, STATUS_LABEL, docLink } from './labels'

/** The project page tab a task's thread is about. */
const taskTab = (type: string) => (type === 'report' ? 'reports' : type === 'study' ? 'study' : 'design')

export function StatusBadge({ item }: { item: Pick<FeedbackItem, 'status'> }) {
  return (
    <Badge color={STATUS_COLOR[item.status]} variant="light" size="sm">
      {STATUS_LABEL[item.status]}
    </Badge>
  )
}

/** Which project an item targets (archeion items carry no badge). */
export function ProjectBadge({ id }: { id: string }) {
  if (id === REGISTRY) {
    return (
      <Badge variant="dot" size="sm" color="grape">
        registry
      </Badge>
    )
  }
  return (
    <Badge variant="dot" size="sm" color="grape" component={Link} to={projectUrl(id)} style={{ cursor: 'pointer' }}>
      {id}
    </Badge>
  )
}

/** Which project's own session sent an item (/archeion:report, ADR 0009). */
export function OriginBadge({ id }: { id: string }) {
  return (
    <Badge variant="light" size="sm" color="teal" component={Link} to={projectUrl(id)} style={{ cursor: 'pointer' }}>
      from {id}
    </Badge>
  )
}

/** A thread in a list: its first request, its status and its latest reply (ADR 0018). */
export function FeedbackCard({ item, showDoc = true }: { item: FeedbackThread; showDoc?: boolean }) {
  const first = item.body.trim().split('\n')[0] ?? ''
  const link = docLink(item)
  return (
    <Card withBorder padding="sm" radius="md">
      <Stack gap={4}>
        <Group justify="space-between" wrap="nowrap">
          <Group gap="xs" wrap="nowrap">
            <Anchor component={Link} to={`/feedback/${item.id}`} fw={600}>
              #{item.id}
            </Anchor>
            <Badge variant="outline" size="sm">
              {KIND_LABEL[item.kind]}
            </Badge>
            <StatusBadge item={item} />
            {item.source !== SELF && <ProjectBadge id={item.source} />}
            {item.origin && <OriginBadge id={item.origin} />}
            {item.messages > 1 && (
              <Group gap={2}>
                <IconMessages size={14} />
                <Text size="xs" c="dimmed">
                  {item.messages} messages
                </Text>
              </Group>
            )}
          </Group>
          <Text size="xs" c="dimmed" style={{ whiteSpace: 'nowrap' }}>
            {timeAgo(item.updated_at)}
          </Text>
        </Group>
        <Text size="sm" lineClamp={2} component={Link} to={`/feedback/${item.id}`} c="inherit">
          {first}
        </Text>
        {showDoc && link && (
          <Text size="xs" c="dimmed">
            <Anchor component={Link} to={link} size="xs">
              {item.doc_path}
            </Anchor>{' '}
            · {describeAnchor(item.anchor)}
          </Text>
        )}
        {item.anchor?.study && (
          <Text size="xs" c="dimmed">
            <Anchor component={Link} to={studyUrl(item.anchor.study)} size="xs">
              {describeAnchor(item.anchor)}
            </Anchor>
          </Text>
        )}
        {item.anchor?.task && (
          <Text size="xs" c="dimmed">
            <Anchor component={Link} to={`/projects/${encodeURIComponent(item.anchor.task.project)}?tab=${taskTab(item.anchor.task.type)}`} size="xs">
              {describeAnchor(item.anchor)}
            </Anchor>
          </Text>
        )}
        {!showDoc && item.anchor && !item.anchor.study && !item.anchor.task && (
          <Text size="xs" c="dimmed">
            {describeAnchor(item.anchor)}
          </Text>
        )}
        {item.reply && (
          <Text size="xs" c="green" lineClamp={1}>
            Claude{item.messages > 1 ? ' (latest)' : ''}: {item.reply}
          </Text>
        )}
      </Stack>
    </Card>
  )
}
