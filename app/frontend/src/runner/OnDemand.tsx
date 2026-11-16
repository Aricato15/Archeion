import { Alert, Badge, Button, Card, Group, Stack, Switch, Text, Title, Tooltip } from '@mantine/core'
import { IconBolt, IconPlayerPlay, IconPlayerStop } from '@tabler/icons-react'
import { useEffect, useRef } from 'react'
import { Link, useLocation } from 'react-router'
import { isNotFound } from '../api/client'
import { useResponder, useRunResponder, useSetResponder, useStopResponder } from '../api/queries'
import { timeAgo } from '../lib/format'

/**
 * Settings card: on-demand Claude (ADR 0020). When it's on, the backend opens a window running
 * `claude -p "/inbox"` as soon as a new message waits, and the window closes when the run ends.
 * Never alongside the inbox terminal: one Claude job at a time.
 */
export function OnDemandCard() {
  const status = useResponder()
  const toggle = useSetResponder()
  const run = useRunResponder()
  const stop = useStopResponder()
  const data = status.data
  const { hash } = useLocation()
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (hash === '#on-demand' && data) ref.current?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
  }, [hash, data])
  const error = toggle.error ?? run.error ?? stop.error

  return (
    <Card withBorder id="on-demand" ref={ref}>
      <Stack gap="sm">
        <Group justify="space-between" wrap="wrap">
          <Group gap="xs">
            <IconBolt size={20} />
            <Title order={3}>On-demand Claude</Title>
            {data && (
              <Badge
                color={data.running ? 'green' : data.enabled ? 'blue' : 'gray'}
                variant={data.running ? 'filled' : 'light'}
              >
                {data.running ? 'working' : data.enabled ? 'on, idle' : 'off'}
              </Badge>
            )}
          </Group>
          {data && (
            <Group gap="xs">
              <Tooltip label={data.reason ?? ''} disabled={data.can_start || data.enabled} multiline w={260}>
                <Switch
                  label="Answer new messages"
                  checked={data.enabled}
                  disabled={toggle.isPending || (!data.enabled && !data.can_start)}
                  onChange={(e) => toggle.mutate({ enabled: e.currentTarget.checked })}
                />
              </Tooltip>
              {data.running ? (
                <Button
                  size="xs"
                  color="red"
                  variant="light"
                  leftSection={<IconPlayerStop size={14} />}
                  loading={stop.isPending}
                  onClick={() => stop.mutate()}
                >
                  Stop {data.jobs.length > 1 ? 'these runs' : 'this run'}
                </Button>
              ) : (
                <Tooltip label={data.reason ?? 'Answer the inbox once, now'} multiline w={260}>
                  <Button
                    size="xs"
                    variant="default"
                    leftSection={<IconPlayerPlay size={14} />}
                    loading={run.isPending}
                    disabled={!data.can_start}
                    onClick={() => run.mutate()}
                  >
                    Run now
                  </Button>
                </Tooltip>
              )}
            </Group>
          )}
        </Group>
        <Text size="sm" c="dimmed">
          When it's on, Archeion starts Claude as soon as a new message waits: a new thread, a reply, or a study started
          from a project's Study tab. By default it opens a window running <code>cmd /c claude "/inbox"</code>, so you can
          watch it think and work, and closes it when its turn ends. With <b>Headless</b> (Claude jobs, above) nothing
          opens and every step goes to a log. Messages Claude leaves open on purpose don't start a run. It may use
          Archeion's CLI, and edits files as the <b>Edits</b> setting says; in a window you can approve anything else,
          headless it says in its reply what it couldn't run.
        </Text>
        {data && (
          <Text size="sm">
            {data.running
              ? data.jobs
                  .map((j) => `${j.mode === 'headless' ? 'Headless run' : 'Window'} working since ${timeAgo(j.started_at)}.`)
                  .join(' ')
              : data.last_run_at
                ? `Last run ${timeAgo(data.last_run_at)}.`
                : "It hasn't run yet."}{' '}
            {data.waiting > 0 && `${data.waiting} new message(s) waiting.`}
          </Text>
        )}
        {data && !data.can_start && !data.running && (
          <Alert color="gray" variant="light">
            {data.reason}{' '}
            {data.reason?.includes('inbox terminal') && <Link to="/settings#inbox-terminal">Inbox terminal</Link>}
          </Alert>
        )}
        {status.isError && (
          <Alert color="orange" title="On-demand Claude isn't available">
            {isNotFound(status.error)
              ? "The backend that's running doesn't have it yet: it was started before this version. Restart Archeion (restart.bat)."
              : status.error.message}
          </Alert>
        )}
        {error && <Alert color="red">{error.message}</Alert>}
      </Stack>
    </Card>
  )
}

/** Header badge while on-demand Claude is on or working. */
export function OnDemandBadge() {
  const status = useResponder()
  if (!status.data || (!status.data.enabled && !status.data.running)) return null
  const { running } = status.data
  return (
    <Tooltip label={running ? 'On-demand Claude is answering the inbox' : 'On-demand Claude answers new messages'}>
      <Badge
        component={Link}
        to="/settings#on-demand"
        variant={running ? 'filled' : 'dot'}
        color={running ? 'green' : 'blue'}
        style={{ cursor: 'pointer' }}
        visibleFrom="sm"
      >
        {running ? 'Claude working' : 'on demand'}
      </Badge>
    </Tooltip>
  )
}
