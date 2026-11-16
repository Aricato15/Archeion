import { Alert, Badge, Card, Group, SegmentedControl, Stack, Switch, Text, Title } from '@mantine/core'
import { IconCpu } from '@tabler/icons-react'
import { useResponder, useSetResponder } from '../api/queries'

/**
 * Settings card (ADR 0021): how Archeion runs Claude. Headless runs open no window; Max Claude
 * instances caps the Claude processes running at once, the inbox terminal included.
 */
export function ClaudeJobsCard() {
  const status = useResponder()
  const save = useSetResponder()
  const data = status.data
  if (!data) return null
  return (
    <Card withBorder id="claude-jobs">
      <Stack gap="sm">
        <Group justify="space-between" wrap="wrap">
          <Group gap="xs">
            <IconCpu size={20} />
            <Title order={3}>Claude jobs</Title>
            <Badge variant="light" color={data.instances ? 'green' : 'gray'}>
              {data.instances} of {data.max_instances} running
            </Badge>
          </Group>
        </Group>
        <Group gap="xl" align="flex-start" wrap="wrap">
          <Stack gap={4}>
            <Text size="sm" fw={500}>
              Max Claude instances
            </Text>
            <SegmentedControl
              size="xs"
              value={String(data.max_instances)}
              disabled={save.isPending}
              onChange={(v) => save.mutate({ max_instances: Number(v) })}
              data={['1', '2']}
            />
            <Text size="xs" c="dimmed" maw={340}>
              Counts the inbox terminal and every on-demand run. With 1 they never run together; with 2 they can, or two
              on-demand runs can answer in parallel.
            </Text>
          </Stack>
          <Stack gap={4}>
            <Text size="sm" fw={500}>
              Edits
            </Text>
            <SegmentedControl
              size="xs"
              value={data.accept_edits ? 'accept' : 'confirm'}
              disabled={save.isPending}
              onChange={(v) => save.mutate({ accept_edits: v === 'accept' })}
              data={[
                { value: 'accept', label: 'Auto accept edits' },
                { value: 'confirm', label: 'Seek user confirmations', disabled: data.headless },
              ]}
            />
            <Text size="xs" c="dimmed" maw={340}>
              For both the inbox terminal and on-demand runs. Asking first needs someone at the window, so it can't be
              combined with Headless.
            </Text>
          </Stack>
          <Stack gap={4}>
            <Switch
              label="Headless"
              checked={data.headless}
              disabled={save.isPending || (!data.headless && !data.accept_edits)}
              onChange={(e) => save.mutate({ headless: e.currentTarget.checked })}
            />
            <Text size="xs" c="dimmed" maw={360}>
              On-demand runs open no window and log every step (thinking, tool calls, results) to{' '}
              <code>app/backend/data/responder/</code>. Off, each run opens a window you can watch, closed when its turn
              ends. The inbox terminal is always a window: its <code>/loop</code> needs an interactive session.
            </Text>
          </Stack>
        </Group>
        {save.error && <Alert color="red">{save.error.message}</Alert>}
      </Stack>
    </Card>
  )
}
