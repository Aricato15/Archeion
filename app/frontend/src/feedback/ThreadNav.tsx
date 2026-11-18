import { ActionIcon, Button, Stack, Text, Tooltip, UnstyledButton } from '@mantine/core'
import { IconArrowDown, IconArrowUp } from '@tabler/icons-react'
import { useEffect, useState } from 'react'
import type { FeedbackItem } from '../api/types'
import { formatDate } from '../lib/format'
import { SCROLL_MARGIN, messageDomId } from './threadDom'

const jump = (id: number) => document.getElementById(messageDomId(id))?.scrollIntoView({ behavior: 'smooth', block: 'start' })

/**
 * A long thread's table of contents (v1.4.0): one number per message, in order, which scrolls to it.
 * The number is the message's place in the thread (the tooltip has its id and date). The one in view
 * is highlighted, and **Latest** goes to the last message. It stays in view while the thread scrolls.
 */
export function ThreadNav({ thread, current }: { thread: FeedbackItem[]; current: number }) {
  const [active, setActive] = useState<number | null>(null)

  // Which messages are on screen; the first of them is "where you are".
  useEffect(() => {
    if (typeof IntersectionObserver === 'undefined') return
    const visible = new Set<number>()
    const order = thread.map((t) => t.id)
    const observer = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          const id = Number(e.target.getAttribute('data-message'))
          if (e.isIntersecting) visible.add(id)
          else visible.delete(id)
        }
        setActive(order.find((id) => visible.has(id)) ?? null)
      },
      { rootMargin: `-${SCROLL_MARGIN}px 0px -55% 0px` },
    )
    for (const id of order) {
      const el = document.getElementById(messageDomId(id))
      if (el) observer.observe(el)
    }
    return () => observer.disconnect()
  }, [thread])

  const last = thread[thread.length - 1]
  if (!last) return null
  return (
    <Stack gap={6} align="stretch" aria-label="Thread navigation" role="navigation" style={{ width: 84 }}>
      <Text size="xs" c="dimmed" ta="center">
        {thread.length} messages
      </Text>
      <Button
        size="compact-xs"
        variant="default"
        leftSection={<IconArrowUp size={12} />}
        onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
      >
        Top
      </Button>
      <Stack gap={2} style={{ maxHeight: 'calc(100vh - 230px)', overflowY: 'auto' }}>
        {thread.map((t, i) => {
          const on = t.id === (active ?? current)
          return (
            <Tooltip key={t.id} position="left" label={`#${t.id} · ${formatDate(t.created_at)}`}>
              <UnstyledButton
                onClick={() => jump(t.id)}
                aria-label={`Message ${i + 1}, #${t.id}`}
                aria-current={on ? 'true' : undefined}
                style={{
                  textAlign: 'center',
                  padding: '2px 0',
                  borderRadius: 4,
                  fontSize: 13,
                  fontWeight: on ? 700 : 400,
                  color: on ? 'var(--mantine-color-white)' : 'var(--mantine-color-text)',
                  background: on ? 'var(--mantine-primary-color-filled)' : 'transparent',
                  border: `1px solid ${on ? 'transparent' : 'var(--mantine-color-default-border)'}`,
                }}
              >
                {i + 1}
              </UnstyledButton>
            </Tooltip>
          )
        })}
      </Stack>
      <Button
        size="compact-xs"
        variant="light"
        leftSection={<IconArrowDown size={12} />}
        onClick={() => jump(last.id)}
        aria-label="Scroll to the latest message"
      >
        Latest
      </Button>
    </Stack>
  )
}

/** The same jump for narrow windows, where the side panel is hidden: a round button at the corner. */
export function LatestButton({ thread }: { thread: FeedbackItem[] }) {
  const last = thread[thread.length - 1]
  if (!last || thread.length < 2) return null
  return (
    <Tooltip label="Latest message" position="left">
      <ActionIcon
        size="xl"
        radius="xl"
        variant="filled"
        aria-label="Scroll to the latest message"
        onClick={() => jump(last.id)}
        style={{ position: 'fixed', right: 16, bottom: 16, zIndex: 20 }}
      >
        <IconArrowDown size={20} />
      </ActionIcon>
    </Tooltip>
  )
}
