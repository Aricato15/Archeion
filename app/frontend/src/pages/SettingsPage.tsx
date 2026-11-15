import {
  ActionIcon,
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Code,
  Group,
  List,
  Loader,
  SegmentedControl,
  Stack,
  Switch,
  Table,
  Text,
  TextInput,
  Title,
  Tooltip,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconAlertTriangle, IconFolderPlus, IconLock, IconPlus, IconTrash } from '@tabler/icons-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { useRegisterProject, useRootSurvey, useRootsSettings, useSaveRoots } from '../api/queries'
import { InboxTerminalCard } from '../runner/InboxTerminal'
import type { ProjectType, RootEntry, RootItem, RootSurvey, RootsSettings } from '../api/types'

const NAME_RE = /^[a-z0-9][a-z0-9-]{1,31}$/

/** The roots Archeion may read projects from: the workspace, plus ARCHEION_ROOTS (ADR 0008, 0010). */
function RootsCard({ data }: { data: RootsSettings }) {
  const save = useSaveRoots()
  const [name, setName] = useState('')
  const [folder, setFolder] = useState('')
  const current = data.roots.map((r) => ({ name: r.name, folder: r.folder }))
  const nameProblem =
    name && !NAME_RE.test(name)
      ? '2–32 characters: lowercase letters, digits and -'
      : name === 'workspace'
        ? "'workspace' is reserved for ARCHEION_WORKSPACE_ROOT"
        : current.some((r) => r.name === name)
          ? 'That name is taken'
        : null

  const submit = (roots: { name: string; folder: string }[], done: string, keepWorkspace = true) =>
    save.mutate({ roots, keepWorkspace }, {
      onSuccess: () => {
        notifications.show({ color: 'green', message: done })
        setName('')
        setFolder('')
      },
    })

  const remove = (root: RootEntry) => {
    if (
      root.projects.length > 0 &&
      !window.confirm(
        `${root.projects.length} registered project(s) use the root '${root.name}' (${root.projects.join(', ')}). ` +
          'They become unavailable until the root is added again. Remove it?',
      )
    )
      return
    if (root.name === 'workspace') submit(current, "Removed the root 'workspace'.", false)
    else
      submit(
        current.filter((r) => r.name !== root.name),
        `Removed the root '${root.name}'.`,
      )
  }
  const rows = [...(data.workspace ? [data.workspace] : []), ...data.roots]

  return (
    <Card withBorder>
      <Stack gap="sm">
        <div>
          <Title order={3}>Roots</Title>
          <Text size="sm" c="dimmed">
            Folders Archeion may read projects from. Granting a folder lets the viewer show the README, CLAUDE.md,
            changelog, roadmap and docs of the projects you register in it, and nothing else. Saved to{' '}
            <Code>ARCHEION_ROOTS</Code> in <Code>.env</Code> (the old file is kept as <Code>.env.bak</Code>), and applied
            at once.
          </Text>
        </div>
        {!data.editable && (
          <Alert color="gray" icon={<IconLock size={18} />} title="Read-only here">
            {data.locked_reason}
          </Alert>
        )}
        {data.errors.length > 0 && (
          <Alert color="orange" icon={<IconAlertTriangle size={18} />} title="Entries in .env that were refused">
            <List size="sm">
              {data.errors.map((e) => (
                <List.Item key={e}>{e}</List.Item>
              ))}
            </List>
            <Text size="sm" mt="xs">
              Saving here drops them. Fix them with configure.bat instead if you want to keep them.
            </Text>
          </Alert>
        )}
        {rows.length === 0 ? (
          <Alert color="blue" title="No roots yet">
            Archeion reads no projects until you grant it a folder. Add the folder that holds your projects below; you
            choose which of them to register afterwards.
          </Alert>
        ) : (
          <Table striped>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Name</Table.Th>
                <Table.Th>Folder</Table.Th>
                <Table.Th>Registered</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {rows.map((r) => (
                <Table.Tr key={r.name}>
                  <Table.Td>
                    <Code>{r.name}</Code>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm" style={{ wordBreak: 'break-all' }}>
                      {r.folder}
                    </Text>
                  </Table.Td>
                  <Table.Td>{r.projects.length}</Table.Td>
                  <Table.Td>
                    <Tooltip label={`Remove the root '${r.name}'`}>
                      <ActionIcon
                        variant="subtle"
                        color="red"
                        aria-label={`Remove the root ${r.name}`}
                        disabled={!data.editable || save.isPending}
                        onClick={() => remove(r)}
                      >
                        <IconTrash size={16} />
                      </ActionIcon>
                    </Tooltip>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
        {data.editable && (
          <form
            onSubmit={(e) => {
              e.preventDefault()
              if (!name || !folder.trim() || nameProblem) return
              submit([...current, { name, folder: folder.trim() }], `Added the root '${name}'.`)
            }}
          >
            <Group align="flex-start" gap="xs" wrap="wrap">
              <TextInput
                label="Name"
                placeholder="private"
                w={160}
                value={name}
                error={nameProblem}
                onChange={(e) => setName(e.currentTarget.value.trim().toLowerCase())}
              />
              <TextInput
                label="Folder"
                description="The folder that holds the projects, not a drive or your whole home folder"
                placeholder="Full path of the folder"
                style={{ flex: 1, minWidth: 240 }}
                value={folder}
                onChange={(e) => setFolder(e.currentTarget.value)}
              />
              <Button
                type="submit"
                mt={25}
                leftSection={<IconPlus size={16} />}
                loading={save.isPending}
                disabled={!name || !folder.trim() || !!nameProblem}
              >
                Add root
              </Button>
            </Group>
          </form>
        )}
        {save.isError && <Alert color="red">{save.error.message}</Alert>}
      </Stack>
    </Card>
  )
}

function RegisterRow({ item }: { item: RootItem }) {
  const register = useRegisterProject()
  const [open, setOpen] = useState(false)
  const [name, setName] = useState(item.name)
  const [type, setType] = useState<ProjectType>(item.detected_type)
  if (!open) {
    return (
      <Button size="xs" variant="light" leftSection={<IconFolderPlus size={14} />} onClick={() => setOpen(true)}>
        Register
      </Button>
    )
  }
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        if (!item.path) return
        register.mutate(
          // Only a choice that differs from detection goes on the page as `type:` (ADR 0016).
          { root: item.root, path: item.path, name, type: type === item.detected_type ? null : type },
          {
            onSuccess: (res) =>
              notifications.show({
                color: 'green',
                message: `Registered ${name}: fill in registry/${res.page} (group, kind, ports, depends_on).`,
              }),
          },
        )
      }}
    >
      <Stack gap={4}>
        <Group gap="xs" wrap="nowrap">
          <TextInput
            size="xs"
            aria-label="Project name"
            value={name}
            onChange={(e) => setName(e.currentTarget.value.trim().toLowerCase())}
            w={180}
          />
          <SegmentedControl
            size="xs"
            aria-label="Register as"
            value={type}
            onChange={(v) => setType(v as ProjectType)}
            data={[
              { value: 'project', label: 'Project' },
              // A module is part of a registered project.
              { value: 'module', label: 'Module', disabled: !item.parent },
            ]}
          />
          <Button size="xs" type="submit" loading={register.isPending} disabled={!name}>
            Create page
          </Button>
          <Button size="xs" variant="subtle" color="gray" onClick={() => setOpen(false)}>
            Cancel
          </Button>
        </Group>
        {register.isError && (
          <Text size="xs" c="red">
            {register.error.message}
          </Text>
        )}
      </Stack>
    </form>
  )
}

function SubProjectNote({ item }: { item: RootItem }) {
  if (item.registered) {
    return item.detected_type === 'module' ? (
      <Text size="xs" c="dimmed">
        module of {item.parent}
      </Text>
    ) : null
  }
  if (!item.parent_folder) return null
  return item.parent ? (
    <Text size="xs" c="dimmed">
      inside {item.parent}; looks like a {item.detected_type === 'module' ? 'module (no git repository of its own)' : 'project (its own git repository)'}
    </Text>
  ) : (
    <Text size="xs" c="dimmed">
      inside {item.parent_folder}, which isn't registered: register it first to link them
    </Text>
  )
}

function RootProjects({ root, onlyNew }: { root: RootSurvey; onlyNew: boolean }) {
  const items = onlyNew ? root.items.filter((i) => !i.registered) : root.items
  const waiting = root.items.filter((i) => !i.registered).length
  return (
    <Card withBorder>
      <Group justify="space-between" mb="xs" wrap="wrap">
        <Group gap="xs">
          <Title order={4}>{root.name}</Title>
          {!root.granted && <Badge color="orange">not granted on this machine</Badge>}
          {waiting > 0 && <Badge variant="light">{waiting} not registered</Badge>}
        </Group>
        {root.folder && (
          <Text size="xs" c="dimmed" style={{ wordBreak: 'break-all' }}>
            {root.folder}
          </Text>
        )}
      </Group>
      {!root.granted && (
        <Text size="sm" c="dimmed" mb="xs">
          Registry pages name this root, but it isn't in your roots, so their projects are unavailable. Add a root
          called <Code>{root.name}</Code> above to bring them back.
        </Text>
      )}
      {items.length === 0 ? (
        <Text size="sm" c="dimmed">
          {root.items.length === 0
            ? 'No projects found here: a project is a folder with a CLAUDE.md.'
            : 'Every project here is registered.'}
        </Text>
      ) : (
        <Table>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Folder</Table.Th>
              <Table.Th>In Archeion</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {items.map((i) => (
              <Table.Tr key={`${i.folder}:${i.name}`}>
                <Table.Td>
                  <Code>{i.folder}</Code>
                  <SubProjectNote item={i} />
                </Table.Td>
                <Table.Td>
                  {i.registered ? (
                    <Group gap="xs">
                      <Badge color="green" variant="light">
                        registered
                      </Badge>
                      <Anchor component={Link} to={`/projects/${i.registered}`} size="sm">
                        {i.registered}
                      </Anchor>
                    </Group>
                  ) : root.granted ? (
                    <RegisterRow item={i} />
                  ) : null}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Card>
  )
}

export function SettingsPage() {
  const roots = useRootsSettings()
  const survey = useRootSurvey()
  const [onlyNew, setOnlyNew] = useState(false)
  return (
    <Stack maw={1100}>
      <Title order={2}>Settings</Title>
      {roots.isPending && <Loader />}
      {roots.isError && <Alert color="red">{roots.error.message}</Alert>}
      {roots.data && <RootsCard data={roots.data} />}

      <Group justify="space-between" mt="md" wrap="wrap">
        <div>
          <Title order={3}>Projects in each root</Title>
          <Text size="sm" c="dimmed">
            Folders with a CLAUDE.md, and folders inside them with a manifest two levels down. Register each as a
            project (its own repository) or a module (part of a project). Registering creates a stub page in the private
            registry; it never changes the project.
          </Text>
        </div>
        <Switch label="Only unregistered" checked={onlyNew} onChange={(e) => setOnlyNew(e.currentTarget.checked)} />
      </Group>
      {survey.isPending && <Loader />}
      {survey.isError && <Alert color="red">{survey.error.message}</Alert>}
      {survey.data?.length === 0 && (
        <Text size="sm" c="dimmed">
          Nothing to show until you add a root.
        </Text>
      )}
      {survey.data?.map((r) => <RootProjects key={r.name} root={r} onlyNew={onlyNew} />)}

      <InboxTerminalCard />
    </Stack>
  )
}
