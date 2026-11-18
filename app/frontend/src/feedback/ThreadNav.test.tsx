import { MantineProvider } from '@mantine/core'
import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { FeedbackItem } from '../api/types'
import { ThreadNav } from './ThreadNav'
import { messageDomId } from './threadDom'

const msg = (id: number) => ({ id, created_at: '2026-11-15T03:00:00+00:00' }) as FeedbackItem
const thread = [msg(10), msg(14), msg(21)]

describe('ThreadNav', () => {
  afterEach(() => document.body.replaceChildren())

  it('has a number per message that scrolls to it, and a Latest button', () => {
    const scrolled: string[] = []
    for (const t of thread) {
      const el = document.createElement('div')
      el.id = messageDomId(t.id)
      el.scrollIntoView = vi.fn(() => void scrolled.push(el.id))
      document.body.append(el)
    }
    render(
      <MantineProvider>
        <ThreadNav thread={thread} current={21} />
      </MantineProvider>,
    )
    expect(screen.getAllByRole('button', { name: /^Message \d/ })).toHaveLength(3)
    fireEvent.click(screen.getByRole('button', { name: 'Message 2, #14' }))
    fireEvent.click(screen.getByRole('button', { name: 'Scroll to the latest message' }))
    expect(scrolled).toEqual([messageDomId(14), messageDomId(21)])
    // Without an observer, the thread's focal message is the one marked.
    expect(screen.getByRole('button', { name: 'Message 3, #21' }).getAttribute('aria-current')).toBe('true')
  })
})
