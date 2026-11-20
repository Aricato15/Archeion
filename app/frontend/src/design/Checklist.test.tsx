import { MantineProvider } from '@mantine/core'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Checklist as ChecklistData, ChecklistItem } from '../api/design'
import { Checklist } from './Checklist'

const item = (over: Partial<ChecklistItem>): ChecklistItem => ({
  id: 'c1',
  title: 'Export to PDF',
  note: 'Both kinds of report.',
  kind: 'feature',
  status: 'decided',
  phase: 'Phase 2',
  priority: 'high',
  refs: [],
  depends_on: [],
  history: [{ at: '2026-11-20T10:00:00Z', by: 'claude', change: 'added', reason: 'agreed' }],
  ...over,
})

function data(over: Partial<ChecklistData> = {}): ChecklistData {
  const items = over.items ?? [item({}), item({ id: 'c2', title: 'Old idea', note: '', status: 'dropped' })]
  const pending = over.pending ?? []
  return {
    items,
    pending,
    log: [],
    counts: { total: items.filter((i) => i.status !== 'dropped').length, done: 0, pending: pending.length, staged: pending.length },
  }
}

let state: ChecklistData
let calls: { url: string; method: string; body: unknown }[]

function mockApi() {
  calls = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      calls.push({ url, method, body: init?.body ? JSON.parse(String(init.body)) : undefined })
      const body = url.includes('/feedback/7') ? { item: { id: 7 }, thread: [{ id: 7 }, { id: 9 }] } : state
      return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })
    }),
  )
}

function renderList(revision: number | null = null) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <MantineProvider>
      <QueryClientProvider client={qc}>
        <Checklist project="example" slug="main" revision={revision} thread={7} />
      </QueryClientProvider>
    </MantineProvider>,
  )
}

beforeEach(() => {
  state = data()
  mockApi()
  try {
    localStorage.clear()
  } catch {
    // none
  }
})
afterEach(() => vi.unstubAllGlobals())

describe('Checklist', () => {
  it('shows a minimal list that hides dropped items, and rich details on the switch', async () => {
    renderList()
    expect(await screen.findByText('Export to PDF')).toBeTruthy()
    expect(screen.queryByText('Old idea')).toBeNull()
    expect(screen.queryByText('Both kinds of report.')).toBeNull()
    fireEvent.click(screen.getByText('Rich'))
    expect(screen.getByText('Both kinds of report.')).toBeTruthy()
    expect(screen.getByText('Old idea')).toBeTruthy()
    expect(localStorage.getItem('archeion.checklist.mode')).toBe('rich')
  })

  it('stages an added item as the user instead of applying it', async () => {
    renderList()
    await screen.findByText('Export to PDF')
    fireEvent.change(screen.getByLabelText('Add an item'), { target: { value: 'Dark mode' } })
    fireEvent.click(screen.getByRole('button', { name: 'Stage' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'POST' && c.url.endsWith('/checklist/changes'))).toBe(true))
    const post = calls.find((c) => c.method === 'POST')!
    expect(post.body).toMatchObject({ changes: [{ op: 'add', fields: { title: 'Dark mode', kind: 'idea', status: 'idea' } }] })
  })

  it('reviews a proposal: accept, reject, comment, then confirm only decided changes', async () => {
    state = data({
      pending: [
        {
          id: 'p1',
          op: 'update',
          item: 'c1',
          fields: { status: 'doing' },
          reason: 'work started',
          by: 'claude',
          state: 'pending',
          staged: '2026-11-20T10:00:00Z',
          comments: [],
        },
        {
          id: 'p2',
          op: 'add',
          item: null,
          fields: { title: 'Dark mode' },
          reason: '',
          by: 'claude',
          state: 'pending',
          staged: '2026-11-20T10:00:00Z',
          comments: [{ at: '2026-11-20T10:05:00Z', by: 'user', text: 'later' }],
        },
      ],
    })
    renderList()
    expect(await screen.findByText(/Waiting for your review \(2\)/)).toBeTruthy()
    expect(screen.getByText('Why: work started')).toBeTruthy()
    const confirm = screen.getByRole('button', { name: /Confirm 0 decisions/ })
    expect((confirm as HTMLButtonElement).disabled).toBe(true)

    fireEvent.click(screen.getAllByRole('button', { name: 'Accept' })[0])
    await waitFor(() =>
      expect(calls.find((c) => c.method === 'PUT')?.body).toEqual({ state: 'accepted' }),
    )
    expect(calls.find((c) => c.method === 'PUT')!.url).toContain('/checklist/changes/p1')

    fireEvent.click(screen.getByRole('button', { name: 'Send comments to Claude' }))
    await waitFor(() => expect(calls.some((c) => c.url.endsWith('/feedback') && c.method === 'POST')).toBe(true))
    const sent = calls.find((c) => c.url.endsWith('/feedback'))!.body as { parent_id: number; body: string }
    expect(sent.parent_id).toBe(9)
    expect(sent.body).toContain('later')
  })

  it('is read-only for a frozen revision', async () => {
    renderList(1)
    await screen.findByText('Export to PDF')
    expect(screen.queryAllByLabelText('Status of Export to PDF')).toHaveLength(0)
    expect(screen.queryByText('Add an item')).toBeNull()
    expect(screen.getByText(/Frozen with the revision/)).toBeTruthy()
  })
})
