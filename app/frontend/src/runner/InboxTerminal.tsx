import { Alert, Badge, Button, Card, Code, Group, Select, Stack, Text, Title, Tooltip } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconPlayerPlay, IconPlayerStop, IconRefresh, IconTerminal } from '@tabler/icons-react'
import { useEffect, useRef } from 'react'
import { Link, useLocation } from 'react-router'
import { useRunner, useSetRunnerInterval, useStartRunner, useStopRunner } from '../api/queries'
import { timeAgo } from '../lib/format'

const PRESETS = ['5m', '10m', '15m', '30m', '1h', '2h']
const LABELS: Record<string, string> = { m: 'minutes', h: 'hours' }

const describe = (interval: string) => {
  const m = interval.match(/^(\d+)([mh])$/)
  if (!m) return interval
  const n = Number(m[1])
  return `every ${n} ${n === 1 ? LABELS[m[2]].slice(0, -1) : LABELS[m[2]]}`
}

/** Settings card: the Claude Code window that runs `/loop <interval> /inbox` (ADR 0013). */
export function InboxTerminalCard() {
  const status = useRunner()
  const saveInterval = useSetRunnerInterval()
  const start = useStartRunner()
  const stop = useStopRunner()
  const data = status.data
  const { hash } = useLocation()
  const ref = useRef<HTMLDivElement>(null)
  // The header badge links here.
  useEffect(() => {
    if (hash === '#inbox-terminal' && data) ref.current?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
  }, [hash, data])
  const busy = start.isPending || stop.isPending
  const error = start.error ?? stop.error ?? saveInterval.error

  const restart = () =>
    stop.mutate(undefined, {
      onSuccess: () => start.mutate(undefined, { onSuccess: () => notifications.show({ color: 'green', message: 'Inbox terminal restarted.' }) }),
    })

  return (
    <Card withBorder id="inbox-terminal" ref={ref}>
      <Stack gap="sm">
        <Group justify="space-between" wrap="wrap">
          <Group gap="xs">
            <IconTerminal size={20} />
            <Title order={3}>Inbox terminal</Title>
            {data && (
              <Badge color={data.running ? 'green' : 'gray'} variant={data.running ? 'filled' : 'light'}>
                {data.running ? 'running' : 'stopped'}
              </Badge>
            )}
          </Group>
          {data && (
            <Group gap="xs">
              {data.running ? (
                <>
                  <Button size="xs" variant="default" leftSection={<IconRefresh size={14} />} loading={busy} onClick={restart}>
                    Restart
                  </Button>
                  <Button size="xs" color="red" variant="light" leftSection={<IconPlayerStop size={14} />} loading={busy} onClick={() => stop.mutate()}>
                    Stop
                  </Button>
                </>
              ) : (
                <Tooltip label={data.reason ?? 'Opens a Claude Code window on this machine'} multiline w={260}>
                  <Button
                    size="xs"
                    leftSection={<IconPlayerPlay size={14} />}
                    loading={busy}
                    disabled={!data.can_start}
                    onClick={() => start.mutate(undefined)}
                  >
                    Start
                  </Button>
                </Tooltip>
              )}
            </Group>
          )}
        </Group>
        <Text size="sm" c="dimmed">
          A Claude Code window at Archeion's root that runs <Code>/loop {data?.interval ?? '10m'} /inbox</Code>, so what
          you write in the viewer gets picked up while it's open. File edits still ask for approval in that window. Each
          check is a short Claude turn, even when the inbox is empty. Closing the window stops it; stop.bat leaves it alone.
        </Text>
        {status.isError && <Alert color="red">{status.error.message}</Alert>}
        {data && (
          <Group align="flex-end" wrap="wrap">
            <Select
              label="Check the inbox"
              w={200}
              data={(PRESETS.includes(data.interval) ? PRESETS : [data.interval, ...PRESETS]).map((v) => ({ value: v, label: describe(v) }))}
              value={data.interval}
              allowDeselect={false}
              disabled={saveInterval.isPending}
              onChange={(v) => v && v !== data.interval && saveInterval.mutate(v)}
            />
            {data.running && data.started_at && (
              <Text size="sm" c="dimmed" pb={6}>
                Started {timeAgo(data.started_at)} (PID {data.pid}).
              </Text>
            )}
          </Group>
        )}
        {data?.running && saveInterval.isSuccess && (
          <Text size="sm" c="orange">
            The running terminal keeps its interval until you restart it.
          </Text>
        )}
        {data && !data.can_start && data.reason && !data.running && <Alert color="orange">{data.reason}</Alert>}
        {error && <Alert color="red">{error.message}</Alert>}
      </Stack>
    </Card>
  )
}

/** Header badge: whether the inbox terminal is running. Links to its card. */
export function InboxTerminalBadge() {
  const status = useRunner()
  if (!status.data) return null
  const { running, interval } = status.data
  return (
    <Tooltip label={running ? `Inbox terminal: checking ${describe(interval)}` : 'Inbox terminal is stopped. Start it in Settings.'}>
      <Badge
        component={Link}
        to="/settings#inbox-terminal"
        variant="dot"
        color={running ? 'green' : 'gray'}
        style={{ cursor: 'pointer' }}
        visibleFrom="sm"
      >
        inbox loop
      </Badge>
    </Tooltip>
  )
}
