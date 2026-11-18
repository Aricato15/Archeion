import { MantineProvider } from '@mantine/core'
import { Notifications } from '@mantine/notifications'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Project, PromotePlan } from '../api/types'
import { PromoteGroup } from './PromoteGroup'

const project = (extra: Record<string, unknown> = {}) =>
  ({
    id: 'solo',
    title: 'solo',
    parent: null,
    group: null,
    type: 'project',
    children: [],
    members: [],
    ...extra,
  }) as unknown as Project

const plan = (extra: Partial<PromotePlan> = {}): PromotePlan => ({
  project: 'solo',
  page: 'projects/solo.md',
  ok: true,
  problems: [],
  members: ['solo-mod'],
  group_page: 'groups/solo.md',
  has_study: true,
  has_design: true,
  ...extra,
})

function setup(p: Project, body: unknown = plan()) {
  const fetchMock = vi.fn(async () => new Response(JSON.stringify(body), { status: 200, headers: { 'content-type': 'application/json' } }))
  vi.stubGlobal('fetch', fetchMock)
  render(
    <MantineProvider>
      <Notifications />
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <PromoteGroup project={p} />
      </QueryClientProvider>
    </MantineProvider>,
  )
  return fetchMock
}

const bodies = (f: ReturnType<typeof setup>) =>
  (f.mock.calls as unknown as [string, RequestInit][]).map(([url, init]) => [url, init?.body ? JSON.parse(String(init.body)) : null])

afterEach(() => vi.unstubAllGlobals())

describe('PromoteGroup', () => {
  it('shows what promoting does, then promotes', async () => {
    const f = setup(project())
    fireEvent.click(screen.getByRole('button', { name: /promote to group/i }))
    expect(await screen.findByText(/Members: solo-mod/)).toBeTruthy()
    expect(screen.getByText(/keeps groups\/solo.md as its narrative/)).toBeTruthy()
    expect(screen.getByText(/marked as needing a restudy/)).toBeTruthy()
    expect(bodies(f)[0]).toEqual(['/api/registry/projects/solo/promote', { dry_run: true }])
    fireEvent.click(screen.getByRole('button', { name: 'Promote' }))
    await waitFor(() => expect(bodies(f).some(([, b]) => JSON.stringify(b) === '{}')).toBe(true))
  })

  it('says why it cannot promote, and keeps the button off', async () => {
    setup(project(), plan({ ok: false, problems: ["it's a module of x: make it a project first"] }))
    fireEvent.click(screen.getByRole('button', { name: /promote to group/i }))
    expect(await screen.findByText(/make it a project first/)).toBeTruthy()
    expect((screen.getByRole('button', { name: 'Promote' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('offers nothing for a module, a sub-project or a member of a group', () => {
    setup(project({ type: 'module' }))
    expect(screen.queryByRole('button', { name: /promote/i })).toBeNull()
  })

  it('offers demote for a group, blocked while it has members', async () => {
    setup(project({ type: 'group', members: ['a', 'b'] }))
    fireEvent.click(screen.getByRole('button', { name: /demote to project/i }))
    expect(await screen.findByText(/still has 2 member/)).toBeTruthy()
    expect((screen.getByRole('button', { name: 'Demote' }) as HTMLButtonElement).disabled).toBe(true)
  })
})
