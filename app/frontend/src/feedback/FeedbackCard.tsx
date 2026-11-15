import { Anchor, Badge, Card, Group, Stack, Text } from '@mantine/core'
import { IconCornerDownRight } from '@tabler/icons-react'
import { Link } from 'react-router'
import { SELF, type FeedbackItem } from '../api/types'
import { describeAnchor } from '../docs/anchors'
import { projectUrl } from '../docs/links'
import { timeAgo } from '../lib/format'
import { KIND_LABEL, STATUS_COLOR, STATUS_LABEL, docLink } from './labels'

export function StatusBadge({ item }: { item: Pick<FeedbackItem, 'status'> }) {
  return (
    <Badge color={STATUS_COLOR[item.status]} variant="light" size="sm">
      {STATUS_LABEL[item.status]}
    </Badge>
  )
}

/** Which project an item targets (archeion items carry no badge). */
export function ProjectBadge({ id }: { id: string }) {
  return (
    <Badge variant="dot" size="sm" color="grape" component={Link} to={projectUrl(id)} style={{ cursor: 'pointer' }}>
      {id}
    </Badge>
  )
}

export function FeedbackCard({ item, showDoc = true }: { item: FeedbackItem; showDoc?: boolean }) {
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
            {item.parent_id && (
              <Group gap={2}>
                <IconCornerDownRight size={14} />
                <Text size="xs" c="dimmed">
                  follow-up of #{item.parent_id}
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
        {!showDoc && item.anchor && (
          <Text size="xs" c="dimmed">
            {describeAnchor(item.anchor)}
          </Text>
        )}
        {item.reply && (
          <Text size="xs" c="green" lineClamp={1}>
            Claude: {item.reply}
          </Text>
        )}
      </Stack>
    </Card>
  )
}
