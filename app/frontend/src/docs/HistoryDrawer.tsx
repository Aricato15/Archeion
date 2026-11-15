import { Alert, Badge, Button, Drawer, Group, Loader, Modal, NavLink, ScrollArea, Stack, Text } from '@mantine/core'
import { IconEye } from '@tabler/icons-react'
import { useState } from 'react'
import { useDiff, useDocAt, useHistory } from '../api/queries'
import { formatDate } from '../lib/format'
import { DiffView } from './DiffView'
import { MarkdownView } from './MarkdownView'

export const WORKTREE = 'WORKTREE'

type Props = {
  path: string
  dirty: boolean
  opened: boolean
  onClose: () => void
  initialRev?: string | null
}

export function HistoryDrawer({ path, dirty, opened, onClose, initialRev }: Props) {
  const history = useHistory(path, opened)
  const [picked, setPicked] = useState<string | null>(null)
  const [viewRev, setViewRev] = useState<string | null>(null)
  const commits = history.data ?? []
  const rev = picked ?? initialRev ?? (dirty ? WORKTREE : (commits[0]?.rev ?? null))
  const diff = useDiff(path, opened ? rev : null)
  const at = useDocAt(path, viewRev)

  return (
    <>
      <Drawer opened={opened} onClose={onClose} position="right" size="80rem" title={`History of ${path}`}>
        <Group align="flex-start" wrap="nowrap" gap="md">
          <ScrollArea.Autosize mah="calc(100vh - 100px)" w={300} style={{ flexShrink: 0 }}>
            {dirty && (
              <NavLink
                active={rev === WORKTREE}
                onClick={() => setPicked(WORKTREE)}
                label={<Text fw={600}>Uncommitted changes</Text>}
                description="Working tree vs. last commit"
                rightSection={<Badge color="orange" size="xs">dirty</Badge>}
              />
            )}
            {history.isPending && <Loader size="sm" m="md" />}
            {!history.isPending && commits.length === 0 && (
              <Text c="dimmed" size="sm" p="sm">
                Not committed yet.
              </Text>
            )}
            {commits.map((c) => (
              <NavLink
                key={c.rev}
                active={rev === c.rev}
                onClick={() => setPicked(c.rev)}
                label={c.subject}
                description={`${c.short} · ${c.author_name} · ${formatDate(c.date)}`}
              />
            ))}
          </ScrollArea.Autosize>
          <Stack style={{ flex: 1, minWidth: 0 }} gap="sm">
            {rev && rev !== WORKTREE && (
              <Button
                variant="light"
                size="xs"
                w="fit-content"
                leftSection={<IconEye size={14} />}
                onClick={() => setViewRev(rev)}
              >
                View the doc as of this commit
              </Button>
            )}
            {diff.isPending && rev && <Loader size="sm" />}
            {diff.isError && <Alert color="red">{diff.error.message}</Alert>}
            {diff.data && <DiffView diff={diff.data.diff} />}
          </Stack>
        </Group>
      </Drawer>
      <Modal
        opened={viewRev !== null}
        onClose={() => setViewRev(null)}
        size="xl"
        title={`${path} at ${viewRev?.slice(0, 8) ?? ''}`}
      >
        {at.isPending && <Loader size="sm" />}
        {at.isError && <Alert color="red">{at.error.message}</Alert>}
        {at.data && <MarkdownView content={at.data.content} docPath={path} />}
      </Modal>
    </>
  )
}
