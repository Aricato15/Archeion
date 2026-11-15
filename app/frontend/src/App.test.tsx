import { MantineProvider } from '@mantine/core'
import { Notifications } from '@mantine/notifications'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { RouterProvider, createMemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { LoginPage } from './auth/LoginPage'
import { RequireAuth } from './auth/RequireAuth'
import { DocPage } from './docs/DocPage'
import { FeedbackPage } from './feedback/FeedbackPage'
import { ThreadPage } from './feedback/ThreadPage'
import { Shell } from './layout/Shell'
import { RoadmapPage } from './pages/RoadmapPage'

vi.mock('mermaid', () => ({
  default: { initialize: vi.fn(), parse: vi.fn(async () => true), render: vi.fn(async () => ({ svg: '<svg/>' })) },
}))

const item = {
  id: 7,
  kind: 'comment',
  doc_path: 'README.md',
  anchor: { heading: 'Docs', lines: [1, 1], quote: 'Docs' },
  body: 'Tighten the intro.',
  status: 'answered',
  reply: 'Done: tightened it.',
  parent_id: null,
  doc_rev: 'a'.repeat(40),
  created_at: '2026-11-15T03:00:00+00:00',
  updated_at: '2026-11-15T03:05:00+00:00',
  claimed_at: '2026-11-15T03:01:00+00:00',
  answered_at: '2026-11-15T03:05:00+00:00',
}

function mockApi(loggedIn: boolean) {
  const routes: Record<string, unknown> = {
    '/api/auth/session': loggedIn ? { expires_at: '2026-11-22T00:00:00+00:00' } : null,
    '/api/version': { version: '0.1.0' },
    '/api/docs/tree': {
      name: 'docs',
      path: '',
      type: 'dir',
      children: [
        { name: 'roadmap', path: 'roadmap', type: 'dir', children: [{ name: 'roadmap.md', path: 'roadmap/roadmap.md', type: 'file' }] },
        { name: 'README.md', path: 'README.md', type: 'file' },
      ],
    },
    '/api/docs/file': {
      path: 'README.md',
      content: '# Docs\n\nSee [roadmap](roadmap/roadmap.md).\n\n## One\n\n## Two\n\n```mermaid\nflowchart LR\n  A --> B\n```\n',
      sha: 'x',
      modified_at: '2026-11-15T03:00:00+00:00',
      dirty: true,
    },
    '/api/feedback/summary': { open: 1, in_progress: 0, answered: 1, resolved: 0 },
    '/api/feedback/7': { item, thread: [item] },
    '/api/feedback': [item],
    '/api/roadmap': {
      path: 'roadmap/roadmap.md',
      updated: '2026-11-15',
      now: [{ text: 'Build the viewer, see [plan](plan.md).', links: [] }],
      next: [],
      later: [],
      plans: [{ path: 'roadmap/plan.md', title: 'The plan', date: '2026-11-15' }],
    },
  }
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string) => {
      const path = input.split('?')[0]
      const body = routes[path]
      if (body === undefined) return new Response('{"detail":"not mocked"}', { status: 404 })
      if (body === null) return new Response('{"detail":"not logged in"}', { status: 401 })
      return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })
    }),
  )
}

class FakeEventSource {
  static CLOSED = 2
  readyState = 1
  onerror: (() => void) | null = null
  addEventListener() {}
  close() {}
}

function renderAt(url: string) {
  const router = createMemoryRouter(
    [
      { path: '/login', element: <LoginPage /> },
      {
        element: <RequireAuth />,
        children: [
          {
            element: <Shell />,
            children: [
              { path: 'docs/*', element: <DocPage /> },
              { path: 'roadmap', element: <RoadmapPage /> },
              { path: 'feedback', element: <FeedbackPage /> },
              { path: 'feedback/:id', element: <ThreadPage /> },
            ],
          },
        ],
      },
    ],
    { initialEntries: [url] },
  )
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <MantineProvider>
      <Notifications />
      <QueryClientProvider client={qc}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </MantineProvider>,
  )
}

describe('app', () => {
  beforeEach(() => vi.stubGlobal('EventSource', FakeEventSource))
  afterEach(() => vi.unstubAllGlobals())

  it('shows only the login page without a session', async () => {
    mockApi(false)
    renderAt('/docs/README.md')
    expect(await screen.findByLabelText('Admin password')).toBeTruthy()
    expect(screen.queryByText('Roadmap')).toBeNull()
  })

  it('renders a doc with the shell, tree, badges and diagram', async () => {
    mockApi(true)
    renderAt('/docs/README.md')
    expect(await screen.findByRole('heading', { name: 'Docs' })).toBeTruthy()
    expect(screen.getByText('Uncommitted changes')).toBeTruthy()
    expect(await screen.findByText('1 answered')).toBeTruthy()
    expect(screen.getByText('On this page')).toBeTruthy()
    expect(screen.getByText('roadmap', { selector: 'a' }).getAttribute('href')).toBe('/docs/roadmap/roadmap.md')
  })

  it('renders the roadmap, feedback list and a thread', async () => {
    mockApi(true)
    renderAt('/roadmap')
    expect(await screen.findByText('The plan')).toBeTruthy()
  })

  it('renders the feedback list', async () => {
    mockApi(true)
    renderAt('/feedback')
    expect(await screen.findByText('Tighten the intro.')).toBeTruthy()
  })

  it('renders a thread with Claude’s reply', async () => {
    mockApi(true)
    renderAt('/feedback/7')
    expect(await screen.findByText('Done: tightened it.')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Resolve' })).toBeTruthy()
  })
})
