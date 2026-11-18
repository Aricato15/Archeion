import { Alert, Button, Checkbox, Group, Modal, SegmentedControl, Select, Stack, Text, Textarea, TextInput } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconPlus } from '@tabler/icons-react'
import { useState } from 'react'
import { useNavigate } from 'react-router'
import { useCreateProject, useRootsSettings } from '../api/queries'
import type { Registry } from '../api/types'
import { projectUrl } from '../docs/links'

const NAME_RE = /^[a-z0-9][a-z0-9._-]{0,63}$/

/**
 * Create a new project or group in a granted root (ADR 0028): a new folder with a README.md and a
 * CLAUDE.md, optionally a git repository, and its registry page. It never writes into a folder that exists.
 */
export function NewProject({ registry }: { registry: Registry }) {
  const [open, setOpen] = useState(false)
  const roots = useRootsSettings()
  const create = useCreateProject()
  const navigate = useNavigate()
  const [kind, setKind] = useState<'project' | 'group'>('project')
  const [root, setRoot] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [status, setStatus] = useState('planned')
  const [group, setGroup] = useState<string | null>(null)
  const [inside, setInside] = useState(false)
  const [git, setGit] = useState(true)

  const granted = [...(roots.data?.workspace ? [{ ...roots.data.workspace, name: 'workspace' }] : []), ...(roots.data?.roots ?? [])]
  const chosenRoot = root ?? granted[0]?.name ?? null
  const host = group ? registry.groups.find((g) => g.id === group) : undefined
  const hostHome = host?.home ? registry.projects.find((p) => p.id === host.home) : undefined
  const canInside = Boolean(hostHome?.available)
  const useInside = inside && canInside
  const nameOk = NAME_RE.test(name)
  const taken = registry.projects.some((p) => p.id === name) || registry.groups.some((g) => g.id === name)
  const ready = nameOk && !taken && (useInside || chosenRoot !== null)

  const reset = () => {
    setName('')
    setTitle('')
    setDescription('')
    setGroup(null)
    setInside(false)
  }

  const where = useInside ? `${group}/${name || '<name>'}` : `${chosenRoot ?? '<root>'}/${name || '<name>'}`

  return (
    <>
      <Button size="xs" leftSection={<IconPlus size={14} />} onClick={() => setOpen(true)}>
        New project or group
      </Button>
      <Modal opened={open} onClose={() => setOpen(false)} title="New project or group" size="lg">
        <Stack gap="sm">
          <SegmentedControl
            size="xs"
            value={kind}
            onChange={(v) => {
              setKind(v as 'project' | 'group')
              if (v === 'group') {
                setGroup(null)
                setInside(false)
              }
            }}
            data={[
              { value: 'project', label: 'Project' },
              { value: 'group', label: 'Group (a system of projects)' },
            ]}
          />
          {granted.length === 0 && !useInside && (
            <Alert color="orange">No root is granted yet, so there's nowhere to create it. Add one on the Settings page.</Alert>
          )}
          <Select
            label="Root"
            description="The granted folder it's created in"
            data={granted.map((r) => ({ value: r.name, label: `${r.name} (${r.folder})` }))}
            value={useInside ? null : chosenRoot}
            onChange={setRoot}
            disabled={useInside}
            allowDeselect={false}
          />
          <TextInput
            label="Name"
            description="The folder and registry name: lowercase letters, digits, . _ -"
            value={name}
            onChange={(e) => setName(e.currentTarget.value)}
            error={name && !nameOk ? 'Lowercase letters, digits, . _ - (up to 64)' : taken ? 'Already a project or group' : undefined}
          />
          <TextInput label="Title (optional)" value={title} onChange={(e) => setTitle(e.currentTarget.value)} maxLength={100} />
          <Textarea
            label="Brief description"
            description="Goes into the README, the CLAUDE.md and the registry page"
            autosize
            minRows={2}
            maxLength={2000}
            value={description}
            onChange={(e) => setDescription(e.currentTarget.value)}
          />
          <Select
            label="Status"
            data={['planned', 'active', 'paused', 'archived']}
            value={status}
            onChange={(v) => setStatus(v ?? 'planned')}
            allowDeselect={false}
          />
          {kind === 'project' && (
            <>
              <Select
                label="Member of a group (optional)"
                description="It can sit anywhere: a project used by a group doesn't have to live in its folder"
                clearable
                data={registry.groups.map((g) => ({ value: g.id, label: g.title }))}
                value={group}
                onChange={(v) => {
                  setGroup(v)
                  setInside(false)
                }}
              />
              {group && (
                <Checkbox
                  label="Create it inside the group's folder"
                  description={
                    canInside
                      ? 'As a module, or a sub-project when it gets a git repository of its own'
                      : "This group has no folder on this machine, so it's linked with group: instead"
                  }
                  checked={useInside}
                  disabled={!canInside}
                  onChange={(e) => setInside(e.currentTarget.checked)}
                />
              )}
            </>
          )}
          <Checkbox label="Run git init" checked={git} onChange={(e) => setGit(e.currentTarget.checked)} />
          <Text size="xs" c="dimmed">
            Creates <code>{where}/</code> with README.md and CLAUDE.md{git ? ', a git repository' : ''}, and its registry page. It
            never writes into a folder that already exists.
          </Text>
          {create.isError && <Alert color="red">{create.error.message}</Alert>}
          <Group justify="flex-end" gap="xs">
            <Button variant="default" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              disabled={!ready}
              loading={create.isPending}
              onClick={() =>
                create.mutate(
                  {
                    root: useInside ? null : chosenRoot,
                    name,
                    kind,
                    title: title.trim() || null,
                    description: description.trim() || null,
                    status,
                    group,
                    inside_group: useInside,
                    git_init: git,
                  },
                  {
                    onSuccess: (r) => {
                      setOpen(false)
                      reset()
                      notifications.show({
                        color: 'green',
                        title: `Created ${r.name}`,
                        message: `In ${r.location}. Design it from its Design tab when you're ready.`,
                      })
                      navigate(projectUrl(r.name))
                    },
                  },
                )
              }
            >
              Create
            </Button>
          </Group>
        </Stack>
      </Modal>
    </>
  )
}
