import { describe, expect, it } from 'vitest'
import { prefersLandscape } from './PrintContext'

const svg = (w: number, h: number) => `<svg viewBox="0 0 ${w} ${h}" style="max-width: ${w}px"></svg>`

describe('prefersLandscape', () => {
  it('keeps small and tall diagrams on a portrait page', () => {
    expect(prefersLandscape(svg(400, 300))).toBe(false)
    expect(prefersLandscape(svg(600, 1200))).toBe(false)
  })

  it('moves wide diagrams to a landscape page', () => {
    expect(prefersLandscape(svg(1600, 500))).toBe(true) // a wide component map
    expect(prefersLandscape(svg(1700, 900))).toBe(true) // a flow with many lanes
  })

  it('does not switch for a diagram that is only slightly wider than the page', () => {
    expect(prefersLandscape(svg(720, 400))).toBe(false)
  })

  it('stays on portrait when the size is unknown', () => {
    expect(prefersLandscape('<svg></svg>')).toBe(false)
    expect(prefersLandscape('<svg viewBox="0 0 0 0"></svg>')).toBe(false)
  })
})
