import { Alert, Anchor, Badge, Box, Group, Loader, NavLink, Stack, Text, Title } from '@mantine/core'
import { Link, useNavigate, useParams } from 'react-router'
import { useDoc, useTree, useVersion } from '../api/queries'
import { SELF } from '../api/types'
import { docUrl } from '../docs/links'
import { MarkdownView } from '../docs/MarkdownView'
import { flattenFiles } from '../lib/format'
import { compareVersions, updateNotes } from '../lib/updates'

/**
 * The update notes of docs/updates/: a list of the versions you can update to on one side,
 * the selected note on the other. The note is an ordinary doc, so it's also open in the doc viewer,
 * with its history and comments.
 */
export function UpdatesPage() {
  const params = useParams()
  const navigate = useNavigate()
  const tree = useTree(SELF)
  const installed = useVersion().data?.version
  const notes = updateNotes(tree.data ? flattenFiles(tree.data) : [])
  const current = notes.find((n) => n.version === params.version) ?? (params.version ? undefined : notes[0])
  const doc = useDoc(SELF, current?.path ?? '', Boolean(current))

  if (tree.isPending) return <Loader />
  if (tree.isError) return <Alert color="red">{tree.error.message}</Alert>
  if (notes.length === 0) return <Alert color="yellow">There are no update notes in docs/updates yet.</Alert>

  return (
    <Stack maw={1200}>
      <Title order={2}>Updates</Title>
      <Group align="flex-start" wrap="nowrap" gap="lg">
        <Stack gap={2} w={210} style={{ flexShrink: 0, position: 'sticky', top: 72 }} aria-label="Update notes">
          <Text size="xs" c="dimmed" mb={4}>
            Updating to
          </Text>
          {notes.map((n) => (
            <NavLink
              key={n.version}
              component={Link}
              to={`/updates/${n.version}`}
              active={n.version === current?.version}
              label={`v${n.version}`}
              rightSection={
                installed && n.version === installed ? (
                  <Badge size="xs" variant="light" color="green">
                    installed
                  </Badge>
                ) : installed && compareVersions(n.version, installed) > 0 ? (
                  <Badge size="xs" variant="light">
                    newer
                  </Badge>
                ) : null
              }
              style={{ borderRadius: 6 }}
            />
          ))}
        </Stack>
        <Box style={{ flex: 1, minWidth: 0 }}>
          {!current ? (
            <Alert color="yellow">
              There is no update note for v{params.version}.{' '}
              <Anchor component="button" type="button" onClick={() => navigate('/updates')}>
                Show the latest
              </Anchor>
            </Alert>
          ) : doc.isPending ? (
            <Loader />
          ) : doc.isError ? (
            <Alert color="red">{doc.error.message}</Alert>
          ) : (
            <Stack gap="xs">
              <Group justify="flex-end">
                <Anchor component={Link} to={docUrl(SELF, current.path)} size="sm">
                  Open as a doc
                </Anchor>
              </Group>
              <MarkdownView content={doc.data.content} docPath={current.path} source={SELF} />
            </Stack>
          )}
        </Box>
      </Group>
    </Stack>
  )
}
