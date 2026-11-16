import { MantineProvider } from '@mantine/core'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { DiagramFrame } from './DiagramFrame'
import { bindLabels } from './diagramLabels'

const svg = '<svg xmlns="http://www.w3.org/2000/svg"><g><text>routes</text><text>other</text></g></svg>'

function show(labels = {}) {
  const view = render(
    <MantineProvider>
      <DiagramFrame svg={svg} labels={labels} title="A flow" />
    </MantineProvider>,
  )
  const inner = view.container.querySelector('.mermaid-block') as HTMLElement
  return { ...view, inner }
}

describe('DiagramFrame', () => {
  it('zooms with the buttons and Ctrl+wheel, but lets a plain wheel scroll the page', () => {
    const { inner } = show()
    expect(screen.getByText('100%')).toBeTruthy()
    fireEvent.click(screen.getByLabelText('Zoom in'))
    expect(screen.getByText('125%')).toBeTruthy()
    expect(inner.style.transform).toContain('scale(1.25)')
    fireEvent.click(screen.getByLabelText('Fit'))
    expect(inner.style.transform).toContain('scale(1)')
    const viewport = inner.parentElement!
    fireEvent.wheel(viewport, { deltaY: -100 })
    expect(screen.getByText('100%')).toBeTruthy()
    fireEvent.wheel(viewport, { deltaY: -100, ctrlKey: true })
    expect(screen.getByText('112%')).toBeTruthy()
  })

  it('pans by dragging', () => {
    const { inner } = show()
    const viewport = inner.parentElement!
    fireEvent.pointerDown(viewport, { button: 0, clientX: 10, clientY: 10 })
    fireEvent.pointerMove(viewport, { clientX: 60, clientY: 30 })
    fireEvent.pointerUp(viewport)
    expect(inner.style.transform).toContain('translate(50px, 20px)')
  })

  it('makes named labels clickable, and not after a drag', () => {
    const open = vi.fn()
    const { inner } = show({ routes: open })
    const label = inner.querySelector('[data-diagram-link="routes"]')!
    expect(inner.querySelector('[data-diagram-link="other"]')).toBeNull()
    fireEvent.click(label)
    expect(open).toHaveBeenCalledTimes(1)
    const viewport = inner.parentElement!
    fireEvent.pointerDown(viewport, { button: 0, clientX: 0, clientY: 0 })
    fireEvent.pointerMove(viewport, { clientX: 40, clientY: 0 })
    fireEvent.click(label)
    expect(open).toHaveBeenCalledTimes(1)
  })

  it('opens full screen', async () => {
    show()
    fireEvent.click(screen.getByLabelText('Full screen'))
    expect(await screen.findByText('Wheel to zoom, drag to pan.')).toBeTruthy()
    expect(screen.getByText('A flow')).toBeTruthy()
  })
})

it('bindLabels binds the innermost match only and cleans up', () => {
  const root = document.createElement('div')
  root.innerHTML = '<div class="label"><span>store</span></div>'
  const f = vi.fn()
  const off = bindLabels(root, { store: f }, () => false)
  expect(root.querySelectorAll('.diagram-link')).toHaveLength(1)
  ;(root.querySelector('span') as HTMLElement).click()
  expect(f).toHaveBeenCalledTimes(1)
  off()
  expect(root.querySelectorAll('.diagram-link')).toHaveLength(0)
})
