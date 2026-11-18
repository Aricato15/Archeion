import { MantineProvider } from '@mantine/core'
import { Notifications } from '@mantine/notifications'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Project } from '../api/types'
import { BreakDown } from './BreakDown'

const group = { id: 'top', title: 'Top', type: 'group', members: [] } as unknown as Project

const proposals = [
  { folder: 'ma', name: 'ma', type: 'module', components: ['svc-a'] },
  { folder: 'nested', name: 'nested', type: 'project', components: ['sub'] },
]

function setup(plan: unknown = proposals) {
  const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
    const body = init?.method === 'POST' ? { pages: ['projects/ma.md'] } : plan
    return new Response(JSON.stringify(body), { status: init?.method === 'POST' ? 201 : 200, headers: { 'content-type': 'application/json' } })
  })
  vi.stubGlobal('fetch', fetchMock)
  render(
    <MantineProvider>
      <Notifications />
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <BreakDown group={group} />
      </QueryClientProvider>
    </MantineProvider>,
  )
  return fetchMock
}

afterEach(() => vi.unstubAllGlobals())

describe('BreakDown', () => {
  it('lists the folders the study suggests and registers the ones left ticked', async () => {
    const f = setup()
    fireEvent.click(screen.getByRole('button', { name: /break down/i }))
    expect(await screen.findByText('ma/')).toBeTruthy()
    expect(screen.getByText('nested/')).toBeTruthy()
    // untick the sub-project, rename the module
    fireEvent.click(screen.getByLabelText('Register nested'))
    fireEvent.change(screen.getByLabelText('ma/'), { target: { value: 'part-a' } })
    fireEvent.click(screen.getByRole('button', { name: /register 1 member/i }))
    await waitFor(() => {
      const post = (f.mock.calls as unknown as [string, RequestInit][]).find(([, init]) => init?.method === 'POST')
      expect(post?.[0]).toBe('/api/registry/projects/top/break-down')
      expect(JSON.parse(String(post?.[1].body))).toEqual({ members: [{ folder: 'ma', name: 'part-a' }] })
    })
  })

  it('says what to do when the study suggests nothing', async () => {
    setup([])
    fireEvent.click(screen.getByRole('button', { name: /break down/i }))
    expect(await screen.findByText(/Nothing to suggest/)).toBeTruthy()
    expect((screen.getByRole('button', { name: /register/i }) as HTMLButtonElement).disabled).toBe(true)
  })
})
