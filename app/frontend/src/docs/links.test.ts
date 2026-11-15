import { describe, expect, it } from 'vitest'
import { DEFAULT_LINKS, docUrl, imageSrc, locate, normalize, resolveLink, type LinkContext } from './links'

const ctx: LinkContext = {
  bases: {
    archeion: 'docs',
    example-gateway: '../example-gateway',
    cdc: '../example-data',
    example-collector: '../example-data/collectors/example-collector',
  },
}

describe('normalize', () => {
  it('keeps leading parent segments', () => {
    expect(normalize('docs/system/../../../example-gateway/docs/api.md')).toBe('../example-gateway/docs/api.md')
    expect(normalize('./a//b/./c')).toBe('a/b/c')
    expect(normalize('a/../..')).toBe('..')
  })
})

describe('locate', () => {
  it('picks the deepest source', () => {
    expect(locate(ctx, '../example-data/collectors/example-collector/README.md')).toEqual({ source: 'example-collector', rel: 'README.md' })
    expect(locate(ctx, '../example-data/docs/x.md')).toEqual({ source: 'cdc', rel: 'docs/x.md' })
    expect(locate(ctx, 'CLAUDE.md')).toBeNull()
  })
})

describe('resolveLink', () => {
  it('routes archeion doc links in-app, keeping the hash', () => {
    expect(resolveLink(ctx, 'archeion', 'roadmap/roadmap.md', '../decisions/0002-x.md#shape')).toEqual({
      kind: 'doc',
      to: '/docs/decisions/0002-x.md#shape',
    })
  })

  it('follows links from archeion into a project, and to a project page', () => {
    expect(resolveLink(ctx, 'archeion', 'system/projects/example-gateway.md', '../../../../example-gateway/docs/api.md')).toEqual({
      kind: 'doc',
      to: '/p/example-gateway/docs/api.md',
    })
    expect(resolveLink(ctx, 'archeion', 'system/overview.md', '../../../example-gateway')).toEqual({
      kind: 'project',
      to: '/projects/example-gateway',
    })
  })

  it('follows links inside and between projects', () => {
    expect(resolveLink(ctx, 'example-gateway', 'docs/services.md', 'api.md')).toEqual({ kind: 'doc', to: '/p/example-gateway/docs/api.md' })
    expect(resolveLink(ctx, 'example-gateway', 'docs/services.md', '../../example-data/README.md')).toEqual({
      kind: 'doc',
      to: '/p/cdc/README.md',
    })
    expect(resolveLink(ctx, 'cdc', 'README.md', 'collectors/example-collector/README.md')).toEqual({ kind: 'doc', to: '/p/example-collector/README.md' })
  })

  it('classifies other links', () => {
    expect(resolveLink(ctx, 'archeion', 'README.md', 'https://semver.org')).toEqual({ kind: 'external', href: 'https://semver.org' })
    expect(resolveLink(ctx, 'archeion', 'README.md', '#now')).toEqual({ kind: 'anchor', hash: '#now' })
    expect(resolveLink(ctx, 'archeion', 'roadmap/roadmap.md', '../../CLAUDE.md').kind).toBe('outside')
    expect(resolveLink(ctx, 'archeion', 'README.md', '/etc/x.md').kind).toBe('outside')
    expect(resolveLink(ctx, 'unknown', 'README.md', 'x.md').kind).toBe('outside')
    expect(resolveLink(ctx, 'archeion', 'roadmap/r.md', 'pic.png')).toEqual({
      kind: 'file',
      href: '/api/docs/raw?source=archeion&path=roadmap%2Fpic.png',
    })
  })

  it('works without a registry (only archeion known)', () => {
    expect(resolveLink(DEFAULT_LINKS, 'archeion', 'README.md', 'my%20doc.md')).toEqual({ kind: 'doc', to: '/docs/my%20doc.md' })
    expect(resolveLink(DEFAULT_LINKS, 'archeion', 'README.md', '../../example-gateway/README.md').kind).toBe('outside')
  })
})

describe('imageSrc', () => {
  it('serves relative images through the backend', () => {
    expect(imageSrc(ctx, 'archeion', 'system/overview.md', '../img/a.svg')).toBe('/api/docs/raw?source=archeion&path=img%2Fa.svg')
    expect(imageSrc(ctx, 'example-gateway', 'docs/x.md', 'img/a.png')).toBe('/api/docs/raw?source=example-gateway&path=docs%2Fimg%2Fa.png')
  })
  it('keeps remote images and refuses everything else', () => {
    expect(imageSrc(ctx, 'archeion', 'README.md', 'https://example.com/a.png')).toBe('https://example.com/a.png')
    expect(imageSrc(ctx, 'archeion', 'README.md', 'javascript:alert(1)')).toBeNull()
    expect(imageSrc(ctx, 'archeion', 'README.md', '../../secret.png')).toBeNull()
    expect(imageSrc(ctx, 'archeion', 'README.md', 'notes.md')).toBeNull()
  })
})

it('docUrl encodes each segment and routes by source', () => {
  expect(docUrl('archeion', 'a b/c#d.md', '#x')).toBe('/docs/a%20b/c%23d.md#x')
  expect(docUrl('example-gateway', 'docs/api.md')).toBe('/p/example-gateway/docs/api.md')
})
