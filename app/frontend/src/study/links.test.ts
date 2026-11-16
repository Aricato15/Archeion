import { describe, expect, it } from 'vitest'
import { describeAnchor } from '../docs/anchors'
import { studyUrl } from './links'

describe('study anchors', () => {
  const s = { project: 'example', snapshot: '2026-11-16-abcdef1', element: 'api.routes', kind: 'component' as const }

  it('link to the element in the Study tab', () => {
    expect(studyUrl(s)).toBe('/projects/example?tab=study&snap=2026-11-16-abcdef1&view=components&item=api.routes')
    expect(studyUrl({ ...s, kind: 'finding', element: 'f1' })).toBe(
      '/projects/example?tab=study&snap=2026-11-16-abcdef1&view=findings',
    )
  })

  it('describe themselves', () => {
    expect(describeAnchor({ study: s })).toBe('component api.routes in the study of example')
  })
})
