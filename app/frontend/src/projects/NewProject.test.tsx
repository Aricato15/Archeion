import { MantineProvider } from '@mantine/core'
import { Notifications } from '@mantine/notifications'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Registry } from '../api/types'
import { NewProject } from './NewProject'

const registry = {
  projects: [{ id: 'taken', title: 'Taken', available: true }],
  groups: [
    { id: 'sys', title: 'The system', home: 'sys-home', projects: [] },
    { id: 'virtual', title: 'A virtual group', home: null, projects: [] },
  ],
  warnings: [],
  unregistered: [],
} as unknown as Registry

const roots = {
  workspace: null,
  roots: [{ name: 'lab', folder: 'the lab folder', projects: [] }],
  errors: [],
  editable: true,
  locked_reason: null,
}

function setup() {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const post = init?.method === 'POST'
    const body = post
      ? { name: 'fresh', kind: 'project', title: 'fresh', location: 'lab:fresh', files: ['README.md', 'CLAUDE.md'], git: true, page: 'projects/fresh.md' }
      : url.includes('settings/roots')
        ? roots
        : {}
    return new Response(JSON.stringify(body), { status: post ? 201 : 200, headers: { 'content-type': 'application/json' } })
  })
  vi.stubGlobal('fetch', fetchMock)
  render(
    <MantineProvider>
      <Notifications />
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter>
          <NewProject registry={registry} />
        </MemoryRouter>
      </QueryClientProvider>
    </MantineProvider>,
  )
  return fetchMock
}

const posts = (f: ReturnType<typeof setup>) =>
  (f.mock.calls as unknown as [string, RequestInit][]).filter(([, init]) => init?.method === 'POST')

afterEach(() => vi.unstubAllGlobals())

describe('NewProject', () => {
  it('creates a project in the chosen root with the details typed', async () => {
    const f = setup()
    fireEvent.click(screen.getByRole('button', { name: /new project or group/i }))
    const create = await screen.findByRole('button', { name: 'Create' })
    expect((create as HTMLButtonElement).disabled).toBe(true)
    fireEvent.change(screen.getByLabelText(/^Name/), { target: { value: 'fresh' } })
    fireEvent.change(screen.getByLabelText(/Brief description/), { target: { value: 'A brief one.' } })
    await waitFor(() => expect((screen.getByRole('button', { name: 'Create' }) as HTMLButtonElement).disabled).toBe(false))
    expect(screen.getByText(/lab\/fresh\//)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Create' }))
    await waitFor(() => expect(posts(f)).toHaveLength(1))
    const [url, init] = posts(f)[0]
    expect(url).toBe('/api/registry/new')
    expect(JSON.parse(String(init.body))).toEqual({
      root: 'lab',
      name: 'fresh',
      kind: 'project',
      title: null,
      description: 'A brief one.',
      status: 'planned',
      group: null,
      inside_group: false,
      git_init: true,
    })
  })

  it('refuses a bad or taken name', async () => {
    setup()
    fireEvent.click(screen.getByRole('button', { name: /new project or group/i }))
    await screen.findByRole('button', { name: 'Create' })
    fireEvent.change(screen.getByLabelText(/^Name/), { target: { value: 'Bad Name' } })
    expect(await screen.findByText(/Lowercase letters/)).toBeTruthy()
    fireEvent.change(screen.getByLabelText(/^Name/), { target: { value: 'taken' } })
    expect(await screen.findByText('Already a project or group')).toBeTruthy()
    expect((screen.getByRole('button', { name: 'Create' }) as HTMLButtonElement).disabled).toBe(true)
  })
})
