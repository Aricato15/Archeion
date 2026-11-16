import { Blockquote, Button, Group, Modal, SegmentedControl, Select, Stack, Text, Textarea } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { useMemo, useState } from 'react'
import { useCreateFeedback, useSources, useTree } from '../api/queries'
import { SELF, type Anchor, type FeedbackItem, type FeedbackKind, type SourceId } from '../api/types'
import { describeAnchor } from '../docs/anchors'
import { flattenFiles } from '../lib/format'
import { KIND_HELP, KIND_LABEL } from './labels'

export type FeedbackDraft = {
  kind?: FeedbackKind
  /** The project the item targets; archeion when unset. */
  source?: SourceId | null
  docPath?: string | null
  anchor?: Anchor | null
  /** Let the user pick the project and doc (for a new prompt from a list page). */
  pickDoc?: boolean
  /** Text to start from, which the user can edit (e.g. "Study <project>"). */
  body?: string
}

type Props = {
  draft: FeedbackDraft | null
  onClose: () => void
  onCreated?: (item: FeedbackItem) => void
}

export function FeedbackForm({ draft, onClose, onCreated }: Props) {
  return (
    <Modal
      opened={draft !== null}
      onClose={onClose}
      size="lg"
      title="New feedback for Claude"
    >
      {/* Mounted per draft, so every opening starts from a clean form. */}
      {draft && <FormBody draft={draft} onClose={onClose} onCreated={onCreated} />}
    </Modal>
  )
}

function FormBody({ draft, onClose, onCreated }: Props & { draft: FeedbackDraft }) {
  const create = useCreateFeedback()
  const sources = useSources()
  const [kind, setKind] = useState<FeedbackKind>(
    draft.kind ?? (draft.anchor ? 'comment' : draft.docPath ? 'review' : 'prompt'),
  )
  const [source, setSource] = useState<SourceId>(draft.source ?? SELF)
  const [docPath, setDocPath] = useState<string | null>(draft.docPath ?? null)
  const [body, setBody] = useState(draft.body ?? '')
  const tree = useTree(source, Boolean(draft.pickDoc))

  const docs = useMemo(
    () => (tree.data ? flattenFiles(tree.data).filter((p) => p.endsWith('.md')) : []),
    [tree.data],
  )
  // The anchor only applies while the doc it came from is still selected.
  const sameDoc = source === (draft.source ?? SELF) && docPath === (draft.docPath ?? null)
  const anchor = sameDoc ? (draft.anchor ?? null) : null

  const submit = () => {
    if (!body.trim()) return
    create.mutate(
      { kind, body: body.trim(), source, doc_path: docPath, anchor },
      {
        onSuccess: (item) => {
          const where = item.source === SELF ? 'Archeion' : item.source
          notifications.show({
            color: 'green',
            title: 'Sent to Claude',
            message: `Feedback #${item.id} is in ${where}'s inbox. Run /inbox in a Claude Code session there.`,
          })
          onCreated?.(item)
          onClose()
        },
      },
    )
  }

  return (
    <Stack gap="sm">
      <div>
        <SegmentedControl
          value={kind}
          onChange={(v) => setKind(v as FeedbackKind)}
          data={(['comment', 'review', 'prompt'] as const).map((k) => ({ value: k, label: KIND_LABEL[k] }))}
        />
        <Text size="xs" c="dimmed" mt={4}>
          {KIND_HELP[kind]}
        </Text>
      </div>
      {draft.pickDoc ? (
        <Group grow align="flex-start">
          <Select
            label="For"
            description="The project whose Claude session picks this up"
            data={(sources.data ?? [{ id: SELF, title: 'Archeion', kind: SELF }]).map((s) => ({
              value: s.id,
              label: s.id === SELF ? 'Archeion (cross-project)' : s.id === 'registry' ? 'Registry (private)' : s.title,
            }))}
            value={source}
            onChange={(v) => {
              setSource(v ?? SELF)
              setDocPath(null)
            }}
            allowDeselect={false}
            searchable
          />
          <Select
            label="Doc (optional)"
            description=" "
            placeholder="Not about a specific doc"
            data={docs}
            value={docPath}
            onChange={setDocPath}
            searchable
            clearable
          />
        </Group>
      ) : (
        (docPath || source !== SELF) && (
          <Text size="sm">
            {source !== SELF && <b>{source}: </b>}
            {docPath && <b>{docPath}</b>}
            {docPath && ` · ${describeAnchor(anchor)}`}
          </Text>
        )
      )}
      {anchor?.study && (
        <Text size="sm">
          About the {describeAnchor(anchor)} (snapshot {anchor.study.snapshot})
        </Text>
      )}
      {anchor?.quote && (
        <Blockquote p="xs" style={{ maxHeight: 140, overflow: 'auto', whiteSpace: 'pre-wrap' }}>
          <Text size="sm">{anchor.quote}</Text>
        </Blockquote>
      )}
      <Textarea
        label="What should Claude do or know?"
        placeholder="Markdown is fine."
        autosize
        minRows={4}
        maxRows={14}
        value={body}
        onChange={(e) => setBody(e.currentTarget.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) submit()
        }}
        data-autofocus
      />
      {create.isError && (
        <Text c="red" size="sm">
          {create.error.message}
        </Text>
      )}
      <Group justify="space-between">
        <Text size="xs" c="dimmed">
          Ctrl+Enter to send
        </Text>
        <Group gap="xs">
          <Button variant="default" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={submit} loading={create.isPending} disabled={!body.trim()}>
            Send
          </Button>
        </Group>
      </Group>
    </Stack>
  )
}
