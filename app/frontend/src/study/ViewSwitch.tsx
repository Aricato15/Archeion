import { Group, SegmentedControl, Stack } from '@mantine/core'
import { type ReactNode, useState } from 'react'

const KEY = 'archeion.diagramView'
type Mode = 'interactive' | 'mermaid'

function stored(): Mode {
  try {
    return localStorage.getItem(KEY) === 'mermaid' ? 'mermaid' : 'interactive'
  } catch {
    return 'interactive'
  }
}

/** A diagram drawn two ways: the interactive view (the default) and the Mermaid one. The choice is remembered. */
export function ViewSwitch({ interactive, mermaid }: { interactive: ReactNode; mermaid: ReactNode }) {
  const [mode, setMode] = useState<Mode>(stored)
  return (
    <Stack gap="xs">
      <Group justify="flex-end">
        <SegmentedControl
          size="xs"
          aria-label="How to draw it"
          value={mode}
          onChange={(v) => {
            setMode(v as Mode)
            try {
              localStorage.setItem(KEY, v)
            } catch {
              // not remembered
            }
          }}
          data={[
            { value: 'interactive', label: 'Interactive' },
            { value: 'mermaid', label: 'Mermaid' },
          ]}
        />
      </Group>
      {mode === 'interactive' ? interactive : mermaid}
    </Stack>
  )
}
