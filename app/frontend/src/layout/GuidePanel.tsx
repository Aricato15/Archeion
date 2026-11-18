import { ActionIcon, AppShell, Alert, Group, Loader, ScrollArea, Text, Tooltip } from '@mantine/core'
import { IconExternalLink, IconTerminal2, IconX } from '@tabler/icons-react'
import { Link } from 'react-router'
import { useDoc } from '../api/queries'
import { SELF } from '../api/types'
import { MarkdownView } from '../docs/MarkdownView'
import { docUrl } from '../docs/links'

/** The doc the panel shows. It's an ordinary doc, so it updates live and has a page of its own. */
export const GUIDE_PATH = 'guides/claude-cli.md'

/** Right-hand panel: how to work with Claude from the command line. */
export function GuidePanel({ opened, onClose }: { opened: boolean; onClose: () => void }) {
  const doc = useDoc(SELF, GUIDE_PATH, opened)
  return (
    <AppShell.Aside p="xs" aria-label="Claude CLI guide">
      <Group justify="space-between" wrap="nowrap" px="xs" pb="xs">
        <Group gap={6} wrap="nowrap">
          <IconTerminal2 size={18} />
          <Text fw={600} size="sm">
            Claude CLI
          </Text>
        </Group>
        <Group gap={4} wrap="nowrap">
          <Tooltip label="Open as a page">
            <ActionIcon component={Link} to={docUrl(SELF, GUIDE_PATH)} variant="subtle" aria-label="Open the guide as a page">
              <IconExternalLink size={16} />
            </ActionIcon>
          </Tooltip>
          <Tooltip label="Close">
            <ActionIcon variant="subtle" aria-label="Close the guide" onClick={onClose}>
              <IconX size={16} />
            </ActionIcon>
          </Tooltip>
        </Group>
      </Group>
      <AppShell.Section grow component={ScrollArea} px="xs" viewportProps={{ style: { overscrollBehavior: 'contain' } }}>
        {doc.isPending && opened && <Loader size="sm" m="sm" />}
        {doc.isError && (
          <Alert color="orange" title="Guide not found">
            <Text size="sm">
              The panel shows <code>docs/{GUIDE_PATH}</code>, which the backend couldn't load.
            </Text>
          </Alert>
        )}
        {doc.data && <MarkdownView content={doc.data.content} docPath={GUIDE_PATH} compact />}
      </AppShell.Section>
    </AppShell.Aside>
  )
}
