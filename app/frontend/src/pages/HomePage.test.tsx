import { MantineProvider } from '@mantine/core'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { HomePage } from './HomePage'

const logs: Record<string, string> = {
  archeion: '# Changelog\n\n## [Unreleased]\n\n## [1.2.0] - 2026-11-17\n\n- Added a glossary.\n\n## [1.1.0] - 2026-11-10\n\n- Older thing.\n',
  gateway: '## [0.3.0] - 2026-11-14\n\n- Gateway thing.\n',
}

function mockApi() {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      const u = new URL(url, 'http://x')
      if (u.pathname === '/api/changelog') return new Response(JSON.stringify({ content: logs.archeion }), { status: 200 })
      if (u.pathname === '/api/version') return new Response(JSON.stringify({ version: '1.2.0' }), { status: 200 })
      if (u.pathname === '/api/sources') {
        return new Response(
          JSON.stringify([
            { id: 'archeion', title: 'Archeion', kind: 'archeion' },
            { id: 'registry', title: 'Registry', kind: 'registry' },
            { id: 'gateway', title: 'Gateway', kind: 'project' },
            { id: 'quiet', title: 'Quiet', kind: 'project' },
          ]),
          { status: 200 },
        )
      }
      const source = u.searchParams.get('source') ?? ''
      if (u.pathname === '/api/docs/file' && source === 'gateway') {
        return new Response(JSON.stringify({ path: 'CHANGELOG.md', content: logs.gateway, dirty: false }), { status: 200 })
      }
      return new Response(JSON.stringify({ detail: 'not found' }), { status: 404 })
    }),
  )
}

function renderHome() {
  return render(
    <MantineProvider>
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter>
          <HomePage />
        </MemoryRouter>
      </QueryClientProvider>
    </MantineProvider>,
  )
}

describe('HomePage', () => {
  afterEach(() => vi.unstubAllGlobals())
  const releases = (c: HTMLElement) => [...c.querySelectorAll('[data-release]')].map((el) => el.getAttribute('data-release'))

  it("starts on Archeion's own changelog, shown whole, with no projects in it", async () => {
    mockApi()
    renderHome()
    expect(await screen.findByText('Added a glossary.')).toBeTruthy()
    expect(screen.getByText('Older thing.', { exact: false })).toBeTruthy()
    expect(screen.queryByText('Gateway thing.')).toBeNull()
  })

  it('says so when the changelog is missing', async () => {
    mockApi()
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ detail: 'this checkout has no CHANGELOG.md' }), { status: 404 }))
    vi.stubGlobal('fetch', fetchMock)
    renderHome()
    expect(await screen.findByText(/couldn't be read/)).toBeTruthy()
  })

  it('switches to the projects, skipping those without a changelog, and back', async () => {
    mockApi()
    const { container } = renderHome()
    await screen.findByText('Added a glossary.')
    fireEvent.click(screen.getByText('Projects'))
    await screen.findByText('Gateway thing.')
    expect(releases(container)).toEqual(['gateway@0.3.0'])
    expect(screen.queryByText(/couldn't be read/)).toBeNull()
    fireEvent.click(screen.getByText('Archeion'))
    expect(await screen.findByText('Added a glossary.')).toBeTruthy()
    await waitFor(() => expect(releases(container)).toEqual([]))
  })
})
