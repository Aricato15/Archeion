import { MantineProvider } from '@mantine/core'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ReportContent } from '../api/reports'
import { PrintReport } from './PrintReport'

vi.mock('mermaid', () => ({
  default: {
    initialize: vi.fn(),
    registerLayoutLoaders: vi.fn(),
    registerIconPacks: vi.fn(),
    parse: vi.fn(async () => true),
    render: vi.fn(async () => ({ svg: '<svg data-testid="diagram"></svg>' })),
  },
}))

const project = {
  id: 'alpha',
  title: 'Alpha',
  summary: 'The alpha service.',
  type: 'project',
  status: 'active',
  group: 'g1',
  kind: null,
  ports: [20100],
  depends_on: ['beta'],
  used_by: [],
  verified: '2026-11-15',
}

const content = {
  project,
  preset: {
    name: 'full',
    mode: 'guided',
    title: '',
    options: { page_size: 'A4', orientation: 'portrait', cover: true, toc: true },
    sections: [],
  },
  generated: '2026-11-18',
  study: {
    id: '2026-11-16-abcdef1',
    date: '2026-11-16',
    commit: 'abcdef1234',
    model: {
      schema: 1,
      meta: { project: 'alpha', date: '2026-11-16', commit: 'abcdef1' },
      components: [{ id: 'api', name: 'API', kind: 'service' }],
      relations: [],
      interfaces: { exposes: [], calls: [] },
      entities: [],
      flows: [],
      activities: [],
      states: [],
      findings: [],
      questions: [],
    },
  },
  sections: [
    {
      id: 'authored:summary',
      title: 'Executive summary',
      type: 'authored',
      markdown: 'Alpha owns items.',
      cites: [{ id: 'overview.facts', title: 'Summary and facts' }],
    },
    { id: 'overview.facts', title: 'Summary and facts', type: 'facts' },
    { id: 'study.map', title: 'Component map (top level)', type: 'diagram', diagram: 'map', focus: null },
    { id: 'study.flow:gone', title: 'Flow: gone', type: 'diagram', diagram: 'flow', ref: 'gone' },
    { id: 'system.dependencies', title: 'Dependencies', type: 'dependencies', depends_on: ['beta'], used_by: [] },
  ],
} as unknown as ReportContent

function mockApi(body: unknown, status = 200) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      const registry = { projects: [], groups: [], warnings: [], unregistered: [] }
      const data = url.includes('/registry') ? registry : body
      const code = url.includes('/registry') ? 200 : status
      return new Response(JSON.stringify(data), { status: code, headers: { 'Content-Type': 'application/json' } })
    }),
  )
}

function renderReport() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <MantineProvider>
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={['/print/report/alpha?preset=full']}>
          <Routes>
            <Route path="/print/report/:project" element={<PrintReport />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    </MantineProvider>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
  delete document.body.dataset.reportState
})

describe('PrintReport', () => {
  it('lays out the cover, contents and every section in order', async () => {
    mockApi(content)
    const { container } = renderReport()
    await screen.findByText('1. Executive summary', { selector: 'h2' })
    expect(screen.getByRole('heading', { level: 1, name: 'Alpha' })).toBeTruthy()
    const headings = [...container.querySelectorAll('.report-section > h2')].map((h) => h.textContent)
    expect(headings).toEqual([
      '1. Executive summary',
      '2. Summary and facts',
      '3. Component map (top level)',
      '4. Flow: gone',
      '5. Dependencies',
    ])
    expect(container.querySelectorAll('.report-toc li')).toHaveLength(5)
    expect(screen.getByText('Written by Claude', { selector: '.written-by' })).toBeTruthy()
    expect(screen.getByText(/Sources: Summary and facts/)).toBeTruthy()
    expect(screen.getByText('20100')).toBeTruthy()
  })

  it('says a diagram can no longer be drawn instead of leaving a gap', async () => {
    mockApi(content)
    renderReport()
    expect(await screen.findByText(/no longer in the study/)).toBeTruthy()
  })

  it('marks the page ready once the diagrams are drawn', async () => {
    mockApi(content)
    renderReport()
    await waitFor(() => expect(document.body.dataset.reportState).toBe('ready'), { timeout: 4000 })
    expect(document.body.dataset.reportSections).toBe('5')
    expect(document.body.dataset.reportFailed).toBe('0')
    expect(document.querySelectorAll('.print-diagram')).toHaveLength(1)
  })

  it('reports an error state when the report cannot be built', async () => {
    mockApi({ detail: 'no section study.map' }, 422)
    renderReport()
    expect(await screen.findByText("This report can't be built")).toBeTruthy()
    await waitFor(() => expect(document.body.dataset.reportState).toBe('error'))
    expect(document.body.dataset.reportError).toContain('study.map')
  })
})
