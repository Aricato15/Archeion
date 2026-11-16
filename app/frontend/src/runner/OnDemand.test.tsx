import { MantineProvider } from '@mantine/core'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ResponderStatus } from '../api/types'
import { OnDemandCard } from './OnDemand'

const base: ResponderStatus = {
  enabled: false,
  running: false,
  pid: null,
  started_at: null,
  last_run_at: null,
  waiting: 0,
  can_start: true,
  reason: null,
}

function show(status: ResponderStatus) {
  const calls: { url: string; method: string; body: unknown }[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      const body = init?.body ? JSON.parse(String(init.body)) : null
      calls.push({ url, method, body })
      const next = method === 'PUT' ? { ...status, enabled: body.enabled } : status
      return new Response(JSON.stringify(next), { status: 200 })
    }),
  )
  render(
    <MantineProvider>
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter>
          <OnDemandCard />
        </MemoryRouter>
      </QueryClientProvider>
    </MantineProvider>,
  )
  return calls
}

afterEach(() => vi.unstubAllGlobals())

describe('OnDemandCard', () => {
  it('switches on and runs once', async () => {
    const calls = show(base)
    fireEvent.click(await screen.findByLabelText('Answer new messages'))
    await waitFor(() => expect(calls.some((c) => c.method === 'PUT' && (c.body as { enabled: boolean }).enabled)).toBe(true))
    fireEvent.click(screen.getByRole('button', { name: /Run now/ }))
    await waitFor(() => expect(calls.some((c) => c.url.endsWith('/responder/run'))).toBe(true))
  })

  it("can't be switched on while the inbox terminal runs", async () => {
    show({ ...base, can_start: false, reason: 'The inbox terminal is running. Stop it first.' })
    const toggle = (await screen.findByLabelText('Answer new messages')) as HTMLInputElement
    expect(toggle.disabled).toBe(true)
    expect(screen.getByRole('button', { name: /Run now/ }).hasAttribute('disabled')).toBe(true)
    expect(screen.getByText(/The inbox terminal is running/)).toBeTruthy()
  })
})
