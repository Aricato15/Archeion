import { MantineProvider } from '@mantine/core'
import { Notifications } from '@mantine/notifications'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ReportDialog } from './ReportDialog'
import { ReportTab } from './ReportTab'

const entry = (id: string, title: string, extra: Record<string, unknown> = {}) => ({
  id,
  group: 'overview',
  title,
  kind: 'text',
  available: true,
  reason: null,
  parent: null,
  ...extra,
})

const catalog = [
  entry('overview.facts', 'Summary and facts'),
  entry('study.map', 'Component map (top level)', { group: 'study', kind: 'diagram' }),
  entry('study.findings', 'Findings', { group: 'study' }),
]

const plan = {
  plan: {
    name: 'exec',
    mode: 'guided',
    title: 'Executive review',
    prompt: 'For the executive team',
    outline: '1. Overview',
    options: { page_size: 'A4', orientation: 'portrait', cover: true, toc: true },
    sections: [
      {
        id: 'authored:summary',
        title: 'Executive summary',
        body: 'Alpha owns **items**.',
        cites: ['overview.facts', 'study.findings'],
      },
      { id: 'study.map' },
      { id: 'study.findings' },
    ],
  },
  thread: 12,
  updated: '2026-11-18T10:00:00Z',
}

type Call = { method: string; url: string; body: unknown }

function stubApi(overrides: Record<string, unknown> = {}) {
  const calls: Call[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      calls.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : undefined })
      const key = `${method} ${url.split('?')[0]}`
      const table: Record<string, unknown> = {
        'GET /api/reports/alpha/catalog': catalog,
        'GET /api/reports/alpha/presets': [],
        'GET /api/reports/alpha/preflight': { ok: true, problems: [] },
        'GET /api/reports/alpha/plan': null,
        'GET /api/responder': { enabled: true },
        'POST /api/feedback': { id: 41, status: 'open' },
        'POST /api/reports/alpha/plan/approve': { id: 'abc123abc123', status: 'running' },
        'GET /api/reports/alpha/builds/abc123abc123': {
          id: 'abc123abc123',
          status: 'done',
          result: { file: '2026-11-18-exec.pdf', pages: 6, sections: 3, failed: 0 },
        },
        ...overrides,
      }
      if (!(key in table)) return new Response('{"detail":"unexpected"}', { status: 404 })
      return new Response(JSON.stringify(table[key]), { status: 200, headers: { 'Content-Type': 'application/json' } })
    }),
  )
  return calls
}

function open() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const onClose = vi.fn()
  render(
    <MantineProvider>
      <Notifications />
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <ReportDialog project="alpha" opened onClose={onClose} />
        </MemoryRouter>
      </QueryClientProvider>
    </MantineProvider>,
  )
  fireEvent.click(screen.getByText('Guided: describe what you need'))
  return { onClose }
}

afterEach(() => vi.unstubAllGlobals())

describe('Guided report, before there is a plan', () => {
  it('asks what is needed, and will not start without a prompt', async () => {
    stubApi()
    open()
    const button = (await screen.findByRole('button', { name: /Ask Claude to plan the report/ })) as HTMLButtonElement
    expect(button.disabled).toBe(true)
    fireEvent.change(screen.getByLabelText(/What do you need/), { target: { value: 'For executives' } })
    expect(button.disabled).toBe(false)
  })

  it('starts a report thread for Archeion with the prompt and the outline', async () => {
    const calls = stubApi()
    const { onClose } = open()
    await screen.findByRole('button', { name: /Ask Claude to plan the report/ })
    fireEvent.change(screen.getByLabelText(/What do you need/), { target: { value: 'For executives' } })
    fireEvent.change(screen.getByLabelText(/The structure you'd like/), { target: { value: '1. Overview\n2. Risks' } })
    fireEvent.click(screen.getByRole('button', { name: /Ask Claude to plan the report/ }))
    await waitFor(() => expect(onClose).toHaveBeenCalled())
    const sent = calls.find((c) => c.method === 'POST' && c.url === '/api/feedback')!
    expect(sent.body).toMatchObject({
      kind: 'prompt',
      source: 'archeion',
      anchor: { task: { type: 'report', project: 'alpha' } },
    })
    const body = (sent.body as { body: string }).body
    expect(body).toContain('For executives')
    expect(body).toContain('1. Overview\n2. Risks')
  })
})

describe('Guided report, with a plan', () => {
  it("shows Claude's plan in order, marks what Claude wrote, and links the thread", async () => {
    stubApi({ 'GET /api/reports/alpha/plan': plan })
    open()
    expect(await screen.findByText('3 sections')).toBeTruthy()
    const dialog = screen.getByRole('dialog')
    const order = within(dialog).getAllByLabelText(/^Drag /).map((b) => b.getAttribute('aria-label'))
    expect(order).toEqual([
      'Drag Executive summary to move it',
      'Drag Component map (top level) to move it',
      'Drag Findings to move it',
    ])
    expect(within(dialog).getAllByText('Claude')).toHaveLength(1) // only the summary is Claude's
    expect(within(dialog).getByRole('link', { name: /Open the thread/ }).getAttribute('href')).toBe('/feedback/12')
    expect(within(dialog).getByText('Written by Claude')).toBeTruthy()
    fireEvent.click(within(dialog).getByText('Executive summary', { selector: '.mantine-Accordion-label' }))
    expect(await within(dialog).findByText(/Sources: Summary and facts; Findings/)).toBeTruthy()
  })

  it('saves the plan when a section is dropped, keeping everything else', async () => {
    const calls = stubApi({ 'GET /api/reports/alpha/plan': plan, 'PUT /api/reports/alpha/plan': plan })
    open()
    await screen.findByText('3 sections')
    fireEvent.click(screen.getByLabelText('Remove Findings'))
    await waitFor(() => expect(calls.some((c) => c.method === 'PUT')).toBe(true))
    const saved = calls.find((c) => c.method === 'PUT')!.body as typeof plan.plan
    expect(saved.sections.map((s) => s.id)).toEqual(['authored:summary', 'study.map'])
    expect(saved.name).toBe('exec')
    expect(saved.prompt).toBe('For the executive team')
    expect((saved.sections[0] as { cites: string[] }).cites).toEqual(['overview.facts', 'study.findings'])
  })

  it('approves the plan and shows the built PDF', async () => {
    const calls = stubApi({ 'GET /api/reports/alpha/plan': plan })
    open()
    await screen.findByText('3 sections')
    fireEvent.click(screen.getByRole('button', { name: /Approve and build/ }))
    expect(await screen.findByText('Report built')).toBeTruthy()
    expect(calls.some((c) => c.method === 'POST' && c.url === '/api/reports/alpha/plan/approve')).toBe(true)
    expect(screen.getByText(/2026-11-18-exec.pdf: 6 pages, 3 sections/)).toBeTruthy()
    expect(screen.getByRole('link', { name: /Open/ }).getAttribute('href')).toBe(
      '/api/reports/alpha/files/2026-11-18-exec.pdf?inline=true',
    )
  })

  it("won't build while a section has lost its source, and says which", async () => {
    stubApi({
      'GET /api/reports/alpha/plan': plan,
      'GET /api/reports/alpha/catalog': [
        ...catalog.slice(0, 2),
        entry('study.findings', 'Findings', { group: 'study', available: false, reason: 'none recorded' }),
      ],
    })
    open()
    expect(await screen.findByText(/Some sections lost their source/)).toBeTruthy()
    const build = screen.getByRole('button', { name: /Approve and build/ }) as HTMLButtonElement
    await waitFor(() => expect(build.disabled).toBe(true))
  })

  it('discards the plan after confirming', async () => {
    const calls = stubApi({ 'GET /api/reports/alpha/plan': plan, 'DELETE /api/reports/alpha/plan': null })
    vi.stubGlobal('confirm', vi.fn(() => true))
    open()
    await screen.findByText('3 sections')
    fireEvent.click(screen.getByRole('button', { name: /Discard plan/ }))
    await waitFor(() => expect(calls.some((c) => c.method === 'DELETE')).toBe(true))
  })
})

describe('Guided report, choosing the sections', () => {
  it('lets Claude use everything by default, and sends no restriction', async () => {
    const calls = stubApi()
    open()
    fireEvent.change(await screen.findByLabelText(/What do you need/), { target: { value: 'For executives' } })
    expect(await screen.findByText('all of them')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /Ask Claude to plan the report/ }))
    await waitFor(() => expect(calls.some((c) => c.method === 'POST' && c.url === '/api/feedback')).toBe(true))
    const body = (calls.find((c) => c.method === 'POST' && c.url === '/api/feedback')!.body as { body: string }).body
    expect(body).not.toContain('Use only these sections')
  })

  it('sends the sections that were ticked when some are left out', async () => {
    const calls = stubApi()
    open()
    fireEvent.change(await screen.findByLabelText(/What do you need/), { target: { value: 'For executives' } })
    fireEvent.click(await screen.findByText(/Which sections can Claude use/))
    fireEvent.click(await screen.findByLabelText('Component map (top level)'))
    expect(await screen.findByText('2 of 3 chosen')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /Ask Claude to plan the report/ }))
    await waitFor(() => expect(calls.some((c) => c.method === 'POST' && c.url === '/api/feedback')).toBe(true))
    const body = (calls.find((c) => c.method === 'POST' && c.url === '/api/feedback')!.body as { body: string }).body
    expect(body).toContain("Use only these sections (catalog ids), and don't read or cite any others:")
    expect(body).toContain('- overview.facts\n- study.findings')
    expect(body).not.toContain('study.map')
  })

  it('will not ask with no sections at all', async () => {
    stubApi()
    open()
    fireEvent.change(await screen.findByLabelText(/What do you need/), { target: { value: 'For executives' } })
    fireEvent.click(await screen.findByText(/Which sections can Claude use/))
    for (const title of ['Summary and facts', 'Component map (top level)', 'Findings'])
      fireEvent.click(await screen.findByLabelText(title))
    const button = screen.getByRole('button', { name: /Ask Claude to plan the report/ }) as HTMLButtonElement
    await waitFor(() => expect(button.disabled).toBe(true))
  })

  it('adds a section to the plan from the checklist, and keeps what Claude wrote', async () => {
    const withMore = [...catalog, entry('study.interfaces', 'Interfaces', { group: 'study' })]
    const calls = stubApi({
      'GET /api/reports/alpha/plan': plan,
      'GET /api/reports/alpha/catalog': withMore,
      'PUT /api/reports/alpha/plan': plan,
    })
    open()
    await screen.findByText('3 sections')
    fireEvent.click(screen.getByText('Add or remove sections'))
    fireEvent.click(await screen.findByLabelText('Interfaces'))
    await waitFor(() => expect(calls.some((c) => c.method === 'PUT')).toBe(true))
    const saved = calls.find((c) => c.method === 'PUT')!.body as typeof plan.plan
    expect(saved.sections.map((s) => s.id)).toEqual([
      'authored:summary',
      'study.map',
      'study.findings',
      'study.interfaces',
    ])
    expect((saved.sections[0] as { body: string }).body).toBe('Alpha owns **items**.')
  })
})

describe('The Reports tab', () => {
  const tab = () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <MantineProvider>
        <QueryClientProvider client={qc}>
          <MemoryRouter>
            <ReportTab project="alpha" />
          </MemoryRouter>
        </QueryClientProvider>
      </MantineProvider>,
    )
  }

  it('shows a plan waiting for review, with Approve and build', async () => {
    stubApi({ 'GET /api/reports/alpha/plan': plan, 'GET /api/reports/alpha/files': [] })
    tab()
    expect(await screen.findByRole('button', { name: /Approve and build/ })).toBeTruthy()
    expect(screen.getByText('Executive review')).toBeTruthy()
  })

  it('shows no plan card when there is none', async () => {
    stubApi({ 'GET /api/reports/alpha/files': [] })
    tab()
    expect(await screen.findByText(/No reports built yet/)).toBeTruthy()
    expect(screen.queryByRole('button', { name: /Approve and build/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /Ask Claude to plan/ })).toBeNull()
  })
})
