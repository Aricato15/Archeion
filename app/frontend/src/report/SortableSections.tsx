import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core'
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { ActionIcon, Badge, Group, Paper, Stack, Text } from '@mantine/core'
import { IconGripVertical, IconX } from '@tabler/icons-react'
import type { CatalogEntry } from '../api/reports'

function Row({
  index,
  entry,
  onRemove,
}: {
  index: number
  entry: CatalogEntry
  onRemove: (id: string) => void
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: entry.id })
  return (
    <Paper
      ref={setNodeRef}
      withBorder
      px="xs"
      py={4}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.6 : 1,
        zIndex: isDragging ? 2 : undefined,
        position: 'relative',
      }}
    >
      <Group gap="xs" wrap="nowrap">
        <ActionIcon
          variant="subtle"
          color="gray"
          size="sm"
          aria-label={`Drag ${entry.title} to move it`}
          style={{ cursor: 'grab', touchAction: 'none' }}
          {...attributes}
          {...listeners}
        >
          <IconGripVertical size={16} />
        </ActionIcon>
        <Text size="xs" c="dimmed" w={22} ta="right">
          {index + 1}
        </Text>
        <Text size="sm" style={{ flex: 1, minWidth: 0 }} truncate="end" title={entry.title}>
          {entry.title}
        </Text>
        {entry.kind === 'diagram' && (
          <Badge size="xs" variant="light" color="grape">
            diagram
          </Badge>
        )}
        <ActionIcon
          variant="subtle"
          color="gray"
          size="sm"
          aria-label={`Remove ${entry.title}`}
          onClick={() => onRemove(entry.id)}
        >
          <IconX size={14} />
        </ActionIcon>
      </Group>
    </Paper>
  )
}

/** The chosen sections in report order; drag a handle (or focus it and use the arrow keys) to reorder. */
export function SortableSections({
  selection,
  byId,
  onChange,
}: {
  selection: string[]
  byId: Map<string, CatalogEntry>
  onChange: (next: string[]) => void
}) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )
  const onDragEnd = ({ active, over }: DragEndEvent) => {
    if (!over || active.id === over.id) return
    const from = selection.indexOf(String(active.id))
    const to = selection.indexOf(String(over.id))
    if (from >= 0 && to >= 0) onChange(arrayMove(selection, from, to))
  }
  const rows = selection.flatMap((id, i) => {
    const entry = byId.get(id)
    return entry ? [{ id, i, entry }] : []
  })
  return (
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
      <SortableContext items={rows.map((r) => r.id)} strategy={verticalListSortingStrategy}>
        <Stack gap={4}>
          {rows.map((r) => (
            <Row key={r.id} index={r.i} entry={r.entry} onRemove={(id) => onChange(selection.filter((s) => s !== id))} />
          ))}
        </Stack>
      </SortableContext>
    </DndContext>
  )
}
