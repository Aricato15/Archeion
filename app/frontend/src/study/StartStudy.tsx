import { Alert, Button, Group, Modal, Stack, Text, Textarea } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconMicroscope } from '@tabler/icons-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { useCreateFeedback, useResponder } from '../api/queries'
import { SELF } from '../api/types'

/**
 * Starts a study as a conversation (ADR 0020): a thread for Archeion anchored to the task. Claude
 * answers each round with findings, the draft and its questions; the user replies until it's done.
 */
export function StartStudyButton({
  project,
  refresh = false,
  variant = 'filled',
}: {
  project: string
  refresh?: boolean
  variant?: 'filled' | 'default'
}) {
  const [open, setOpen] = useState(false)
  const [focus, setFocus] = useState('')
  const create = useCreateFeedback()
  const responder = useResponder()
  const navigate = useNavigate()
  const onDemand = responder.data?.enabled ?? false

  const submit = () => {
    const ask = refresh
      ? `Refresh the study of ${project}: reread what changed since the last snapshot.`
      : `Study ${project}.`
    const body = focus.trim() ? `${ask}\n\nFocus on: ${focus.trim()}` : ask
    create.mutate(
      { kind: 'prompt', source: SELF, body, anchor: { task: { type: 'study', project } } },
      {
        onSuccess: (item) => {
          setOpen(false)
          setFocus('')
          notifications.show({
            color: 'green',
            title: 'Study started',
            message: onDemand
              ? 'On-demand Claude picks it up in a moment. Its findings and questions arrive in this thread.'
              : "It's in Archeion's inbox. Run /inbox there, or switch on On-demand Claude in Settings.",
          })
          navigate(`/feedback/${item.id}`)
        },
      },
    )
  }

  return (
    <>
      <Button size="xs" variant={variant} leftSection={<IconMicroscope size={14} />} onClick={() => setOpen(true)}>
        {refresh ? 'Ask for a refresh' : `Ask Claude to study ${project}`}
      </Button>
      <Modal opened={open} onClose={() => setOpen(false)} title={refresh ? `Refresh the study of ${project}` : `Study ${project}`}>
        <Stack gap="sm">
          <Text size="sm">
            This starts a conversation with Claude in a thread. Each round it reports what it found, shows the draft on
            this tab and asks what it needs to know. You answer in the thread, and it saves the study once you say it's
            done.
          </Text>
          <Textarea
            label="Anything to focus on? (optional)"
            placeholder="e.g. the sync job, and how it talks to the other services"
            autosize
            minRows={2}
            value={focus}
            onChange={(e) => setFocus(e.currentTarget.value)}
          />
          {!onDemand && (
            <Alert color="gray" variant="light">
              On-demand Claude is off, so the thread waits for <code>/inbox</code> in Archeion's terminal. Switch it on in{' '}
              <Link to="/settings#on-demand">Settings</Link> to have each round answered as soon as you reply.
            </Alert>
          )}
          {create.error && <Alert color="red">{create.error.message}</Alert>}
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={submit} loading={create.isPending}>
              Start
            </Button>
          </Group>
        </Stack>
      </Modal>
    </>
  )
}
