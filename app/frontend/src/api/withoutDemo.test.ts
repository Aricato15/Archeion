import { describe, expect, it } from 'vitest'
import { withoutDemo } from './queries'
import type { Registry } from './types'

describe('withoutDemo', () => {
  it('drops the example project from the lists of the user’s own projects', () => {
    const reg = {
      projects: [{ id: 'a' }, { id: 'example-project', demo: true }],
      groups: [],
      warnings: [],
      unregistered: [],
    } as unknown as Registry
    expect(withoutDemo(reg).projects.map((p) => p.id)).toEqual(['a'])
  })
})
