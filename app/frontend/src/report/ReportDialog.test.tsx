import { MantineProvider } from '@mantine/core'
import { Notifications } from '@mantine/notifications'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { CatalogEntry } from '../api/reports'
import { ReportDialog } from './ReportDialog'
import { ReportTab } from './ReportTab'

const entry = (id: string, group: CatalogEntry['group'], title: string, extra: Partial<CatalogEntry> = {}) => ({
  id,
  group,
  title,
  kind: 'text',
  available: true,
  reason: null,
  parent: null,
  ...extra,
})

const catalog = [
  entry('overview.facts', 'overview', 'Summary and facts'),
  entry('study.map', 'study', 'Component map (top level)', { kind: 'diagram' }),
  entry('study.sub:api', 'study', 'Sub-system: API', { kind: 'diagram', parent: 'study.map' }),
  entry('design.brief', 'design', 'Brief', { available: false, reason: 'no design yet' }),
]

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
        'GET /api/reports/alpha/preflight': { ok: true, problems: [], browser: true, frontend: true },
        'PUT /api/reports/alpha/presets': { name: 'full' },
        'POST /api/reports/alpha/presets/full/build': { id: 'abc123abc123', status: 'running' },
        'GET /api/reports/alpha/builds/abc123abc123': {
          id: 'abc123abc123',
          status: 'done',
          result: { file: '2026-11-18-full.pdf', pages: 5, sections: 3, failed: 0 },
        },
        'GET /api/reports/alpha/files': [],
        ...overrides,
      }
      if (!(key in table)) return new Response('{"detail":"unexpected"}', { status: 404 })
      return new Response(JSON.stringify(table[key]), { status: 200, headers: { 'Content-Type': 'application/json' } })
    }),
  )
  return calls
}

function renderWith(node: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <MantineProvider>
      <Notifications />
      <QueryClientProvider client={qc}>{node}</QueryClientProvider>
    </MantineProvider>,
  )
}

afterEach(() => vi.unstubAllGlobals())

describe('ReportDialog', () => {
  it('starts with every available section, in order, and greys out what has no source', async () => {
    stubApi()
    renderWith(<ReportDialog project="alpha" opened onClose={() => {}} />)
    expect(await screen.findByText('3 sections')).toBeTruthy()
    const dialog = screen.getByRole('dialog')
    const brief = within(dialog).getByLabelText('Brief') as HTMLInputElement
    expect(brief.disabled).toBe(true)
    expect(within(dialog).getByText('no design yet')).toBeTruthy()
    const order = within(dialog).getAllByLabelText(/^Drag /).map((b) => b.getAttribute('aria-label'))
    expect(order).toEqual([
      'Drag Summary and facts to move it',
      'Drag Component map (top level) to move it',
      'Drag Sub-system: API to move it',
    ])
  })

  it('removes a section from the order when it is unticked, and adds it back', async () => {
    stubApi()
    renderWith(<ReportDialog project="alpha" opened onClose={() => {}} />)
    await screen.findByText('3 sections')
    const dialog = screen.getByRole('dialog')
    fireEvent.click(within(dialog).getByLabelText('Remove Summary and facts'))
    expect(await screen.findByText('2 sections')).toBeTruthy()
    fireEvent.click(within(dialog).getByLabelText('Summary and facts'))
    expect(await screen.findByText('3 sections')).toBeTruthy()
  })

  it('saves the preset and starts the build with the chosen sections, then offers the PDF', async () => {
    const calls = stubApi()
    renderWith(<ReportDialog project="alpha" opened onClose={() => {}} />)
    await screen.findByText('3 sections')
    const dialog = screen.getByRole('dialog')
    fireEvent.click(within(dialog).getByLabelText('Remove Sub-system: API'))
    fireEvent.change(within(dialog).getByLabelText('Report title'), { target: { value: 'Q4 review' } })
    fireEvent.click(within(dialog).getByRole('button', { name: /Generate PDF/ }))
    await screen.findByText('Report built')
    const save = calls.find((c) => c.method === 'PUT')!
    expect(save.body).toMatchObject({
      name: 'full',
      mode: 'standard',
      title: 'Q4 review',
      sections: [{ id: 'overview.facts' }, { id: 'study.map' }],
      options: { page_size: 'A4', orientation: 'portrait', cover: true, toc: true },
    })
    expect(calls.some((c) => c.method === 'POST' && c.url.endsWith('/presets/full/build'))).toBe(true)
    expect(screen.getByText(/2026-11-18-full.pdf: 5 pages, 3 sections/)).toBeTruthy()
    expect(screen.getByRole('button', { name: /Preview/ })).toBeTruthy()
  })

  it('shows why a report cannot be built and does not offer to generate it', async () => {
    stubApi({
      'GET /api/reports/alpha/preflight': {
        ok: false,
        problems: ["the viewer frontend isn't running (start.bat); the PDF is printed from it"],
      },
    })
    renderWith(<ReportDialog project="alpha" opened onClose={() => {}} />)
    expect(await screen.findByText(/frontend isn't running/)).toBeTruthy()
    const button = screen.getByRole('button', { name: /Generate PDF/ }) as HTMLButtonElement
    await waitFor(() => expect(button.disabled).toBe(true))
  })

  it('shows the reason when the build fails', async () => {
    stubApi({
      'GET /api/reports/alpha/builds/abc123abc123': { id: 'abc123abc123', status: 'error', error: 'Edge crashed' },
    })
    renderWith(<ReportDialog project="alpha" opened onClose={() => {}} />)
    await screen.findByText('3 sections')
    fireEvent.click(screen.getByRole('button', { name: /Generate PDF/ }))
    expect(await screen.findByText('Edge crashed')).toBeTruthy()
  })
})

describe('ReportTab', () => {
  it('says so when nothing was built', async () => {
    stubApi()
    renderWith(<ReportTab project="alpha" />)
    expect(await screen.findByText(/No reports built yet/)).toBeTruthy()
  })

  it('lists the built reports with how each was made', async () => {
    stubApi({
      'GET /api/reports/alpha/files': [
        {
          file: '2026-11-18-full.pdf',
          preset: 'full',
          mode: 'standard',
          built: '2026-11-18T10:00:00Z',
          pages: 30,
          failed: 0,
          bytes: 1500000,
        },
        { file: 'old.pdf', mode: 'guided', pages: 4, failed: 2, bytes: 2048 },
      ],
    })
    renderWith(<ReportTab project="alpha" />)
    expect(await screen.findByText('2026-11-18-full.pdf')).toBeTruthy()
    expect(screen.getByText('1.4 MB')).toBeTruthy()
    expect(screen.getByText('guided')).toBeTruthy()
    expect(screen.getByText('2 diagram(s) failed')).toBeTruthy()
    expect(screen.getByLabelText('Download old.pdf').getAttribute('href')).toBe('/api/reports/alpha/files/old.pdf')
  })
})
