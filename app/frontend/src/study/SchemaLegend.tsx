import { Badge, Group, Text, Tooltip } from '@mantine/core'
import { useMemo } from 'react'
import type { StudyEntity } from '../api/study'
import { buildSchema } from './schema'

/** What the schema view's lines mean, and how many of each there are. */
export function SchemaLegend({ entities }: { entities: StudyEntity[] }) {
  const { links } = useMemo(() => buildSchema(entities), [entities])
  const inferred = links.filter((l) => l.inferred).length
  return (
    <Group gap="xs">
      <Badge variant="light" color="blue">
        {links.length - inferred} declared key(s)
      </Badge>
      {inferred > 0 && (
        <Tooltip label="Columns named like a key (owner_id) that the study didn't declare, linked to the matching table's primary key">
          <Badge variant="outline" color="gray">
            {inferred} inferred
          </Badge>
        </Tooltip>
      )}
      <Text size="xs" c="dimmed">
        Each line runs from a foreign-key column to the column it references. Hover a table to light up its relations;
        drag a table to move it; click it for its fields and sources.
      </Text>
    </Group>
  )
}
