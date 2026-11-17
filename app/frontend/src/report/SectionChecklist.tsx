import { Checkbox, Group, ScrollArea, Stack, Text } from '@mantine/core'
import type { CatalogEntry } from '../api/reports'
import { GROUP_TITLES, groupEntries, groupState, toggle, toggleGroup } from './config'

/**
 * The checklist of sections a report can hold, grouped, with a tri-state box per group. Sections
 * with no source are greyed out with the reason. Shared by the standard report, and by the guided
 * one (to scope what Claude may use, and to add sections back to its plan). `selection` is the
 * ordered list of chosen ids, and may hold ids that aren't in the catalog (sections Claude wrote),
 * which are left alone.
 */
export function SectionChecklist({
  entries,
  selection,
  onChange,
  height = 380,
}: {
  entries: CatalogEntry[]
  selection: string[]
  onChange: (next: string[]) => void
  height?: number
}) {
  return (
    <ScrollArea h={height} type="auto" offsetScrollbars>
      <Stack gap="md">
        {groupEntries(entries).map(({ group, entries: items }) => {
          const state = groupState(selection, entries, group)
          const usable = items.some((i) => i.available)
          return (
            <Stack key={group} gap={4}>
              <Checkbox
                label={GROUP_TITLES[group]}
                fw={600}
                styles={{ label: { fontWeight: 600 } }}
                checked={state === 'all'}
                indeterminate={state === 'some'}
                disabled={!usable}
                onChange={(e) => onChange(toggleGroup(selection, entries, group, e.currentTarget.checked))}
              />
              {items.map((entry) => (
                <Group key={entry.id} gap="xs" ml={entry.parent ? 56 : 28} wrap="nowrap">
                  <Checkbox
                    size="xs"
                    label={entry.title}
                    checked={selection.includes(entry.id)}
                    disabled={!entry.available}
                    onChange={() => onChange(toggle(selection, entry, entries))}
                  />
                  {!entry.available && (
                    <Text size="xs" c="dimmed">
                      {entry.reason}
                    </Text>
                  )}
                </Group>
              ))}
            </Stack>
          )
        })}
      </Stack>
    </ScrollArea>
  )
}
