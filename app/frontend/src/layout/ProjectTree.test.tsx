import { MantineProvider } from '@mantine/core'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import type { Registry } from '../api/types'
import { ProjectTree } from './ProjectTree'

const project = (id: string, extra: Record<string, unknown> = {}) => ({
  id,
  title: id,
  page: `projects/${id}.md`,
  path: `../${id}`,
  root: null,
  parent: null,
  group: null,
  status: 'active',
  kind: null,
  type: 'project',
  type_source: 'detected',
  detected_type: 'project',
  owner: null,
  inbox_edits: true,
  inbox_edits_source: 'default',
  ports: [],
  depends_on: [],
  docs_dir: 'docs',
  verified: '2026-11-15',
  summary: '',
  available: true,
  children: [],
  used_by: [],
  ...extra,
})

const registry = {
  projects: [project('datasvc', { children: ['collector-a'] }), project('collector-a', { parent: 'datasvc', type: 'module', detected_type: 'module', owner: 'datasvc' })],
  groups: [],
  warnings: [],
  unregistered: [],
} as unknown as Registry

function Where() {
  return <div data-testid="where">{useLocation().pathname}</div>
}

function renderAt(path: string, onNavigate = vi.fn()) {
  render(
    <MantineProvider>
      <MemoryRouter initialEntries={[path]}>
        <ProjectTree registry={registry} onNavigate={onNavigate} />
        <Where />
      </MemoryRouter>
    </MantineProvider>,
  )
  return onNavigate
}

const parent = () => screen.getByRole('link', { name: 'datasvc' })

describe('ProjectTree', () => {
  it('opens a parent project’s page and unfolds its sub-projects', () => {
    const onNavigate = renderAt('/docs/README.md')
    expect(parent().getAttribute('aria-expanded')).toBe('false')
    fireEvent.click(parent())
    expect(screen.getByTestId('where').textContent).toBe('/projects/datasvc')
    expect(parent().getAttribute('aria-expanded')).toBe('true')
    expect(onNavigate).toHaveBeenCalled()
    // clicking it again keeps it open
    fireEvent.click(parent())
    expect(parent().getAttribute('aria-expanded')).toBe('true')
  })

  it('folds and unfolds with the chevron, without leaving the page', () => {
    renderAt('/docs/README.md')
    const chevron = parent().querySelector('[data-toggle]')!
    fireEvent.click(chevron)
    expect(parent().getAttribute('aria-expanded')).toBe('true')
    expect(screen.getByTestId('where').textContent).toBe('/docs/README.md')
    fireEvent.click(chevron)
    expect(parent().getAttribute('aria-expanded')).toBe('false')
  })

  it('starts unfolded on a module’s page, with the module icon', () => {
    renderAt('/projects/collector-a')
    expect(parent().getAttribute('aria-expanded')).toBe('true')
    expect(screen.getByRole('link', { name: 'collector-a' }).getAttribute('href')).toBe('/projects/collector-a')
    // modules get their own icon (ADR 0016)
    expect(screen.getByRole('link', { name: 'collector-a' }).querySelector('[data-type="module"]')).toBeTruthy()
    expect(parent().querySelector('[data-type="module"]')).toBeNull()
  })
})
