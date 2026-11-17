import { Anchor, Badge, Group, List, Stack, Text, Title } from '@mantine/core'
import type { StudyActivity, StudyStates } from '../api/study'

type Link = { id: string; name: string; via?: string }

/** What leads into a box and what leaves it, for the side panel of a state or an activity step. */
export function NodeDetails({
  title,
  badges,
  note,
  incoming,
  outgoing,
  onSelect,
}: {
  title: string
  badges: string[]
  note?: string
  incoming: Link[]
  outgoing: Link[]
  onSelect: (id: string) => void
}) {
  const list = (label: string, links: Link[]) =>
    links.length > 0 && (
      <Stack gap={2}>
        <Text size="sm" fw={600}>
          {label}
        </Text>
        <List size="sm" spacing={2}>
          {links.map((l, i) => (
            <List.Item key={`${l.id}-${i}`}>
              <Anchor component="button" type="button" size="sm" onClick={() => onSelect(l.id)}>
                {l.name}
              </Anchor>
              {l.via && (
                <Text span size="sm" c="dimmed">
                  {' '}
                  ({l.via})
                </Text>
              )}
            </List.Item>
          ))}
        </List>
      </Stack>
    )
  return (
    <Stack gap="sm">
      <Group gap="xs">
        <Title order={4}>{title}</Title>
        {badges.map((b) => (
          <Badge key={b} variant="light">
            {b}
          </Badge>
        ))}
      </Group>
      {note && <Text size="sm">{note}</Text>}
      {list('Comes from', incoming)}
      {list('Goes to', outgoing)}
      {incoming.length === 0 && outgoing.length === 0 && <Text c="dimmed">Nothing connects to it.</Text>}
    </Stack>
  )
}

export function StateNode({ m, id, onSelect }: { m: StudyStates; id: string; onSelect: (id: string) => void }) {
  const s = m.states.find((x) => x.id === id)
  if (!s) return <Text c="dimmed">No state '{id}' here.</Text>
  const name = (i: string) => m.states.find((x) => x.id === i)?.label || i
  return (
    <NodeDetails
      title={s.label || s.id}
      badges={[...(m.initial === id ? ['initial'] : []), ...((m.final ?? []).includes(id) ? ['final'] : [])]}
      incoming={m.transitions.filter((t) => t.to === id).map((t) => ({ id: t.from, name: name(t.from), via: t.label }))}
      outgoing={m.transitions.filter((t) => t.from === id).map((t) => ({ id: t.to, name: name(t.to), via: t.label }))}
      onSelect={onSelect}
    />
  )
}

export function ActivityNode({ a, id, onSelect }: { a: StudyActivity; id: string; onSelect: (id: string) => void }) {
  const n = a.nodes.find((x) => x.id === id)
  if (!n) return <Text c="dimmed">No step '{id}' here.</Text>
  const name = (i: string) => a.nodes.find((x) => x.id === i)?.label || i
  return (
    <NodeDetails
      title={n.label || n.id}
      badges={[n.kind ?? 'action']}
      incoming={a.edges.filter((e) => e.to === id).map((e) => ({ id: e.from, name: name(e.from), via: e.label }))}
      outgoing={a.edges.filter((e) => e.from === id).map((e) => ({ id: e.to, name: name(e.to), via: e.label }))}
      onSelect={onSelect}
    />
  )
}
