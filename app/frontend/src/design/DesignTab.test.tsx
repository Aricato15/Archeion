import { MantineProvider } from '@mantine/core'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { asStudyModel, type DesignFull, type DesignRow } from '../api/design'
import { DesignTab } from './DesignTab'

// Mermaid can't render in jsdom: show the code instead.
vi.mock('../docs/MermaidBlock', () => ({ MermaidBlock: ({ code }: { code: string }) => <pre data-testid="mermaid">{code}</pre> }))

const row: DesignRow = {
  project: 'example',
  slug: 'main',
  stage: 'architecture',
  updated: '2026-11-17T10:00:00Z',
  thread: 7,
  revision: null,
  revisions: [],
  changed_since_revision: false,
  summary: 'An example, redesigned.',
  valid: true,
  problems: [],
  files: {},
  counts: { components: 2, exposes: 1, calls: 0, entities: 0, flows: 0 },
  structure: { ports: [20101] },
  checklist: { total: 0, done: 0, pending: 0, staged: 0 },
}

const full: DesignFull = {
  ...row,
  label: 'working copy',
  files: {
    'brief.md': '# Brief\n\nExample keeps the items and serves them to the web app.\n',
    'architecture.md': '# Architecture\n',
    'plan.md': '# Plan\n',
    'questions.md': '# Open questions\n\n- Who calls it?\n',
    'decisions/0001-use-sqlite.md': '# 0001: Use SQLite\n\nOne file per service.\n',
  },
  model: {
    schema: 1,
    meta: { project: 'example', date: '2026-11-17', summary: 'An example, redesigned.' },
    components: [
      { id: 'api', name: 'API', kind: 'service' },
      { id: 'db', name: 'example.db', kind: 'database' },
    ],
    relations: [{ id: 'r1', from: 'api', to: 'db', kind: 'sql' }],
    interfaces: { exposes: [{ id: 'x', kind: 'http', method: 'GET', path: '/api/items' }], calls: [] },
    entities: [],
    flows: [],
    activities: [],
    states: [],
    questions: [],
    structure: { ports: [20101], depends_on: ['other'] },
  },
  model_problems: [],
}

function mockApi(rows: DesignRow[], opts: { blockHandoff?: boolean } = {}) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      let body: unknown = {}
      if (url.includes('/preflight')) {
        const handoff = url.includes('for=handoff')
        body =
          handoff && opts.blockHandoff
            ? {
                ok: false,
                problems: [
                  {
                    severity: 'block',
                    code: 'inbox-edits-off',
                    message: "Archeion's /inbox may not edit example.",
                    fix: 'projects inbox-edits example on',
                  },
                ],
              }
            : { ok: true, problems: [] }
      } else if (url.endsWith('/impact')) {
        body = [
          {
            kind: 'missing-endpoint',
            severity: 'warn',
            message: "other doesn't expose 'POST /api/y', which this design calls.",
            neighbour: 'other',
            suggestion: 'Please add POST /api/y.',
          },
          { kind: 'unverified', severity: 'info', message: 'third has not been studied.', neighbour: 'third', suggestion: null },
        ]
      } else if (url.endsWith('/built')) {
        body = {
          studied: '2026-11-16-abcdef1',
          sections: { components: { designed_only: ['example.db'], built_only: ['cache'], both: 1 } },
        }
      } else if (url.endsWith('/approval')) {
        body = {
          problems: [],
          changes: [{ key: 'ports', old: [20100], new: [20100, 20101], value: '[20100, 20101]' }],
          page: 'projects/example.md',
          next_revision: 1,
        }
      } else if (url.endsWith('/stage') && init?.method === 'PUT') {
        body = { ...row, stage: 'plan' }
      } else if (url.includes('/checklist')) {
        body = { items: [], pending: [], log: [], counts: row.checklist }
      } else if (url.includes('/designs/example/main')) {
        body = full
      } else if (url.includes('/designs/example')) {
        body = rows
      } else if (url.includes('/responder')) {
        body = { enabled: false }
      }
      return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })
    }),
  )
}

function renderTab() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <MantineProvider>
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={['/projects/example?tab=design']}>
          <DesignTab project="example" />
        </MemoryRouter>
      </QueryClientProvider>
    </MantineProvider>,
  )
}

afterEach(() => vi.unstubAllGlobals())

describe('DesignTab', () => {
  it('offers to start a design when there is none', async () => {
    mockApi([])
    renderTab()
    expect(await screen.findByRole('button', { name: /Ask Claude to design example/ })).toBeTruthy()
  })

  it('shows the stage, the brief and the generated diagrams', async () => {
    mockApi([row])
    renderTab()
    expect(await screen.findByText('An example, redesigned.')).toBeTruthy()
    expect(screen.getByText('draft')).toBeTruthy()
    expect(await screen.findByText(/Example keeps the items/)).toBeTruthy()
    fireEvent.click(screen.getByText('Architecture'))
    // Interactive views first; Mermaid is behind a switch on each diagram.
    fireEvent.click((await screen.findAllByText('Mermaid'))[0])
    const diagram = await screen.findByTestId('mermaid')
    expect(diagram.textContent).toContain('example.db')
    expect(screen.getByText('/api/items', { exact: false })).toBeTruthy()
    expect(screen.getByText('What approval records in the registry')).toBeTruthy()
  })

  it('shows decisions and open questions', async () => {
    mockApi([row])
    renderTab()
    await screen.findByText(/Example keeps the items/)
    fireEvent.click(screen.getByText('Decisions'))
    expect(await screen.findByText(/One file per service/)).toBeTruthy()
    fireEvent.click(screen.getByText('Open questions'))
    expect(await screen.findByText(/Who calls it/)).toBeTruthy()
  })

  it('lets the user approve after seeing which registry lines change', async () => {
    mockApi([row])
    renderTab()
    await screen.findByText(/Example keeps the items/)
    fireEvent.click(screen.getByRole('button', { name: 'Approve' }))
    expect(await screen.findByText(/revision 1/)).toBeTruthy()
    expect(screen.getByText('[20100, 20101]')).toBeTruthy()
    expect(screen.getByText(/projects\/example\.md/)).toBeTruthy()
  })

  it('moves the stage when the user picks one', async () => {
    mockApi([row])
    renderTab()
    await screen.findByText(/Example keeps the items/)
    fireEvent.click(screen.getByLabelText('plan'))
    await waitFor(() => {
      const calls = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls
      expect(calls.some(([u, i]) => String(u).endsWith('/stage') && i?.method === 'PUT')).toBe(true)
    })
  })

  it('offers the handoff only once a revision exists, and shows what blocks it', async () => {
    const approved: DesignRow = {
      ...row,
      stage: 'approved',
      revision: 1,
      revisions: [{ id: '2026-11-17-r1', number: 1, date: '2026-11-17', handoff: null }],
    }
    mockApi([approved], { blockHandoff: true })
    renderTab()
    const button = await screen.findByRole('button', { name: /Hand off revision 1/ })
    expect(await screen.findByText(/may not edit example/)).toBeTruthy()
    expect((button as HTMLButtonElement).disabled).toBe(true)
  })
})

describe('DesignTab, across projects', () => {
  it('lists what the design asks of other projects, and sends an item to the neighbour', async () => {
    mockApi([row])
    renderTab()
    await screen.findByText(/Example keeps the items/)
    fireEvent.click(screen.getByText('Impact on others'))
    expect(await screen.findByText(/doesn't expose 'POST \/api\/y'/)).toBeTruthy()
    expect(screen.getByText(/third has not been studied/)).toBeTruthy()
    // Only an item with something to say can be sent.
    expect(screen.getAllByRole('button', { name: /Send to/ })).toHaveLength(1)
    fireEvent.click(screen.getByRole('button', { name: 'Send to other' }))
    await waitFor(() => {
      const posts = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.filter(
        ([u, i]) => String(u) === '/api/feedback' && i?.method === 'POST',
      )
      expect(posts).toHaveLength(1)
      expect(JSON.parse(posts[0][1].body)).toMatchObject({ source: 'other', body: 'Please add POST /api/y.' })
    })
  })

  it('compares the design with the latest study', async () => {
    mockApi([row])
    renderTab()
    await screen.findByText(/Example keeps the items/)
    fireEvent.click(screen.getByText('Built vs designed'))
    expect(await screen.findByText(/study 2026-11-16-abcdef1/)).toBeTruthy()
    expect(screen.getByText('example.db')).toBeTruthy()
    expect(screen.getByText('cache')).toBeTruthy()
  })
})

describe('asStudyModel', () => {
  it('gives a design the commit and sections the study views expect', () => {
    const m = asStudyModel({ ...full.model, entities: undefined } as unknown as DesignFull['model'])!
    expect(m.meta.commit).toBe('design')
    expect(m.entities).toEqual([])
    expect(m.findings).toEqual([])
    expect(asStudyModel(null)).toBeNull()
  })
})
