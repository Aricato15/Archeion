import { MantineProvider } from '@mantine/core'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Project } from '../api/types'
import { StudyTab } from './StudyTab'

// Mermaid can't render in jsdom: show the code instead.
vi.mock('../docs/MermaidBlock', () => ({ MermaidBlock: ({ code }: { code: string }) => <pre data-testid="mermaid">{code}</pre> }))
// ELK needs a worker: lay everything out in a row instead.
vi.mock('../graph/layout', () => ({
  layoutGraph: async (root: { children?: { width?: number; height?: number }[] }) => ({
    ...root,
    children: root.children?.map((c, i) => ({ ...c, x: i * 200, y: 0, width: c.width ?? 300, height: c.height ?? 150 })),
  }),
}))

const project = { id: 'example', title: 'Example' } as Project

const row = {
  id: '2026-11-16-abcdef1',
  project: 'example',
  date: '2026-11-16',
  commit: 'abcdef1234',
  dirty: false,
  summary: 'An example service.',
  counts: { components: 2, relations: 1, entities: 0, flows: 1, activities: 0, states: 0, findings: 1, exposes: 1, calls: 0 },
  valid: true,
  problems: [],
  notes: false,
  draft: false,
  thread: null,
  commits_since: 3,
}

const model = {
  schema: 1,
  meta: { project: 'example', date: '2026-11-16', commit: 'abcdef1234', summary: 'An example service.', stack: ['python'] },
  components: [
    { id: 'api', name: 'API', kind: 'service', summary: 'Serves things.', cites: [{ path: 'src/app.py', line: 3, snippet: 'app = App()' }] },
    { id: 'db', name: 'app.db', kind: 'database' },
  ],
  relations: [{ id: 'r1', from: 'api', to: 'db', kind: 'sql', label: 'SELECT' }],
  interfaces: { exposes: [{ id: 'x', kind: 'http', method: 'GET', path: '/items', handler: 'api' }], calls: [] },
  flows: [{ id: 'f', title: 'Read items', participants: ['api', 'db'], steps: [{ from: 'api', to: 'db', label: 'SELECT' }] }],
  findings: [{ id: 'f1', severity: 'warn', title: 'No index' }],
}

function mockApi(snapshots: unknown[]) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      const body = url.endsWith('/studies/example') ? snapshots : { ...row, model, notes_text: '' }
      return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })
    }),
  )
}

function renderTab(path = '/projects/example?tab=study') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <MantineProvider>
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={[path]}>
          <StudyTab project={project} />
        </MemoryRouter>
      </QueryClientProvider>
    </MantineProvider>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear() // the Interactive / Mermaid choice is remembered
})

describe('StudyTab', () => {
  it('offers to ask for a study when there is none', async () => {
    mockApi([])
    renderTab()
    expect(await screen.findByText(/No study of example yet/)).toBeTruthy()
    expect(screen.getByRole('button', { name: /Ask Claude to study example/ })).toBeTruthy()
  })

  it('shows the overview, staleness and the generated diagrams', async () => {
    mockApi([row])
    const { container } = renderTab()
    expect(await screen.findByText('An example service.')).toBeTruthy()
    expect(screen.getByText('3 commits behind')).toBeTruthy()
    fireEvent.click(screen.getByText('Components 2'))
    // The interactive graph first, with a box per component...
    await waitFor(() => expect(container.querySelector('[data-node="db"]')).toBeTruthy())
    fireEvent.click(container.querySelector('[data-node="db"]')!)
    expect((await screen.findAllByText('app.db')).length).toBeGreaterThan(1) // the details drawer opened
    // ...and the same map as Mermaid on request.
    fireEvent.click(screen.getByText('Mermaid'))
    const map = await screen.findByTestId('mermaid')
    expect(map.textContent).toContain('flowchart LR')
    expect(map.textContent).toContain('SELECT')
  })

  it('opens a flow as a sequence diagram and a component in the details drawer', async () => {
    mockApi([row])
    renderTab('/projects/example?tab=study&view=flows')
    // The interactive view first, with Mermaid one click away.
    expect(await screen.findByLabelText('Find in the flow')).toBeTruthy()
    fireEvent.click(screen.getByText('Mermaid'))
    expect((await screen.findByTestId('mermaid')).textContent).toContain('sequenceDiagram')
    renderTab('/projects/example?tab=study&view=components&item=api')
    expect((await screen.findAllByText('Serves things.')).length).toBe(2) // the table and the drawer
    expect(screen.getByText('src/app.py:3')).toBeTruthy()
  })

  it('opens a participant panel on a flow without leaving the flow', async () => {
    mockApi([row])
    const { container } = renderTab('/projects/example?tab=study&view=flows')
    await screen.findByLabelText('Find in the flow')
    fireEvent.click(container.querySelector('[data-lane="api"]')!)
    expect(await screen.findByText('Serves things.')).toBeTruthy()
    expect(screen.getByLabelText('Find in the flow')).toBeTruthy()
  })

  it('sends a flow participant to the component map from its panel', async () => {
    mockApi([row])
    const { container } = renderTab('/projects/example?tab=study&view=flows')
    await screen.findByLabelText('Find in the flow')
    fireEvent.click(container.querySelector('[data-lane="api"]')!)
    fireEvent.click(await screen.findByRole('button', { name: 'Show in the component map' }))
    // The flow is gone and the component map (with its Find box) is showing.
    await waitFor(() => expect(screen.queryByLabelText('Find in the flow')).toBeNull())
    expect(await screen.findByLabelText('Find in the map')).toBeTruthy()
  })

  it('shows a study in progress with a link to its conversation', async () => {
    mockApi([{ ...row, id: 'draft', draft: true, thread: 12 }, row])
    renderTab()
    expect(await screen.findByText('A study is in progress')).toBeTruthy()
    expect(screen.getByRole('link', { name: /the conversation \(#12\)/ }).getAttribute('href')).toBe('/feedback/12')
    expect(screen.queryByRole('button', { name: /Ask for a refresh/ })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'View the draft' }))
    expect(await screen.findByText('An example service.')).toBeTruthy()
  })
})