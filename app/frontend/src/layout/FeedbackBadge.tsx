import { Badge, Group, Tooltip } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { useEffect, useRef } from 'react'
import { Link } from 'react-router'
import { useFeedbackSummary } from '../api/queries'

/** Open and answered counts in the header; notifies when Claude answers something. */
export function FeedbackBadge() {
  const summary = useFeedbackSummary()
  const answered = summary.data?.answered
  const previous = useRef<number | undefined>(undefined)

  useEffect(() => {
    if (answered === undefined) return
    if (previous.current !== undefined && answered > previous.current) {
      notifications.show({
        color: 'green',
        title: 'Claude replied',
        message: 'New answers are waiting in Feedback.',
      })
    }
    previous.current = answered
  }, [answered])

  if (!summary.data) return null
  const { open, in_progress } = summary.data
  return (
    <Group gap={6} visibleFrom="xs">
      <Tooltip label="Waiting for Claude (open + in progress)">
        <Badge component={Link} to="/feedback?status=open" variant="light" color="blue" style={{ cursor: 'pointer' }}>
          {open + in_progress} waiting
        </Badge>
      </Tooltip>
      {summary.data.answered > 0 && (
        <Tooltip label="Answered by Claude, waiting for you to resolve">
          <Badge component={Link} to="/feedback?status=answered" variant="filled" color="green" style={{ cursor: 'pointer' }}>
            {summary.data.answered} answered
          </Badge>
        </Tooltip>
      )}
    </Group>
  )
}
