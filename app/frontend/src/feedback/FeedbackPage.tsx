import { Button, Group, Loader, SegmentedControl, Select, Stack, Text, Title } from '@mantine/core'
import { IconPlus } from '@tabler/icons-react'
import { useState } from 'react'
import { useSearchParams } from 'react-router'
import { useFeedbackList, useFeedbackSummary } from '../api/queries'
import type { FeedbackKind, FeedbackStatus } from '../api/types'
import { FeedbackCard } from './FeedbackCard'
import { FeedbackForm, type FeedbackDraft } from './FeedbackForm'
import { KIND_LABEL, STATUS_LABEL } from './labels'

const STATUSES: FeedbackStatus[] = ['open', 'in_progress', 'answered', 'resolved']

export function FeedbackPage() {
  const [params, setParams] = useSearchParams()
  const status = (params.get('status') as FeedbackStatus | 'all' | null) ?? 'all'
  const kind = (params.get('kind') as FeedbackKind | null) ?? null
  const list = useFeedbackList({ status: status === 'all' ? undefined : status, kind: kind ?? undefined })
  const summary = useFeedbackSummary()
  const [draft, setDraft] = useState<FeedbackDraft | null>(null)

  const setParam = (key: string, value: string | null) => {
    const next = new URLSearchParams(params)
    if (value && value !== 'all') next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  return (
    <Stack maw={900}>
      <Group justify="space-between">
        <Title order={2}>Feedback</Title>
        <Button leftSection={<IconPlus size={16} />} onClick={() => setDraft({ kind: 'prompt', pickDoc: true })}>
          New prompt
        </Button>
      </Group>
      <Text c="dimmed" size="sm">
        Everything here waits in Claude's inbox. In a Claude Code session in this repo, run <b>/inbox</b>: Claude
        claims each open item, does the work and replies here.
      </Text>
      <Group>
        <SegmentedControl
          value={status}
          onChange={(v) => setParam('status', v)}
          data={[
            { value: 'all', label: 'All' },
            ...STATUSES.map((s) => ({
              value: s,
              label: `${STATUS_LABEL[s]}${summary.data ? ` (${summary.data[s]})` : ''}`,
            })),
          ]}
        />
        <Select
          placeholder="Any kind"
          clearable
          w={160}
          value={kind}
          onChange={(v) => setParam('kind', v)}
          data={(['comment', 'review', 'prompt'] as const).map((k) => ({ value: k, label: KIND_LABEL[k] }))}
        />
      </Group>
      {list.isPending && <Loader />}
      {list.data?.length === 0 && <Text c="dimmed">No feedback matches.</Text>}
      {list.data?.map((item) => <FeedbackCard key={item.id} item={item} />)}
      <FeedbackForm draft={draft} onClose={() => setDraft(null)} />
    </Stack>
  )
}
