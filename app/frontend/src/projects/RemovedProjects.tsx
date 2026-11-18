import { Alert, Badge, Button, Card, Code, Group, Modal, Stack, Table, Text, Title } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconArrowBackUp, IconTrash } from '@tabler/icons-react'
import { useState } from 'react'
import { usePurgeProject, useRemoved, useRestoreProject } from '../api/queries'
import type { RemovedProject } from '../api/types'

const KEPT_LABEL: Record<string, string> = {
  studies: 'studies',
  designs: 'designs',
  glossary: 'glossary',
  reports: 'reports',
}

function Row({ item }: { item: RemovedProject }) {
  const restore = useRestoreProject()
  const purge = usePurgeProject()
  const [confirm, setConfirm] = useState(false)
  return (
    <Table.Tr>
      <Table.Td>
        <Text fw={600} size="sm">
          {item.name}
        </Text>
        {item.path && (
          <Text size="xs" c="dimmed">
            <Code>{item.path}</Code>
          </Text>
        )}
      </Table.Td>
      <Table.Td>
        <Text size="sm">{item.removed_on}</Text>
      </Table.Td>
      <Table.Td>
        {item.kept.length === 0 ? (
          <Text size="xs" c="dimmed">
            only its page
          </Text>
        ) : (
          <Group gap={4}>
            {item.kept.map((k) => (
              <Badge key={k} size="sm" variant="light" color="gray">
                {KEPT_LABEL[k] ?? k}
              </Badge>
            ))}
          </Group>
        )}
      </Table.Td>
      <Table.Td>
        <Group gap="xs" justify="flex-end" wrap="nowrap">
          <Button
            size="xs"
            variant="light"
            leftSection={<IconArrowBackUp size={14} />}
            loading={restore.isPending}
            onClick={() =>
              restore.mutate(item.name, {
                onSuccess: () => notifications.show({ color: 'green', message: `Restored ${item.name}.` }),
                onError: (err) => notifications.show({ color: 'red', title: 'Not restored', message: err.message }),
              })
            }
          >
            Restore
          </Button>
          <Button size="xs" variant="subtle" color="red" leftSection={<IconTrash size={14} />} onClick={() => setConfirm(true)}>
            Delete permanently
          </Button>
        </Group>
        <Modal opened={confirm} onClose={() => setConfirm(false)} title={`Delete ${item.name} permanently?`}>
          <Stack gap="sm">
            <Text size="sm">
              This deletes its removed page
              {item.kept.length > 0 && <> and the {item.kept.map((k) => KEPT_LABEL[k] ?? k).join(', ')} the registry kept for it</>}. It
              can't be undone. The project's own folder and any feedback about it are left alone.
            </Text>
            {purge.isError && <Alert color="red">{purge.error.message}</Alert>}
            <Group justify="flex-end" gap="xs">
              <Button variant="default" onClick={() => setConfirm(false)}>
                Cancel
              </Button>
              <Button
                color="red"
                loading={purge.isPending}
                onClick={() =>
                  purge.mutate(item.name, {
                    onSuccess: () => {
                      setConfirm(false)
                      notifications.show({ color: 'green', message: `Deleted ${item.name} permanently.` })
                    },
                  })
                }
              >
                Delete permanently
              </Button>
            </Group>
          </Stack>
        </Modal>
      </Table.Td>
    </Table.Tr>
  )
}

/** Projects that were removed (ADR 0026) and not registered since: put one back, or delete it for good. */
export function RemovedProjects() {
  const removed = useRemoved()
  const items = removed.data ?? []
  if (items.length === 0) return null
  return (
    <Card withBorder>
      <Stack gap="xs">
        <div>
          <Group gap="xs">
            <Title order={4}>Previously registered</Title>
            <Badge variant="light" color="gray">
              {items.length}
            </Badge>
          </Group>
          <Text size="sm" c="dimmed">
            Removed projects are kept in the registry's <Code>removed</Code> folder, with their studies, designs, glossary
            and reports. Restore one to bring it back as it was, or delete it permanently.
          </Text>
        </div>
        <Table>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Project</Table.Th>
              <Table.Th>Removed</Table.Th>
              <Table.Th>Still kept</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {items.map((i) => (
              <Row key={i.name} item={i} />
            ))}
          </Table.Tbody>
        </Table>
      </Stack>
    </Card>
  )
}
