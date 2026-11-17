import { MantineProvider } from '@mantine/core'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { GlossaryTab } from './GlossaryTab'
import { searchTerms } from './search'

const terms = [
  { id: 'gateway', term: 'Gateway', aliases: ['GW'], definition: 'The front door.' },
  { id: 'audit-log', term: 'audit log', aliases: [], definition: 'Who did what, kept by the Gateway.' },
  { id: 'saga', term: 'Saga', aliases: [], definition: 'A long running job.' },
]

describe('searchTerms', () => {
  it('ignores case, looks at aliases and meanings, and puts name matches first', () => {
    expect(searchTerms(terms, 'GATEWAY').map((t) => t.id)).toEqual(['gateway', 'audit-log'])
    expect(searchTerms(terms, 'gw').map((t) => t.id)).toEqual(['gateway'])
    expect(searchTerms(terms, '  ').length).toBe(3)
    expect(searchTerms(terms, 'zzz')).toEqual([])
  })
})

describe('GlossaryTab', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('lists terms and filters them as you type', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(terms), { status: 200 })))
    render(
      <MantineProvider>
        <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
          <GlossaryTab project="example" />
        </QueryClientProvider>
      </MantineProvider>,
    )
    expect(await screen.findByText('Saga')).toBeTruthy()
    fireEvent.change(screen.getByLabelText('Search the glossary'), { target: { value: 'sAgA' } })
    await waitFor(() => expect(screen.queryByText('Gateway')).toBeNull())
    expect(screen.getByText('Saga')).toBeTruthy()
    fireEvent.change(screen.getByLabelText('Search the glossary'), { target: { value: 'nothing' } })
    expect(await screen.findByText(/Nothing matches/)).toBeTruthy()
  })
})
