import { Button, Drawer, Group, Loader, SegmentedControl, Stack, Text, UnstyledButton } from '@mantine/core'
import { IconMessagePlus } from '@tabler/icons-react'
import { useState } from 'react'
import { useFeedbackList } from '../api/queries'
import type { Anchor } from '../api/types'
import { FeedbackCard } from './FeedbackCard'

type Props = {
  path: string
  opened: boolean
  onClose: () => void
  onLocate: (anchor: Anchor) => void
  onNew: () => void
}

export function DocFeedbackPanel({ path, opened, onClose, onLocate, onNew }: Props) {
  const [filter, setFilter] = useState<'active' | 'all'>('active')
  const list = useFeedbackList({ doc_path: path }, opened)
  const items = (list.data ?? []).filter((i) => filter === 'all' || i.status !== 'resolved')

  return (
    <Drawer opened={opened} onClose={onClose} position="right" size="md" title="Feedback on this doc">
      <Stack gap="sm">
        <Group justify="space-between">
          <SegmentedControl
            size="xs"
            value={filter}
            onChange={(v) => setFilter(v as typeof filter)}
            data={[
              { value: 'active', label: 'Not resolved' },
              { value: 'all', label: 'All' },
            ]}
          />
          <Button size="xs" leftSection={<IconMessagePlus size={14} />} onClick={onNew}>
            Review this doc
          </Button>
        </Group>
        <Text size="xs" c="dimmed">
          Hover a block and click the comment icon, or select text, to comment on a specific spot.
        </Text>
        {list.isPending && <Loader size="sm" />}
        {list.data && items.length === 0 && <Text c="dimmed">Nothing here yet.</Text>}
        {items.map((item) => (
          <UnstyledButton
            key={item.id}
            onClick={() => item.anchor && onLocate(item.anchor)}
            title={item.anchor ? 'Show in the doc' : undefined}
          >
            <FeedbackCard item={item} showDoc={false} />
          </UnstyledButton>
        ))}
      </Stack>
    </Drawer>
  )
}
