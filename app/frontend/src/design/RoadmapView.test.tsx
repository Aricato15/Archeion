import { MantineProvider } from '@mantine/core'
import { Notifications } from '@mantine/notifications'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ChecklistItem, DesignRoadmap } from '../api/design'
import { RoadmapView } from './RoadmapView'

const item = (id: string, title: string, status: ChecklistItem['status'], phase: string | null = null): ChecklistItem => ({
  id,
  title,
  note: '',
  kind: 'feature',
  status,
  phase,
  priority: null,
  refs: [],
  depends_on: [],
  history: [],
})

function mock(data: Partial<DesignRoadmap>) {
  const body: DesignRoadmap = { now: [], next: [], later: [], done: [], phases: [], pending: 0, markdown: '', ...data }
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })),
  )
}

function renderView(revision: number | null = null, onOpen = vi.fn()) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <MantineProvider>
      <Notifications />
      <QueryClientProvider client={qc}>
        <RoadmapView project="example" slug="main" revision={revision} onOpenItem={onOpen} />
      </QueryClientProvider>
    </MantineProvider>,
  )
  return onOpen
}

afterEach(() => vi.unstubAllGlobals())

describe('RoadmapView', () => {
  it('draws the columns and says when changes are waiting', async () => {
    mock({ now: [item('c1', 'Build it', 'doing')], next: [item('c2', 'Ship it', 'decided')], pending: 2 })
    renderView()
    expect(await screen.findByText('Build it')).toBeTruthy()
    expect(screen.getByText('Ship it')).toBeTruthy()
    expect(screen.getByText(/2 changes on the checklist aren't in this roadmap/)).toBeTruthy()
  })

  it('opens the checklist from an item, and hides the pending notice on a revision', async () => {
    mock({ now: [item('c1', 'Build it', 'doing')], pending: 3 })
    const onOpen = renderView(2)
    fireEvent.click(await screen.findByText('c1'))
    expect(onOpen).toHaveBeenCalledWith('c1')
    expect(screen.queryByText(/aren't in this roadmap/)).toBeNull()
  })

  it('groups by phase on the timeline switch', async () => {
    mock({
      now: [item('c1', 'Build it', 'doing', 'Phase 1')],
      phases: [
        { phase: 'Phase 1', items: [item('c1', 'Build it', 'doing', 'Phase 1')] },
        { phase: null, items: [item('c2', 'Loose idea', 'idea')] },
      ],
    })
    renderView()
    await screen.findByText('Build it')
    fireEvent.click(screen.getByText('By phase'))
    expect(await screen.findByText('No phase yet')).toBeTruthy()
    expect(screen.getByText('Loose idea')).toBeTruthy()
  })

  it('explains an empty roadmap', async () => {
    mock({})
    renderView()
    expect(await screen.findByText(/nothing on it is decided yet/)).toBeTruthy()
  })
})
