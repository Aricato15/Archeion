import { MantineProvider } from '@mantine/core'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { DriftAlert } from './Drift'

const links = {
  links: [],
  unresolved: [],
  drift: [
    { project: 'web', code_only: ['datasvc'], registry_only: [] },
    { project: 'bff', code_only: [], registry_only: ['legacy'] },
  ],
  studied: ['web', 'bff'],
}

function show(project?: string) {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(links), { status: 200 })))
  render(
    <MantineProvider>
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter>
          <DriftAlert project={project} />
        </MemoryRouter>
      </QueryClientProvider>
    </MantineProvider>,
  )
}

afterEach(() => vi.unstubAllGlobals())

describe('DriftAlert', () => {
  it('lists every disagreement on the Projects page', async () => {
    show()
    expect(await screen.findByText('The code and the registry disagree')).toBeTruthy()
    expect(screen.getByRole('link', { name: 'datasvc' })).toBeTruthy()
    expect(screen.getByRole('link', { name: 'legacy' })).toBeTruthy()
  })

  it('shows only its own on a project page, and nothing when there is none', async () => {
    show('bff')
    expect(await screen.findByText(/never calls/)).toBeTruthy()
    expect(screen.queryByRole('link', { name: 'datasvc' })).toBeNull()
  })
})
