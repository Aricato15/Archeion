import { Anchor, Badge, Button, Code, Divider, Group, List, Stack, Text, Title } from '@mantine/core'
import { IconMessagePlus } from '@tabler/icons-react'
import type { StudyModel } from '../api/study'
import { Cites } from './Cites'

/** Everything the study knows about one component: what it is, where it lives, what it
 * talks to, which flows pass through it and which endpoints it handles. */
export function ComponentDetails({
  model,
  id,
  onSelect,
  onFocus,
  onShowInMap,
  onAsk,
}: {
  model: StudyModel
  id: string
  onSelect: (id: string) => void
  onFocus?: (id: string) => void
  /** Open the component map around this component, with it highlighted. */
  onShowInMap?: (id: string) => void
  onAsk?: (id: string) => void
}) {
  const byId = new Map(model.components.map((c) => [c.id, c]))
  const c = byId.get(id)
  if (!c) return <Text c="dimmed">This snapshot has no component '{id}'.</Text>
  const children = model.components.filter((k) => k.parent === id)
  const outgoing = model.relations.filter((r) => r.from === id)
  const incoming = model.relations.filter((r) => r.to === id)
  const flows = model.flows.filter((f) => f.participants.includes(id))
  const handles = model.interfaces.exposes.filter((x) => x.handler === id)
  const calls = model.interfaces.calls.filter((x) => x.from === id)
  const link = (target: string) => (
    <Anchor component="button" type="button" size="sm" onClick={() => onSelect(target)}>
      {byId.get(target)?.name ?? target}
    </Anchor>
  )

  return (
    <Stack gap="sm">
      <Group gap="xs">
        <Title order={4}>{c.name}</Title>
        <Badge variant="light">{c.kind}</Badge>
        {c.tech && <Badge variant="outline">{c.tech}</Badge>}
      </Group>
      {c.parent && (
        <Text size="sm">
          Part of {link(c.parent)}
        </Text>
      )}
      {c.summary && <Text size="sm">{c.summary}</Text>}
      {c.paths?.length ? (
        <Group gap={4}>
          {c.paths.map((p) => (
            <Code key={p}>{p}</Code>
          ))}
        </Group>
      ) : null}
      <Group gap="xs">
        {onShowInMap && (
          <Button size="xs" variant="light" onClick={() => onShowInMap(id)}>
            Show in the component map
          </Button>
        )}
        {onFocus && children.length > 0 && (
          <Button size="xs" variant="light" onClick={() => onFocus(id)}>
            Show its insides
          </Button>
        )}
        {onAsk && (
          <Button size="xs" variant="default" leftSection={<IconMessagePlus size={14} />} onClick={() => onAsk(id)}>
            Ask Claude about this
          </Button>
        )}
      </Group>
      {children.length > 0 && (
        <Section title={`Contains (${children.length})`}>
          {children.map((k) => (
            <List.Item key={k.id}>
              {link(k.id)}{' '}
              <Text span size="xs" c="dimmed">
                {k.kind}
              </Text>
            </List.Item>
          ))}
        </Section>
      )}
      {outgoing.length > 0 && (
        <Section title="Uses">
          {outgoing.map((r) => (
            <List.Item key={r.id}>
              <Text span size="xs" c="dimmed">
                {r.kind}
              </Text>{' '}
              {link(r.to)}
              {r.label && <Text span size="sm">: {r.label}</Text>}
            </List.Item>
          ))}
        </Section>
      )}
      {incoming.length > 0 && (
        <Section title="Used by">
          {incoming.map((r) => (
            <List.Item key={r.id}>
              {link(r.from)}{' '}
              <Text span size="xs" c="dimmed">
                {r.kind}
              </Text>
              {r.label && <Text span size="sm">: {r.label}</Text>}
            </List.Item>
          ))}
        </Section>
      )}
      {handles.length > 0 && (
        <Section title="Handles">
          {handles.map((x) => (
            <List.Item key={x.id}>
              <Code>{[x.method, x.path ?? x.name].filter(Boolean).join(' ')}</Code>
            </List.Item>
          ))}
        </Section>
      )}
      {calls.length > 0 && (
        <Section title="Calls out">
          {calls.map((x) => (
            <List.Item key={x.id}>
              <Code>{[x.method, x.path ?? x.target_url].filter(Boolean).join(' ')}</Code>{' '}
              {x.target_project && <Text span size="sm">on {x.target_project}</Text>}
            </List.Item>
          ))}
        </Section>
      )}
      {flows.length > 0 && (
        <Section title="Takes part in">
          {flows.map((f) => (
            <List.Item key={f.id}>{f.title}</List.Item>
          ))}
        </Section>
      )}
      <Divider />
      <Cites cites={c.cites} />
    </Stack>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Stack gap={2}>
      <Text size="xs" c="dimmed" fw={500}>
        {title}
      </Text>
      <List size="sm" spacing={2}>
        {children}
      </List>
    </Stack>
  )
}
