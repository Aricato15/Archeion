import { Alert, Button, Group, Modal, Stack, Text } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconTrash } from '@tabler/icons-react'
import { useState } from 'react'
import { useRemoveProject } from '../api/queries'
import type { Project } from '../api/types'

/**
 * Take a project out of the registry (ADR 0026). Only its registry page moves, to `registry/removed/`;
 * the project's own folder and the notes kept for it stay as they are.
 */
export function RemoveProject({
  project,
  onRemoved,
  size = 'xs',
}: {
  project: Pick<Project, 'id' | 'children' | 'used_by'>
  onRemoved?: () => void
  size?: 'xs' | 'sm'
}) {
  const [open, setOpen] = useState(false)
  const remove = useRemoveProject()
  const blocked = project.children.length > 0
  return (
    <>
      <Button size={size} variant="subtle" color="red" leftSection={<IconTrash size={14} />} onClick={() => setOpen(true)}>
        Remove
      </Button>
      <Modal opened={open} onClose={() => setOpen(false)} title={`Remove ${project.id} from Archeion?`}>
        <Stack gap="sm">
          {blocked ? (
            <Alert color="orange">
              {project.id} still has {project.children.join(', ')} under it. Remove {project.children.length === 1 ? 'that' : 'those'}{' '}
              first.
            </Alert>
          ) : (
            <>
              <Text size="sm">
                Its registry page moves to <code>registry/removed/</code>, so it's out of the maps and lists. The project's own
                folder is never touched. Its studies, designs, glossary, reports and feedback stay where they are and come back
                if you register it again.
              </Text>
              {project.used_by.length > 0 && (
                <Alert color="yellow">
                  {project.used_by.join(', ')} list{project.used_by.length === 1 ? 's' : ''} it under <code>depends_on</code>.
                  They'll show a warning until you update them.
                </Alert>
              )}
            </>
          )}
          {remove.isError && <Alert color="red">{remove.error.message}</Alert>}
          <Group justify="flex-end" gap="xs">
            <Button variant="default" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              color="red"
              disabled={blocked}
              loading={remove.isPending}
              onClick={() =>
                remove.mutate(project.id, {
                  onSuccess: () => {
                    setOpen(false)
                    notifications.show({ color: 'green', message: `Removed ${project.id}. Its page is in registry/removed/.` })
                    onRemoved?.()
                  },
                })
              }
            >
              Remove project
            </Button>
          </Group>
        </Stack>
      </Modal>
    </>
  )
}
