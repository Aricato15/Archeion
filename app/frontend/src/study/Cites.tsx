import { Anchor, Code, Collapse, Group, Stack, Text } from '@mantine/core'
import { useState } from 'react'
import type { Cite } from '../api/study'

/** Where a cite points, as path:line or path:line-end. */
const citeText = (c: Cite) => `${c.path}${c.line ? `:${c.line}${c.end && c.end !== c.line ? `-${c.end}` : ''}` : ''}`

function OneCite({ cite }: { cite: Cite }) {
  const [open, setOpen] = useState(false)
  return (
    <Stack gap={2}>
      <Group gap={6}>
        <Code>{citeText(cite)}</Code>
        {cite.snippet && (
          <Anchor component="button" type="button" size="xs" onClick={() => setOpen((o) => !o)}>
            {open ? 'hide snippet' : 'show snippet'}
          </Anchor>
        )}
      </Group>
      {cite.snippet && (
        <Collapse expanded={open}>
          <Code block>{cite.snippet}</Code>
        </Collapse>
      )}
    </Stack>
  )
}

/** The code an element was read from (ADR 0019). Paths are relative to the project; the
 * viewer shows only the snippets the study kept, never the project's source itself. */
export function Cites({ cites, title = 'Sources' }: { cites?: Cite[]; title?: string }) {
  if (!cites?.length) return null
  return (
    <Stack gap={4}>
      <Text size="xs" c="dimmed" fw={500}>
        {title}
      </Text>
      {cites.map((c, i) => (
        <OneCite key={`${c.path}:${c.line ?? 0}:${i}`} cite={c} />
      ))}
    </Stack>
  )
}
