import { MantineProvider } from '@mantine/core'
import { render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import { MarkdownView } from './MarkdownView'

vi.mock('mermaid', () => ({
  default: {
    initialize: vi.fn(),
    registerLayoutLoaders: vi.fn(),
    registerIconPacks: vi.fn(),
    parse: vi.fn(async (code: string) => {
      if (code.includes('broken')) throw new Error('Parse error on line 1')
      return true
    }),
    render: vi.fn(async () => ({ svg: '<svg data-testid="diagram"></svg>' })),
  },
}))

function wrap(node: ReactNode) {
  return render(
    <MantineProvider>
      <MemoryRouter>{node}</MemoryRouter>
    </MantineProvider>,
  )
}

describe('MarkdownView', () => {
  it('rewrites links and marks blocks with source lines', () => {
    const { container } = wrap(
      <MarkdownView
        docPath="roadmap/roadmap.md"
        content={'# Roadmap\n\nSee [the plan](plan.md) and [outside](../../CLAUDE.md).\n'}
      />,
    )
    expect(screen.getByText('the plan').closest('a')?.getAttribute('href')).toBe('/docs/roadmap/plan.md')
    expect(screen.getByText('outside').closest('a')).toBeNull()
    const p = container.querySelector('p')!
    expect(p.dataset.lineStart).toBe('3')
    expect(container.querySelector('h1')?.id).toBe('roadmap')
  })

  it('renders mermaid blocks, and shows the source when a diagram is broken', async () => {
    wrap(
      <MarkdownView
        docPath="README.md"
        content={'```mermaid\nflowchart LR\n  A --> B\n```\n\n```mermaid\nbroken\n```\n'}
      />,
    )
    expect(await screen.findByTestId('diagram')).toBeTruthy()
    expect(await screen.findByText('This diagram has an error')).toBeTruthy()
    expect(screen.getByText('broken')).toBeTruthy()
  })
})
