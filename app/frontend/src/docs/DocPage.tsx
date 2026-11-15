import {
  Alert,
  Anchor,
  Badge,
  Box,
  Breadcrumbs,
  Button,
  Group,
  Indicator,
  Loader,
  NavLink,
  Stack,
  Text,
  Title,
  Tooltip,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { IconHistory, IconMessage, IconMessagePlus } from '@tabler/icons-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router'
import { isNotFound } from '../api/client'
import { useDoc, useFeedbackList } from '../api/queries'
import type { Anchor as FeedbackAnchor } from '../api/types'
import { FeedbackForm, type FeedbackDraft } from '../feedback/FeedbackForm'
import { DocFeedbackPanel } from '../feedback/DocFeedbackPanel'
import { formatDate } from '../lib/format'
import { HistoryDrawer, WORKTREE } from './HistoryDrawer'
import { docUrl } from './links'
import { MarkdownView, type Flash, type Heading } from './MarkdownView'

export function DocPage() {
  const path = useParams()['*'] ?? ''
  const [searchParams] = useSearchParams()
  const location = useLocation()
  const navigate = useNavigate()
  const doc = useDoc(path)
  const feedback = useFeedbackList({ doc_path: path }, path.endsWith('.md'))
  const [historyOpen, history] = useDisclosure(false)
  const [historyRev, setHistoryRev] = useState<string | null>(null)
  const [panelOpen, panel] = useDisclosure(false)
  const [draft, setDraft] = useState<FeedbackDraft | null>(null)
  const [headings, setHeadings] = useState<Heading[]>([])
  const [clickFlash, setFlash] = useState<Flash | null>(null)

  const activeFeedback = (feedback.data ?? []).filter((i) => i.status !== 'resolved').length

  // ?line=N (from search and feedback links) scrolls to and highlights that block.
  const lineParam = Number(searchParams.get('line')) || 0
  const lineFlash = useMemo<Flash | null>(() => (lineParam ? { line: lineParam, key: -lineParam } : null), [lineParam])
  const flash = clickFlash ?? lineFlash

  // #heading links: scroll once the content is there.
  useEffect(() => {
    if (!doc.data || !location.hash) return
    const id = decodeURIComponent(location.hash.slice(1))
    window.requestAnimationFrame(() => document.getElementById(id)?.scrollIntoView())
  }, [doc.data, location.hash])

  const onComment = useCallback(
    (anchor: FeedbackAnchor) => setDraft({ kind: 'comment', docPath: path, anchor }),
    [path],
  )
  const onLocate = (anchor: FeedbackAnchor) => {
    panel.close()
    if (anchor.lines) setFlash({ line: anchor.lines[0], key: Date.now() })
    else if (anchor.heading) {
      const h = headings.find((x) => x.text === anchor.heading)
      if (h) document.getElementById(h.id)?.scrollIntoView({ behavior: 'smooth' })
    }
  }

  const crumbs = useMemo(() => path.split('/'), [path])

  if (!path.endsWith('.md')) {
    return <Text c="dimmed">Pick a doc from the sidebar.</Text>
  }
  if (doc.isPending) return <Loader />
  if (doc.isError) {
    return (
      <Alert color={isNotFound(doc.error) ? 'yellow' : 'red'} title={isNotFound(doc.error) ? 'Doc not found' : 'Error'}>
        {isNotFound(doc.error) ? `There's no docs/${path}. It may have been moved or deleted.` : doc.error.message}
      </Alert>
    )
  }

  const data = doc.data
  return (
    <Group align="flex-start" wrap="nowrap" gap="xl">
      <Stack gap="xs" style={{ flex: 1, minWidth: 0, maxWidth: 960 }}>
        <Group justify="space-between" wrap="wrap" gap="xs">
          <Breadcrumbs separatorMargin={4}>
            <Text size="sm" c="dimmed">
              docs
            </Text>
            {crumbs.map((c, i) => (
              <Text key={i} size="sm" c={i === crumbs.length - 1 ? undefined : 'dimmed'} fw={i === crumbs.length - 1 ? 600 : undefined}>
                {c}
              </Text>
            ))}
          </Breadcrumbs>
          <Group gap="xs">
            {data.dirty && (
              <Tooltip label="This doc differs from the last commit. Click to see the diff.">
                <Badge
                  color="orange"
                  variant="light"
                  style={{ cursor: 'pointer' }}
                  onClick={() => {
                    setHistoryRev(WORKTREE)
                    history.open()
                  }}
                >
                  Uncommitted changes
                </Badge>
              </Tooltip>
            )}
            <Text size="xs" c="dimmed">
              Modified {formatDate(data.modified_at)}
            </Text>
            <Button
              size="xs"
              variant="default"
              leftSection={<IconMessagePlus size={14} />}
              onClick={() => setDraft({ kind: 'review', docPath: path })}
            >
              Review
            </Button>
            <Indicator label={activeFeedback} size={16} disabled={activeFeedback === 0}>
              <Button size="xs" variant="default" leftSection={<IconMessage size={14} />} onClick={panel.open}>
                Feedback
              </Button>
            </Indicator>
            <Button
              size="xs"
              variant="default"
              leftSection={<IconHistory size={14} />}
              onClick={() => {
                setHistoryRev(null)
                history.open()
              }}
            >
              History
            </Button>
          </Group>
        </Group>
        <MarkdownView
          content={data.content}
          docPath={path}
          onComment={onComment}
          onHeadings={setHeadings}
          flash={flash}
        />
      </Stack>

      {headings.length >= 3 && (
        <Box visibleFrom="lg" w={240} style={{ position: 'sticky', top: 80, flexShrink: 0 }}>
          <Title order={6} mb={4} c="dimmed">
            On this page
          </Title>
          <Stack gap={0} mah="calc(100vh - 120px)" style={{ overflowY: 'auto' }}>
            {headings.map((h) => (
              <NavLink
                key={h.id}
                label={h.text}
                pl={4 + (h.level - 1) * 12}
                py={2}
                onClick={() => {
                  navigate({ hash: h.id }, { replace: true })
                  document.getElementById(h.id)?.scrollIntoView({ behavior: 'smooth' })
                }}
              />
            ))}
          </Stack>
        </Box>
      )}

      <HistoryDrawer
        key={`${path}:${historyRev ?? ''}`}
        path={path}
        dirty={data.dirty}
        opened={historyOpen}
        onClose={history.close}
        initialRev={historyRev}
      />
      <DocFeedbackPanel
        path={path}
        opened={panelOpen}
        onClose={panel.close}
        onLocate={onLocate}
        onNew={() => {
          panel.close()
          setDraft({ kind: 'review', docPath: path })
        }}
      />
      <FeedbackForm draft={draft} onClose={() => setDraft(null)} />
    </Group>
  )
}

export function DocLink({ path, line, children }: { path: string; line?: number; children?: React.ReactNode }) {
  return (
    <Anchor component={Link} to={line ? `${docUrl(path)}?line=${line}` : docUrl(path)}>
      {children ?? path}
    </Anchor>
  )
}
