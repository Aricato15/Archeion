import { Alert, Badge, Button, Checkbox, Group, Loader, Modal, Stack, Text, TextInput } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconSitemap } from '@tabler/icons-react'
import { useState } from 'react'
import { useBreakDown, useBreakDownPlan } from '../api/queries'
import type { Project } from '../api/types'

/**
 * Register folders of a group as its members (ADR 0027). They come from the group's own study: the
 * folder each top-level component's files sit in. A folder without a repository of its own becomes a
 * module, otherwise a sub-project. Only registry pages are created; nothing in the project changes.
 */
export function BreakDown({ group }: { group: Project }) {
  const [open, setOpen] = useState(false)
  const plan = useBreakDownPlan(group.id, open)
  const register = useBreakDown()
  const [names, setNames] = useState<Record<string, string>>({})
  const [off, setOff] = useState<Set<string>>(new Set())

  const items = plan.data ?? []
  const chosen = items.filter((i) => !off.has(i.folder))
  const nameOf = (i: { folder: string; name: string }) => names[i.folder] ?? i.name

  return (
    <>
      <Button size="xs" variant="default" leftSection={<IconSitemap size={14} />} onClick={() => setOpen(true)}>
        Break down
      </Button>
      <Modal opened={open} onClose={() => setOpen(false)} title={`Break ${group.id} down into members`} size="lg">
        <Stack gap="sm">
          {plan.isPending && <Loader size="sm" />}
          {plan.isError && <Alert color="red">{plan.error.message}</Alert>}
          {plan.data && items.length === 0 && (
            <Alert color="gray">
              Nothing to suggest. The suggestions come from the group&apos;s own study, so study {group.id} first (its
              top-level components need file paths inside the group&apos;s folder), or register folders on the Settings page.
            </Alert>
          )}
          {items.length > 0 && (
            <>
              <Text size="sm">
                Folders of {group.id} that its study points at. Each becomes a member: a module when it has no repository of
                its own, a sub-project when it does. Only registry pages are created.
              </Text>
              {items.map((i) => (
                <Group key={i.folder} wrap="nowrap" align="flex-end">
                  <Checkbox
                    aria-label={`Register ${i.folder}`}
                    checked={!off.has(i.folder)}
                    onChange={(e) => {
                      const on = e.currentTarget.checked
                      setOff((prev) => {
                        const next = new Set(prev)
                        if (on) next.delete(i.folder)
                        else next.add(i.folder)
                        return next
                      })
                    }}
                  />
                  <TextInput
                    size="xs"
                    label={`${i.folder}/`}
                    description={`from ${i.components.join(', ')}`}
                    value={nameOf(i)}
                    onChange={(e) => {
                      const value = e.currentTarget.value
                      setNames((prev) => ({ ...prev, [i.folder]: value }))
                    }}
                    style={{ flex: 1 }}
                  />
                  <Badge variant="light" color={i.type === 'module' ? 'grape' : 'blue'}>
                    {i.type}
                  </Badge>
                </Group>
              ))}
            </>
          )}
          {register.isError && <Alert color="red">{register.error.message}</Alert>}
          <Group justify="flex-end" gap="xs">
            <Button variant="default" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              disabled={chosen.length === 0}
              loading={register.isPending}
              onClick={() =>
                register.mutate(
                  { group: group.id, members: chosen.map((i) => ({ folder: i.folder, name: nameOf(i) })) },
                  {
                    onSuccess: (r) => {
                      setOpen(false)
                      notifications.show({
                        color: 'green',
                        message: `Registered ${r.pages.length} member(s). Study them, then restudy ${group.id}.`,
                      })
                    },
                  },
                )
              }
            >
              Register {chosen.length || ''} member{chosen.length === 1 ? '' : 's'}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </>
  )
}
