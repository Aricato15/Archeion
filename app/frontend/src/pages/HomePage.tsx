import { Anchor, Badge, Card, Group, Loader, SegmentedControl, Select, Stack, Text, Title } from '@mantine/core'
import { useQueries } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { Link } from 'react-router'
import { api, isNotFound, qs } from '../api/client'
import { useChangelog, useSources, useVersion } from '../api/queries'
import type { DocFile, SourceId } from '../api/types'
import { projectUrl, docUrl } from '../docs/links'
import { MarkdownView } from '../docs/MarkdownView'
import { byNewest, parseChangelog, type Release } from '../lib/changelog'

type Entry = Release & { source: SourceId; title: string; key: string }
type Mode = 'archeion' | 'projects'

const SHOWN = 8

/**
 * Where you start: what changed in Archeion, newest first. A switch shows the registered projects'
 * changelogs instead, all together or one at a time.
 */
export function HomePage() {
  const sources = useSources()
  const version = useVersion()
  const [mode, setMode] = useState<Mode>('archeion')
  const [only, setOnly] = useState<string | null>(null)
  const [count, setCount] = useState(SHOWN)

  const own = useChangelog()
  const wanted = useMemo(
    () => (mode === 'projects' ? (sources.data ?? []).filter((s) => s.kind === 'project') : []),
    [sources.data, mode],
  )
  const logs = useQueries({
    queries: wanted.map((s) => ({
      queryKey: ['doc', s.id, 'CHANGELOG.md'],
      queryFn: () => api<DocFile>(`/docs/file${qs({ source: s.id, path: 'CHANGELOG.md' })}`),
      retry: false,
    })),
  })

  const entries = useMemo(() => {
    const out: Entry[] = []
    wanted.forEach((s, i) => {
      const doc = logs[i]?.data
      if (!doc) return
      for (const r of parseChangelog(doc.content)) out.push({ ...r, source: s.id, title: s.title, key: `${s.id}@${r.version}` })
    })
    return out.sort(byNewest)
  }, [wanted, logs])

  const loading = mode === 'archeion' ? own.isPending : sources.isPending || logs.some((l) => l.isPending)
  // A project without a changelog is normal (a 404); anything else is worth saying.
  const failed = logs.filter((l) => l.isError && !isNotFound(l.error)).length
  const have = new Set(entries.map((e) => e.source))
  const shown = entries.filter((e) => !only || e.source === only)
  const limit = count

  return (
    <Stack gap="md">
      <Group justify="space-between" align="flex-end">
        <Stack gap={2}>
          <Title order={2}>{mode === 'archeion' ? "What's changed in Archeion" : "What's changed in your projects"}</Title>
          <Text c="dimmed" size="sm">
            {mode === 'archeion'
              ? `Every release, newest first${version.data?.version ? ` (you're on ${version.data.version})` : ''}. This is the changelog of the commit that's checked out.`
              : 'The latest releases from each registered project that keeps a CHANGELOG.md.'}
          </Text>
        </Stack>
        <Group gap="xs">
          {mode === 'projects' && (
            <Select
              size="xs"
              w={200}
              aria-label="Show one project"
              placeholder="All projects"
              clearable
              data={wanted.filter((s) => have.has(s.id)).map((s) => ({ value: s.id, label: s.title }))}
              value={only}
              onChange={(v) => {
                setOnly(v)
                setCount(SHOWN)
              }}
            />
          )}
          <SegmentedControl
            size="xs"
            aria-label="Whose changes"
            value={mode}
            onChange={(v) => {
              setMode(v as Mode)
              setOnly(null)
              setCount(SHOWN)
            }}
            data={[
              { value: 'archeion', label: 'Archeion' },
              { value: 'projects', label: 'Projects' },
            ]}
          />
        </Group>
      </Group>
      {loading && <Loader size="sm" />}
      {mode === 'archeion' && own.isError && (
        <Text c="orange">The changelog couldn't be read: {own.error.message}</Text>
      )}
      {mode === 'archeion' && own.data && (
        // The whole file, as written. It's the one of the commit that's checked out.
        <Card withBorder radius="md" padding="md">
          {/* The docs source is docs/, and the changelog links to docs/... from the repo root, so drop that prefix. */}
          <MarkdownView content={own.data.content.replace(/\]\(docs\//g, '](')} docPath="CHANGELOG.md" source="archeion" />
        </Card>
      )}
      {mode === 'projects' && failed > 0 && (
        <Text size="sm" c="orange">
          {failed} changelog{failed === 1 ? '' : 's'} couldn't be read.
        </Text>
      )}
      {mode === 'projects' && !loading && shown.length === 0 && (
        <Text c="dimmed">
          None of the registered projects has a changelog with releases.
        </Text>
      )}
      {mode === 'projects' && shown.slice(0, limit).map((e) => (
        <Card key={e.key} withBorder radius="md" padding="md" data-release={e.key}>
          <Group gap="xs" mb="xs">
            <Anchor component={Link} to={projectUrl(e.source)} fw={600}>
              {e.title}
            </Anchor>
            <Badge size="md" variant={e.version === 'Unreleased' ? 'outline' : 'light'}>
              {e.version}
            </Badge>
            {e.date && (
              <Text size="sm" c="dimmed">
                {e.date}
              </Text>
            )}
            <Anchor component={Link} to={docUrl(e.source, 'CHANGELOG.md')} size="xs" ml="auto">
              Full changelog
            </Anchor>
          </Group>
          <MarkdownView content={e.body} docPath="CHANGELOG.md" source={e.source} compact />
        </Card>
      ))}
      {mode === 'projects' && shown.length > limit && (
        <Anchor component="button" type="button" size="sm" onClick={() => setCount((n) => n + SHOWN)}>
          Show older releases ({shown.length - count} more)
        </Anchor>
      )}
    </Stack>
  )
}
