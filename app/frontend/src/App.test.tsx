import { MantineProvider } from '@mantine/core'
import { Notifications } from '@mantine/notifications'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { RouterProvider, createMemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { LoginPage } from './auth/LoginPage'
import { RequireAuth } from './auth/RequireAuth'
import { DocPage } from './docs/DocPage'
import { FeedbackPage } from './feedback/FeedbackPage'
import { ThreadPage } from './feedback/ThreadPage'
import { Shell } from './layout/Shell'
import { RoadmapPage } from './pages/RoadmapPage'
import { SettingsPage } from './pages/SettingsPage'
import { GroupPage } from './projects/GroupPage'
import { ProjectPage } from './projects/ProjectPage'
import { ProjectsPage } from './projects/ProjectsPage'

vi.mock('mermaid', () => ({
  default: { initialize: vi.fn(), parse: vi.fn(async () => true), render: vi.fn(async () => ({ svg: '<svg/>' })) },
}))

const item = {
  id: 7,
  kind: 'comment',
  source: 'archeion',
  origin: null,
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
const projectItem = { ...item, id: 8, source: 'gateway', doc_path: 'docs/api.md', body: 'Document the routes.' }
const reportItem = { ...item, id: 9, origin: 'gateway', doc_path: null, anchor: null, status: 'open', body: 'Gateway moved to port 20061.' }

const project = (id: string, extra: Record<string, unknown> = {}) => ({
  id,
  title: id,
  page: `projects/${id}.md`,
  path: `../${id}`,
  root: null,
  parent: null,
  group: null,
  status: 'active',
  kind: null,
  ports: [],
  depends_on: [],
  docs_dir: 'docs',
  verified: '2026-11-15',
  summary: `About ${id}.`,
  available: true,
  children: [],
  used_by: [],
  ...extra,
})

const registry = {
  projects: [
    project('gateway', { group: 'shop', ports: [20060], depends_on: ['datasvc'], kind: 'service' }),
    project('datasvc', { children: ['collector-a'], used_by: ['gateway'] }),
    project('collector-a', { parent: 'datasvc', path: '../datasvc/collectors/collector-a' }),
    project('vault', { root: 'lab', path: 'vault', available: false }),
  ],
  groups: [{ id: 'shop', title: 'Shop', page: 'groups/shop.md', summary: 'The shop apps.', projects: ['gateway'] }],
  warnings: [
    { page: 'projects/collector-a.md', message: "depends_on 'ghost' isn't a registered project" },
    { page: '', message: ".env: root name 'Bad' must be 2-32 characters" },
  ],
  unregistered: [
    { name: 'newproj', path: '../newproj', root: null, parent: null },
    { name: 'other', path: 'other', root: 'lab', parent: null },
  ],
}

const files: Record<string, unknown> = {
  'archeion:README.md': {
    content: '# Docs\n\nSee [roadmap](roadmap/roadmap.md) and [gateway](../../gateway/docs/api.md).\n\n## One\n\n## Two\n\n```mermaid\nflowchart LR\n  A --> B\n```\n',
    dirty: true,
  },
  'registry:projects/gateway.md': { content: '---\nname: gateway\n---\n# Gateway\n\nThe gateway notes.\n', dirty: false },
  'registry:groups/shop.md': { content: '# Shop\n\nThe shop apps.\n', dirty: false },
  'gateway:README.md': { content: '# Gateway readme\n\nSee [api](docs/api.md).\n', dirty: false },
  'gateway:docs/api.md': { content: '# Gateway API\n\nRoutes.\n', dirty: false },
}

function mockApi(loggedIn: boolean, firstRun = false) {
  const routes: Record<string, unknown> = {
    '/api/auth/session': loggedIn ? { expires_at: '2026-11-22T00:00:00+00:00' } : null,
    '/api/version': { version: '0.2.0' },
    '/api/auth/setup': { needed: firstRun, allowed: true, min_length: 12 },
    '/api/registry': registry,
    '/api/sources': [
      { id: 'archeion', title: 'Archeion', kind: 'archeion' },
      { id: 'registry', title: 'Registry (private)', kind: 'registry' },
      { id: 'gateway', title: 'gateway', kind: 'project' },
    ],
    '/api/docs/tree': {
      name: 'docs',
      path: '',
      type: 'dir',
      children: [
        { name: 'roadmap', path: 'roadmap', type: 'dir', children: [{ name: 'roadmap.md', path: 'roadmap/roadmap.md', type: 'file' }] },
        { name: 'README.md', path: 'README.md', type: 'file' },
      ],
    },
    '/api/settings/roots': {
      workspace: { name: 'workspace', folder: '/work', projects: ['gateway', 'datasvc', 'collector-a'] },
      roots: [{ name: 'lab', folder: '/lab', projects: ['vault'] }],
      errors: ["root name 'Bad' must be 2-32 characters"],
      editable: true,
      locked_reason: null,
    },
    '/api/registry/roots': [
      {
        name: 'workspace',
        folder: '/work',
        granted: true,
        items: [
          { name: 'gateway', path: '../gateway', root: null, folder: 'gateway', parent_folder: null, parent: null, registered: 'gateway' },
          { name: 'newproj', path: '../newproj', root: null, folder: 'newproj', parent_folder: null, parent: null, registered: null },
          { name: 'coll-b', path: '../datasvc/collectors/coll-b', root: null, folder: 'datasvc/collectors/coll-b', parent_folder: 'datasvc', parent: 'datasvc', registered: null },
        ],
      },
      { name: 'gone', folder: null, granted: false, items: [{ name: 'far', path: 'far', root: 'gone', folder: 'far', parent_folder: null, parent: null, registered: 'far' }] },
    ],
    '/api/registry/projects': { page: 'projects/newproj.md', project: null },
    '/api/feedback/summary': { open: 1, in_progress: 0, answered: 1, resolved: 0, waiting_by_source: { gateway: 1 } },
    '/api/feedback/7': { item, thread: [item] },
    '/api/roadmap': {
      cross: {
        path: 'roadmap/roadmap.md',
        updated: '2026-11-15',
        now: [{ text: 'Build the viewer, see [plan](plan.md).', links: [] }],
        next: [],
        later: [],
        structured: true,
        plans: [{ path: 'roadmap/plan.md', title: 'The plan', date: '2026-11-15' }],
      },
      projects: [
        { project: 'gateway', title: 'gateway', roadmap: { path: 'docs/roadmap.md', updated: null, now: [{ text: 'Ship routes', links: [] }], next: [], later: [], structured: true, plans: [] } },
        { project: 'datasvc', title: 'datasvc', roadmap: null },
      ],
    },
  }
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string) => {
      const url = new URL(input, 'http://test')
      let body: unknown = routes[url.pathname]
      if (url.pathname === '/api/docs/file') {
        const key = `${url.searchParams.get('source') ?? 'archeion'}:${url.searchParams.get('path')}`
        const f = files[key] as { content: string; dirty: boolean } | undefined
        body = f && { source: key.split(':')[0], path: url.searchParams.get('path'), sha: 'x', modified_at: '2026-11-15T03:00:00+00:00', frontmatter: null, ...f }
      }
      if (url.pathname === '/api/feedback') {
        const source = url.searchParams.get('source')
        body = [item, projectItem, reportItem].filter((i) => !source || i.source === source)
      }
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
              { path: 'p/:source/*', element: <DocPage /> },
              { path: 'projects', element: <ProjectsPage /> },
              { path: 'projects/:id', element: <ProjectPage /> },
              { path: 'groups/:id', element: <GroupPage /> },
              { path: 'roadmap', element: <RoadmapPage /> },
              { path: 'feedback', element: <FeedbackPage /> },
              { path: 'feedback/:id', element: <ThreadPage /> },
              { path: 'settings', element: <SettingsPage /> },
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

  it('asks for a new admin password on a fresh start', async () => {
    mockApi(false, true)
    renderAt('/docs/README.md')
    expect(await screen.findByText("You're new here!")).toBeTruthy()
    const first = screen.getByLabelText('New admin password')
    expect(screen.queryByLabelText('Admin password')).toBeNull()
    fireEvent.change(first, { target: { value: 'short' } })
    expect(screen.getByText('Use at least 12 characters')).toBeTruthy()
    fireEvent.change(first, { target: { value: 'long-enough-secret' } })
    fireEvent.change(screen.getByLabelText('Repeat it'), { target: { value: 'long-enough-secret!' } })
    expect(screen.getByText("The two entries don't match")).toBeTruthy()
    expect((screen.getByRole('button', { name: 'Save password and log in' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('says so when the backend is down, instead of showing a login form', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('', { status: 502 })))
    renderAt('/login')
    expect(await screen.findByText("Can't reach the backend")).toBeTruthy()
    expect(screen.queryByLabelText('Admin password')).toBeNull()
  })

  it('renders a doc with the shell, project tree, badges and cross-project links', async () => {
    mockApi(true)
    renderAt('/docs/README.md')
    expect(await screen.findByRole('heading', { name: 'Docs' })).toBeTruthy()
    expect(screen.getByText('Uncommitted changes')).toBeTruthy()
    expect(await screen.findByText('1 answered')).toBeTruthy()
    expect(screen.getByText('On this page')).toBeTruthy()
    expect(screen.getByText('roadmap', { selector: 'a' }).getAttribute('href')).toBe('/docs/roadmap/roadmap.md')
    // once the registry is in, a link from archeion into a project's docs opens it in the viewer
    expect((await screen.findByText('gateway', { selector: 'a' })).getAttribute('href')).toBe('/p/gateway/docs/api.md')
    expect(screen.getByText('Shop')).toBeTruthy() // group in the sidebar
  })

  it('renders a project doc read-only, with links resolved inside the project', async () => {
    mockApi(true)
    renderAt('/p/gateway/README.md')
    expect(await screen.findByRole('heading', { name: 'Gateway readme' })).toBeTruthy()
    expect(screen.getByText('read-only')).toBeTruthy()
    expect((await screen.findByText('api', { selector: 'a' })).getAttribute('href')).toBe('/p/gateway/docs/api.md')
  })

  it('renders the projects overview with warnings, unregistered folders and groups', async () => {
    mockApi(true)
    renderAt('/projects')
    expect(await screen.findByText('Registry problems')).toBeTruthy()
    expect(screen.getByText('2 unregistered folder(s)')).toBeTruthy()
    expect(screen.getByText(/\.\.\/newproj, lab:other/)).toBeTruthy()
    expect(screen.getByText(/root name 'Bad' must be/)).toBeTruthy() // the .env warning, shown as Settings
    expect(screen.getAllByRole('link', { name: 'Settings' }).length).toBe(2) // the nav and the hint
    expect(screen.getByText('Standalone')).toBeTruthy()
    expect(screen.getAllByText('About gateway.').length).toBeGreaterThan(0)
  })

  it('renders a project page with facts, notes and sub-projects', async () => {
    mockApi(true)
    renderAt('/projects/datasvc')
    expect(await screen.findByText('Sub-projects')).toBeTruthy()
    expect(screen.getByText('Used by')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Prompt for datasvc' })).toBeTruthy()
  })

  it('shows the root of a project in a granted folder, and why it is unavailable', async () => {
    mockApi(true)
    renderAt('/projects/vault')
    expect(await screen.findByText('Root')).toBeTruthy()
    expect(screen.getByText('lab:vault')).toBeTruthy()
    expect(screen.getByText(/the root 'lab' may not be granted on this machine/)).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Prompt for vault' })).toBeNull()
  })

  it('renders a group page', async () => {
    mockApi(true)
    renderAt('/groups/shop')
    expect(await screen.findByRole('heading', { name: 'Shop', level: 2 })).toBeTruthy()
  })

  it('renders the cross-project and per-project roadmaps', async () => {
    mockApi(true)
    renderAt('/roadmap')
    expect(await screen.findByText('The plan')).toBeTruthy()
    expect(screen.getByText('Ship routes')).toBeTruthy()
    expect(screen.getByText(/No roadmap of their own/)).toBeTruthy()
  })

  it('renders the feedback list with project badges', async () => {
    mockApi(true)
    renderAt('/feedback')
    expect(await screen.findByText('Tighten the intro.')).toBeTruthy()
    expect(screen.getByText('Document the routes.')).toBeTruthy()
    expect(screen.getByText('from gateway')).toBeTruthy()
  })

  it('lists roots and their projects, and registers a folder', async () => {
    mockApi(true)
    renderAt('/settings')
    expect(await screen.findByText('/lab')).toBeTruthy()
    expect(screen.getByText('Entries in .env that were refused')).toBeTruthy()
    expect(await screen.findByText('sub-project of datasvc')).toBeTruthy()
    expect(screen.getByText('not granted on this machine')).toBeTruthy()
    expect(screen.getByText('2 not registered')).toBeTruthy()
    expect(screen.getAllByText('registered').length).toBe(2)

    fireEvent.click(screen.getAllByRole('button', { name: 'Register' })[0])
    fireEvent.click(screen.getByRole('button', { name: 'Create page' }))
    expect(await screen.findByText(/Registered newproj/)).toBeTruthy()
    const calls = (fetch as unknown as { mock: { calls: [string, RequestInit?][] } }).mock.calls
    const post = calls.find(([url, init]) => url === '/api/registry/projects' && init?.method === 'POST')
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({ root: null, path: '../newproj', name: 'newproj' })
  })

  it('renders a thread with Claude’s reply', async () => {
    mockApi(true)
    renderAt('/feedback/7')
    expect(await screen.findByText('Done: tightened it.')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Resolve' })).toBeTruthy()
  })
})
