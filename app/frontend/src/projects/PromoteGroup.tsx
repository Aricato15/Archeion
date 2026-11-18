import { Alert, Button, Group, List, Loader, Modal, Stack, Text } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconStack2 } from '@tabler/icons-react'
import { useState } from 'react'
import { useDemoteProject, usePromotePlan, usePromoteProject } from '../api/queries'
import type { Project } from '../api/types'

/**
 * Promote a project to a group with a home (ADR 0027), or take an empty group back to a project.
 * Only `type:` and `promoted:` on its registry page change: the name, and so its studies, design,
 * glossary, reports and threads, stay as they are.
 */
export function PromoteGroup({ project }: { project: Project }) {
  const [open, setOpen] = useState(false)
  const plan = usePromotePlan(project.id, open && project.type !== 'group')
  const promote = usePromoteProject()
  const demote = useDemoteProject()

  if (project.type === 'group') {
    const blocked = project.members.length > 0
    return (
      <>
        <Button size="xs" variant="subtle" leftSection={<IconStack2 size={14} />} onClick={() => setOpen(true)}>
          Demote to project
        </Button>
        <Modal opened={open} onClose={() => setOpen(false)} title={`Demote ${project.id} to a project?`}>
          <Stack gap="sm">
            {blocked ? (
              <Alert color="orange">
                {project.id} still has {project.members.length} member(s): {project.members.join(', ')}. Move{' '}
                {project.members.length === 1 ? 'it' : 'them'} out first.
              </Alert>
            ) : (
              <Text size="sm">
                <code>type: group</code> and <code>promoted:</code> are removed from its registry page. Nothing else changes.
              </Text>
            )}
            {demote.isError && <Alert color="red">{demote.error.message}</Alert>}
            <Group justify="flex-end" gap="xs">
              <Button variant="default" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button
                disabled={blocked}
                loading={demote.isPending}
                onClick={() =>
                  demote.mutate(project.id, {
                    onSuccess: () => {
                      setOpen(false)
                      notifications.show({ color: 'green', message: `${project.id} is a project again.` })
                    },
                  })
                }
              >
                Demote
              </Button>
            </Group>
          </Stack>
        </Modal>
      </>
    )
  }

  // A module, a sub-project and a member of a group can't be promoted (groups sit at the top and don't nest).
  if (project.type !== 'project' || project.parent || project.group) return null
  const p = plan.data
  return (
    <>
      <Button size="xs" variant="default" leftSection={<IconStack2 size={14} />} onClick={() => setOpen(true)}>
        Promote to group
      </Button>
      <Modal opened={open} onClose={() => setOpen(false)} title={`Promote ${project.id} to a group?`}>
        <Stack gap="sm">
          {plan.isPending && open && <Loader size="sm" />}
          {plan.isError && <Alert color="red">{plan.error.message}</Alert>}
          {p && !p.ok && <Alert color="orange">Can&apos;t promote it: {p.problems.join('; ')}.</Alert>}
          {p?.ok && (
            <>
              <Text size="sm">
                It becomes a group with a home: the same folder and docs, plus members. Only <code>type: group</code> and{' '}
                <code>promoted:</code> are added to its registry page. Nothing in the project is touched.
              </Text>
              <List size="sm" spacing={2}>
                <List.Item>
                  Members: {p.members.length ? p.members.join(', ') : 'none yet (add them with group: or parent:)'}.
                </List.Item>
                {p.group_page && <List.Item>It keeps {p.group_page} as its narrative: one group instead of two pages.</List.Item>}
                {p.has_study && <List.Item>Its study is kept and marked as needing a restudy.</List.Item>}
                {p.has_design && <List.Item>Its design stays with it, under the same name.</List.Item>}
              </List>
            </>
          )}
          {promote.isError && <Alert color="red">{promote.error.message}</Alert>}
          <Group justify="flex-end" gap="xs">
            <Button variant="default" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              disabled={!p?.ok}
              loading={promote.isPending}
              onClick={() =>
                promote.mutate(project.id, {
                  onSuccess: () => {
                    setOpen(false)
                    notifications.show({ color: 'green', message: `${project.id} is now a group.` })
                  },
                })
              }
            >
              Promote
            </Button>
          </Group>
        </Stack>
      </Modal>
    </>
  )
}
