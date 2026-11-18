import { ActionIcon, Modal, Tooltip } from '@mantine/core'
import { IconArrowsMaximize } from '@tabler/icons-react'
import type { ReactNode } from 'react'

/** The height of a diagram shown full screen: the window minus the modal's title bar and padding. */
export const FULL_HEIGHT = 'calc(100vh - 96px)'

/** The button every diagram has for opening itself full screen (v1.4.0). */
export function FullScreenButton({ onClick, size = 'md' }: { onClick: () => void; size?: 'sm' | 'md' }) {
  return (
    <Tooltip label="Full screen" position="right">
      <ActionIcon size={size} variant="default" aria-label="Full screen" onClick={onClick}>
        <IconArrowsMaximize size={size === 'sm' ? 14 : 16} />
      </ActionIcon>
    </Tooltip>
  )
}

/** A diagram in a window of its own that fills the screen. Escape or the close button leaves it. */
export function FullScreenModal({
  opened,
  onClose,
  title,
  children,
}: {
  opened: boolean
  onClose: () => void
  title?: string
  children: ReactNode
}) {
  return (
    <Modal opened={opened} onClose={onClose} fullScreen title={title ?? 'Diagram'} padding="sm">
      {opened && children}
    </Modal>
  )
}
