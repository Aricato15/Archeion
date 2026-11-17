import { ActionIcon, Button, Card, Code, Group, Loader, Modal, Stack, Text, TextInput, Textarea, Title } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconPencil, IconPlus, IconSearch, IconTrash } from '@tabler/icons-react'
import { useMemo, useState } from 'react'
import { type GlossaryTerm, useDeleteTerm, useGlossary, useSaveTerm } from '../api/queries'
import { searchTerms } from './search'

function TermForm({ project, term, onClose }: { project: string; term: GlossaryTerm | null; onClose: () => void }) {
  const save = useSaveTerm(project)
  const [name, setName] = useState(term?.term ?? '')
  const [aliases, setAliases] = useState(term?.aliases.join(', ') ?? '')
  const [definition, setDefinition] = useState(term?.definition ?? '')
  const submit = () =>
    save.mutate(
      {
        replace: term?.id,
        term: name,
        definition,
        aliases: aliases
          .split(',')
          .map((a) => a.trim())
          .filter(Boolean),
      },
      {
        onSuccess: onClose,
        onError: (err) => notifications.show({ color: 'red', title: 'Not saved', message: err.message }),
      },
    )
  return (
    <Stack>
      <TextInput label="Term" value={name} onChange={(e) => setName(e.currentTarget.value)} data-autofocus required />
      <TextInput
        label="Also called"
        description="Other names for it, separated by commas."
        value={aliases}
        onChange={(e) => setAliases(e.currentTarget.value)}
      />
      <Textarea
        label="What it means"
        value={definition}
        onChange={(e) => setDefinition(e.currentTarget.value)}
        autosize
        minRows={3}
        required
      />
      <Group justify="flex-end">
        <Button variant="default" onClick={onClose}>
          Cancel
        </Button>
        <Button onClick={submit} loading={save.isPending} disabled={!name.trim() || !definition.trim()}>
          Save
        </Button>
      </Group>
    </Stack>
  )
}

/** A project's terms and jargon, with a case-insensitive search. Kept in the private registry (ADR 0023). */
export function GlossaryTab({ project }: { project: string }) {
  const glossary = useGlossary(project)
  const remove = useDeleteTerm(project)
  const [q, setQ] = useState('')
  const [editing, setEditing] = useState<GlossaryTerm | 'new' | null>(null)
  const shown = useMemo(() => searchTerms(glossary.data ?? [], q), [glossary.data, q])

  if (glossary.isPending) return <Loader size="sm" />
  if (glossary.isError) return <Text c="red">{glossary.error.message}</Text>
  const total = glossary.data.length

  return (
    <Stack gap="sm">
      <Group justify="space-between" wrap="nowrap">
        <TextInput
          aria-label="Search the glossary"
          placeholder="Search terms and meanings"
          leftSection={<IconSearch size={14} />}
          value={q}
          onChange={(e) => setQ(e.currentTarget.value)}
          style={{ flex: 1 }}
        />
        <Button leftSection={<IconPlus size={14} />} onClick={() => setEditing('new')}>
          Add term
        </Button>
      </Group>
      <Text size="xs" c="dimmed">
        {q.trim() ? `${shown.length} of ${total} terms` : `${total} term${total === 1 ? '' : 's'}`}. Kept in the
        private registry. Claude can add to it with <Code>glossary set {project} &lt;term&gt; &lt;meaning&gt;</Code>.
      </Text>
      {total === 0 && (
        <Text c="dimmed">No terms yet. Add the first one, or ask Claude to collect this project's jargon.</Text>
      )}
      {total > 0 && shown.length === 0 && <Text c="dimmed">Nothing matches “{q}”.</Text>}
      {shown.map((t) => (
        <Card key={t.id} withBorder radius="md" padding="sm">
          <Group justify="space-between" align="flex-start" wrap="nowrap">
            <Stack gap={2}>
              <Title order={5}>{t.term}</Title>
              {t.aliases.length > 0 && (
                <Text size="xs" c="dimmed">
                  also: {t.aliases.join(', ')}
                </Text>
              )}
              <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
                {t.definition}
              </Text>
            </Stack>
            <Group gap={2} wrap="nowrap">
              <ActionIcon variant="subtle" aria-label={`Edit ${t.term}`} onClick={() => setEditing(t)}>
                <IconPencil size={16} />
              </ActionIcon>
              <ActionIcon
                variant="subtle"
                color="red"
                aria-label={`Delete ${t.term}`}
                loading={remove.isPending && remove.variables === t.id}
                onClick={() => {
                  if (window.confirm(`Delete “${t.term}”?`))
                    remove.mutate(t.id, {
                      onError: (err) =>
                        notifications.show({ color: 'red', title: 'Not deleted', message: err.message }),
                    })
                }}
              >
                <IconTrash size={16} />
              </ActionIcon>
            </Group>
          </Group>
        </Card>
      ))}
      <Modal
        opened={editing !== null}
        onClose={() => setEditing(null)}
        title={editing === 'new' ? 'Add a term' : 'Edit term'}
      >
        {editing && (
          <TermForm
            key={editing === 'new' ? 'new' : editing.id}
            project={project}
            term={editing === 'new' ? null : editing}
            onClose={() => setEditing(null)}
          />
        )}
      </Modal>
    </Stack>
  )
}
