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
import { IconExternalLink, IconHistory, IconMessage, IconMessagePlus } from '@tabler/icons-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router'
import { isNotFound } from '../api/client'
import { useDoc, useFeedbackList, useRegistry } from '../api/queries'
import { REGISTRY, SELF, isOwnSource, type Anchor as FeedbackAnchor } from '../api/types'
import { FeedbackForm, type FeedbackDraft } from '../feedback/FeedbackForm'
import { DocFeedbackPanel } from '../feedback/DocFeedbackPanel'
import { formatDate } from '../lib/format'
import { HistoryDrawer, WORKTREE } from './HistoryDrawer'
import { projectUrl } from './links'
import { MarkdownView, type Flash, type Heading } from './MarkdownView'

/** A doc from any source: /docs/* for archeion, /p/:source/* for a registered project. */
export function DocPage() {
  const params = useParams()
  const source = params.source ?? SELF
  const path = params['*'] ?? ''
  const [searchParams] = useSearchParams()
  const location = useLocation()
  const navigate = useNavigate()
  const doc = useDoc(source, path)
  const registry = useRegistry()
  const feedback = useFeedbackList({ source, doc_path: path }, path.endsWith('.md'))
  // A registry page in archeion links to the project page it describes, and the other way round.
  const describes = source === REGISTRY ? registry.data?.projects.find((p) => p.page === path) : undefined
  const project = !isOwnSource(source) ? registry.data?.projects.find((p) => p.id === source) : undefined
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

  const onComment = (anchor: FeedbackAnchor) => setDraft({ kind: 'comment', source, docPath: path, anchor })
  const onLocate = (anchor: FeedbackAnchor) => {
    panel.close()
    if (anchor.lines) setFlash({ line: anchor.lines[0], key: Date.now() })
    else if (anchor.heading) {
      const h = headings.find((x) => x.text === anchor.heading)
      if (h) document.getElementById(h.id)?.scrollIntoView({ behavior: 'smooth' })
    }
  }

  const crumbs = useMemo(() => path.split('/'), [path])
  const root = source === SELF ? 'docs' : source === REGISTRY ? 'registry' : (project?.title ?? source)

  if (!path.endsWith('.md')) {
    return <Text c="dimmed">Pick a doc from the sidebar.</Text>
  }
  if (doc.isPending) return <Loader />
  if (doc.isError) {
    return (
      <Alert color={isNotFound(doc.error) ? 'yellow' : 'red'} title={isNotFound(doc.error) ? 'Doc not found' : 'Error'}>
        {isNotFound(doc.error)
          ? `There's no ${source === SELF ? 'docs/' : `${source}: `}${path}, or it isn't served. It may have been moved or deleted.`
          : doc.error.message}
      </Alert>
    )
  }

  const data = doc.data
  return (
    <Group align="flex-start" wrap="nowrap" gap="xl">
      <Stack gap="xs" style={{ flex: 1, minWidth: 0, maxWidth: 960 }}>
        <Group justify="space-between" wrap="wrap" gap="xs">
          <Breadcrumbs separatorMargin={4}>
            {isOwnSource(source) ? (
              <Text size="sm" c="dimmed">
                {root}
              </Text>
            ) : (
              <Anchor component={Link} to={projectUrl(source)} size="sm">
                {root}
              </Anchor>
            )}
            {crumbs.map((c, i) => (
              <Text key={i} size="sm" c={i === crumbs.length - 1 ? undefined : 'dimmed'} fw={i === crumbs.length - 1 ? 600 : undefined}>
                {c}
              </Text>
            ))}
          </Breadcrumbs>
          <Group gap="xs">
            {describes && (
              <Button
                size="xs"
                variant="light"
                component={Link}
                to={projectUrl(describes.id)}
                leftSection={<IconExternalLink size={14} />}
              >
                Project page
              </Button>
            )}
            {!isOwnSource(source) && (
              <Tooltip label="This project's own file, shown read-only. Comments go to its inbox.">
                <Badge variant="outline">read-only</Badge>
              </Tooltip>
            )}
            {data.private && (
              <Tooltip label="Gitignored on purpose: it stays on this machine, so it has no git history.">
                <Badge variant="light" color="grape">
                  private
                </Badge>
              </Tooltip>
            )}
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
              onClick={() => setDraft({ kind: 'review', source, docPath: path })}
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
          source={source}
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
        key={`${source}:${path}:${historyRev ?? ''}`}
        source={source}
        path={path}
        dirty={data.dirty}
        opened={historyOpen}
        onClose={history.close}
        initialRev={historyRev}
      />
      <DocFeedbackPanel
        source={source}
        path={path}
        opened={panelOpen}
        onClose={panel.close}
        onLocate={onLocate}
        onNew={() => {
          panel.close()
          setDraft({ kind: 'review', source, docPath: path })
        }}
      />
      <FeedbackForm draft={draft} onClose={() => setDraft(null)} />
    </Group>
  )
}

