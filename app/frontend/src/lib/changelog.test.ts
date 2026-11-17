import { describe, expect, it } from 'vitest'
import { byNewest, parseChangelog } from './changelog'

const log = `# Changelog

Intro text.

## [Unreleased]

## [1.2.0] - 2026-11-17

### Added
- A thing.

## [1.1.0] - 2026-11-16

- Older.

## 1.0.0

- No date, no brackets.
`

describe('parseChangelog', () => {
  it('splits releases, newest first, and drops empty ones', () => {
    const r = parseChangelog(log)
    expect(r.map((x) => x.version)).toEqual(['1.2.0', '1.1.0', '1.0.0'])
    expect(r[0]).toEqual({ version: '1.2.0', date: '2026-11-17', body: '### Added\n- A thing.' })
    expect(r[2].date).toBeNull()
  })

  it('keeps an Unreleased section that has notes', () => {
    expect(parseChangelog('## [Unreleased]\n\n- Soon.\n').map((x) => x.version)).toEqual(['Unreleased'])
  })

  it("doesn't take a heading inside a code block for a release", () => {
    const r = parseChangelog('## [1.0.0] - 2026-01-01\n\n```\n## [9.9.9]\n```\n')
    expect(r.map((x) => x.version)).toEqual(['1.0.0'])
  })

  it('reads nothing from a file with no releases', () => {
    expect(parseChangelog('# Changelog\n\nJust words.\n')).toEqual([])
  })
})

it('puts Unreleased first, then dated releases, newest first', () => {
  const e = (version: string, date: string | null, title = 'A') => ({ version, date, body: 'x', source: title, title, key: version + title })
  const sorted = [e('1.0.0', '2026-01-01'), e('Unreleased', null), e('2.0.0', '2026-02-01'), e('0.1.0', null, 'B')].sort(byNewest)
  expect(sorted.map((x) => x.version)).toEqual(['Unreleased', '2.0.0', '1.0.0', '0.1.0'])
})
