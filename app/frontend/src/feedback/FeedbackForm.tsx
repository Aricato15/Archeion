import { Blockquote, Button, Group, Modal, SegmentedControl, Select, Stack, Text, Textarea } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { useMemo, useState } from 'react'
import { useCreateFeedback, useTree } from '../api/queries'
import type { Anchor, FeedbackItem, FeedbackKind } from '../api/types'
import { describeAnchor } from '../docs/anchors'
import { flattenFiles } from '../lib/format'
import { KIND_HELP, KIND_LABEL } from './labels'

export type FeedbackDraft = {
  kind?: FeedbackKind
  docPath?: string | null
  anchor?: Anchor | null
  parentId?: number | null
  /** Let the user pick the doc (for a new prompt from the feedback page). */
  pickDoc?: boolean
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
      title={draft?.parentId ? `Follow up on #${draft.parentId}` : 'New feedback for Claude'}
    >
      {/* Mounted per draft, so every opening starts from a clean form. */}
      {draft && <FormBody draft={draft} onClose={onClose} onCreated={onCreated} />}
    </Modal>
  )
}

function FormBody({ draft, onClose, onCreated }: Props & { draft: FeedbackDraft }) {
  const create = useCreateFeedback()
  const tree = useTree()
  const [kind, setKind] = useState<FeedbackKind>(
    draft.kind ?? (draft.anchor ? 'comment' : draft.docPath ? 'review' : 'prompt'),
  )
  const [docPath, setDocPath] = useState<string | null>(draft.docPath ?? null)
  const [body, setBody] = useState('')

  const docs = useMemo(
    () => (tree.data ? flattenFiles(tree.data).filter((p) => p.endsWith('.md')) : []),
    [tree.data],
  )
  // The anchor only applies while the doc it came from is still selected.
  const anchor = docPath === (draft.docPath ?? null) ? (draft.anchor ?? null) : null

  const submit = () => {
    if (!body.trim()) return
    create.mutate(
      { kind, body: body.trim(), doc_path: docPath, anchor, parent_id: draft.parentId ?? null },
      {
        onSuccess: (item) => {
          notifications.show({
            color: 'green',
            title: 'Sent to Claude',
            message: `Feedback #${item.id} is in the inbox. Run /inbox in Claude Code to work on it.`,
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
        <Select
          label="Doc (optional)"
          placeholder="Not about a specific doc"
          data={docs}
          value={docPath}
          onChange={setDocPath}
          searchable
          clearable
        />
      ) : (
        docPath && (
          <Text size="sm">
            <b>{docPath}</b> · {describeAnchor(anchor)}
          </Text>
        )
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
