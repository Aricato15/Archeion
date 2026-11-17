import { MantineProvider } from '@mantine/core'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { StudyFlow } from '../api/study'
import { SequenceView } from './SequenceView'

const components = [
  { id: 'api', name: 'API', kind: 'service' },
  { id: 'db', name: 'app.db', kind: 'database' },
] as never
const flow = {
  id: 'f',
  title: 'Read',
  participants: ['api', 'db'],
  steps: [
    { from: 'api', to: 'db', label: 'SELECT items' },
    { from: 'db', to: 'api', label: 'rows', reply: true },
  ],
} as unknown as StudyFlow

describe('SequenceView', () => {
  it('opens a participant on click, and dims the other messages on hover and search', () => {
    const open = vi.fn()
    const { container } = render(
      <MantineProvider>
        <SequenceView flow={flow} components={components} onOpen={open} />
      </MantineProvider>,
    )
    fireEvent.click(container.querySelector('[data-lane="db"]')!)
    expect(open).toHaveBeenCalledWith('db')
    fireEvent.change(screen.getByLabelText('Find in the flow'), { target: { value: 'ROWS' } })
    const groups = [...container.querySelectorAll('g[opacity]')].filter((g) => g.querySelector('title')?.textContent?.includes(':'))
    const opacities = groups.map((g) => g.getAttribute('opacity'))
    expect(opacities).toContain('0.2')
    expect(opacities).toContain('1')
  })
})
