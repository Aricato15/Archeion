import { MantineProvider } from '@mantine/core'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import type { ResponderStatus } from '../api/types'
import { ClaudeJobsCard } from './ClaudeJobs'

const status: ResponderStatus = {
  enabled: false,
  running: false,
  jobs: [],
  headless: false,
  max_instances: 1,
  instances: 0,
  terminal_running: false,
  last_run_at: null,
  waiting: 0,
  can_start: true,
  reason: null,
}

afterEach(() => vi.unstubAllGlobals())

it('sets headless and the number of Claude instances', async () => {
  const puts: unknown[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (_url: string, init?: RequestInit) => {
      if (init?.method === 'PUT') puts.push(JSON.parse(String(init.body)))
      return new Response(JSON.stringify(status), { status: 200 })
    }),
  )
  render(
    <MantineProvider>
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <ClaudeJobsCard />
      </QueryClientProvider>
    </MantineProvider>,
  )
  expect(await screen.findByText('0 of 1 running')).toBeTruthy()
  fireEvent.click(screen.getByLabelText('Headless'))
  await waitFor(() => expect(puts).toContainEqual({ headless: true }))
  fireEvent.click(screen.getByText('2'))
  await waitFor(() => expect(puts).toContainEqual({ max_instances: 2 }))
})
