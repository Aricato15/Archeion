import { describe, expect, it } from 'vitest'
import { docUrl, imageSrc, resolveLink, resolveRelative } from './links'

describe('resolveRelative', () => {
  it('joins onto the doc folder', () => {
    expect(resolveRelative('roadmap/roadmap.md', 'plan.md')).toBe('roadmap/plan.md')
    expect(resolveRelative('roadmap/roadmap.md', '../system/overview.md')).toBe('system/overview.md')
    expect(resolveRelative('README.md', './system/x.md')).toBe('system/x.md')
  })
  it('refuses to leave docs/', () => {
    expect(resolveRelative('roadmap/roadmap.md', '../../CLAUDE.md')).toBeNull()
    expect(resolveRelative('README.md', '../x.md')).toBeNull()
  })
})

describe('resolveLink', () => {
  const from = 'roadmap/roadmap.md'
  it('routes doc links in-app, keeping the hash', () => {
    expect(resolveLink(from, '../decisions/0002-x.md#shape')).toEqual({
      kind: 'doc',
      to: '/docs/decisions/0002-x.md#shape',
    })
  })
  it('classifies other links', () => {
    expect(resolveLink(from, 'https://semver.org')).toEqual({ kind: 'external', href: 'https://semver.org' })
    expect(resolveLink(from, '#now')).toEqual({ kind: 'anchor', hash: '#now' })
    expect(resolveLink(from, '../../CLAUDE.md').kind).toBe('outside')
    expect(resolveLink(from, '/etc/x.md').kind).toBe('outside')
    expect(resolveLink(from, 'pic.png')).toEqual({ kind: 'file', href: '/api/docs/raw?path=roadmap%2Fpic.png' })
  })
  it('decodes encoded names', () => {
    expect(resolveLink('README.md', 'my%20doc.md')).toEqual({ kind: 'doc', to: '/docs/my%20doc.md' })
  })
})

describe('imageSrc', () => {
  it('serves relative images through the backend', () => {
    expect(imageSrc('system/overview.md', '../img/a.svg')).toBe('/api/docs/raw?path=img%2Fa.svg')
  })
  it('keeps remote images and refuses everything else', () => {
    expect(imageSrc('README.md', 'https://example.com/a.png')).toBe('https://example.com/a.png')
    expect(imageSrc('README.md', 'javascript:alert(1)')).toBeNull()
    expect(imageSrc('README.md', '../../secret.png')).toBeNull()
    expect(imageSrc('README.md', 'notes.md')).toBeNull()
  })
})

it('docUrl encodes each segment', () => {
  expect(docUrl('a b/c#d.md', '#x')).toBe('/docs/a%20b/c%23d.md#x')
})
