import { describe, expect, it } from 'vitest'
import { anchorForBlock, anchorForSelection, blockForLine, blockOf, describeAnchor, headingFor } from './anchors'

function doc(): HTMLElement {
  const root = document.createElement('div')
  root.innerHTML = [
    '<h1 data-line-start="1" data-line-end="1">Title</h1>',
    '<p data-line-start="3" data-line-end="4">Intro <b>bold</b> text</p>',
    '<h2 data-line-start="6" data-line-end="6">Shape</h2>',
    '<ul data-line-start="8" data-line-end="10"><li>one</li><li>two</li></ul>',
  ].join('\n')
  document.body.appendChild(root)
  return root
}

describe('anchors', () => {
  it('finds the top-level block of a nested node', () => {
    const root = doc()
    const bold = root.querySelector('b')!
    expect(blockOf(root, bold.firstChild)?.tagName).toBe('P')
    expect(blockOf(root, document.body)).toBeNull()
  })

  it('names the nearest heading at or before a block', () => {
    const root = doc()
    const [h1, p, h2, ul] = Array.from(root.children) as HTMLElement[]
    expect(headingFor(p)).toBe('Title')
    expect(headingFor(ul)).toBe('Shape')
    expect(headingFor(h2)).toBe('Shape')
    expect(anchorForBlock(h1)).toEqual({ heading: 'Title', lines: [1, 1] })
    expect(anchorForBlock(ul)).toEqual({ heading: 'Shape', lines: [8, 10] })
  })

  it('builds an anchor from a selection across blocks', () => {
    const root = doc()
    const range = document.createRange()
    range.setStart(root.querySelector('p')!.firstChild!, 0)
    range.setEnd(root.querySelector('li')!.firstChild!, 3)
    const sel = window.getSelection()!
    sel.removeAllRanges()
    sel.addRange(range)
    const anchor = anchorForSelection(root, sel)
    expect(anchor?.heading).toBe('Title')
    expect(anchor?.lines).toEqual([3, 10])
    expect(anchor?.quote).toContain('Intro')
  })

  it('finds the block for a line', () => {
    const root = doc()
    expect(blockForLine(root, 9)?.tagName).toBe('UL')
    expect(blockForLine(root, 5)?.tagName).toBe('P') // between blocks: the one before
    expect(blockForLine(root, 99)?.tagName).toBe('UL')
  })

  it('describes anchors', () => {
    expect(describeAnchor(null)).toBe('Whole doc')
    expect(describeAnchor({ heading: 'Shape', lines: [3, 5] })).toBe('§ Shape, lines 3–5')
    expect(describeAnchor({ lines: [4, 4] })).toBe('line 4')
  })
})
