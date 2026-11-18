import { Alert, Anchor, Badge, Button, Card, Group, Loader, SegmentedControl, Stack, Table, Text, Title } from '@mantine/core'
import { useMemo, useState, type ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router'
import { useComposedStudy } from '../api/queries'
import { normalizeModel, type ComposedMember, type StudyModel } from '../api/study'
import { SELF, type Project } from '../api/types'
import { projectUrl } from '../docs/links'
import { FeedbackForm, type FeedbackDraft } from '../feedback/FeedbackForm'
import { StartStudyButton } from './StartStudy'

export type FlatProps = {
  model: StudyModel
  params: URLSearchParams
  set: (changes: Record<string, string | null>) => void
}

function Behind({ member }: { member: ComposedMember }) {
  if (!member.has_study) return <Badge color="gray" variant="light" size="sm">no study</Badge>
  if (!member.valid) return <Badge color="orange" variant="light" size="sm">doesn&apos;t validate</Badge>
  if (member.commits_since === null) return <Text size="xs" c="dimmed">unknown</Text>
  if (member.commits_since === 0) return <Badge color="green" variant="light" size="sm">current</Badge>
  return (
    <Badge color="orange" variant="light" size="sm">
      {member.commits_since} commit{member.commits_since === 1 ? '' : 's'} behind
    </Badge>
  )
}

/**
 * A group's study (ADR 0027): its own top-level study, with the studies of its members read as they
 * are and never redone. The flattened view puts them together, and says which snapshot each part is from.
 */
export function GroupStudy({
  project,
  own,
  renderFlat,
}: {
  project: Project
  /** The group's own study, drawn as for any project. */
  own: ReactNode
  renderFlat: (props: FlatProps) => ReactNode
}) {
  const [params, setParams] = useSearchParams()
  const flat = params.get('scope') === 'flat'
  const composed = useComposedStudy(project.id)
  const [draft, setDraft] = useState<FeedbackDraft | null>(null)
  const model = useMemo(() => normalizeModel(composed.data?.model ?? undefined), [composed.data])

  const set = (changes: Record<string, string | null>) =>
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        for (const [k, v] of Object.entries(changes)) {
          if (v === null) next.delete(k)
          else next.set(k, v)
        }
        return next
      },
      { replace: true },
    )

  const data = composed.data
  const studied = data?.members.filter((m) => m.has_study).length ?? 0

  return (
    <Stack gap="sm">
      {project.needs_restudy && (
        <Alert color="orange" title="Needs a restudy">
          <Group justify="space-between" gap="xs">
            <Text size="sm">
              {project.id} was studied before it became a group. Study it again to keep a top-level study here and split
              what it found into its members.
            </Text>
            <StartStudyButton project={project.id} refresh variant="default" />
          </Group>
        </Alert>
      )}

      <Card withBorder radius="md" padding="sm">
        <Stack gap="xs">
          <Group justify="space-between">
            <Title order={5}>Members&apos; studies</Title>
            {data && (
              <Text size="xs" c="dimmed">
                {studied} of {data.members.length} studied
              </Text>
            )}
          </Group>
          {composed.isPending && <Loader size="sm" />}
          {composed.isError && <Alert color="red">{composed.error.message}</Alert>}
          {data && data.members.length === 0 && (
            <Text size="sm" c="dimmed">
              No members yet.
            </Text>
          )}
          {data && data.members.length > 0 && (
            <Table withRowBorders={false} verticalSpacing={2}>
              <Table.Tbody>
                {data.members.map((m) => (
                  <Table.Tr key={m.project}>
                    <Table.Td>
                      <Anchor component={Link} size="sm" to={`${projectUrl(m.project)}?tab=study`}>
                        {m.title}
                      </Anchor>
                    </Table.Td>
                    <Table.Td>
                      <Text size="xs" c="dimmed">
                        {m.date ? `${m.date} · ${(m.commit ?? '').slice(0, 7)}` : 'not studied'}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Behind member={m} />
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          )}
        </Stack>
      </Card>

      {data && data.overridden.some((o) => o.differs) && (
        <Alert color="yellow" title="Where the group's study and a member's differ">
          <Stack gap={6}>
            <Text size="sm">A member&apos;s own study wins, since it read that code more closely.</Text>
            {data.overridden
              .filter((o) => o.differs)
              .map((o) => (
                <Group key={o.component} justify="space-between" wrap="nowrap" align="flex-start">
                  <Text size="sm">
                    <b>{o.name}</b>: the group says &ldquo;{o.group_summary}&rdquo;, the member says &ldquo;{o.member_summary}&rdquo;.
                  </Text>
                  <Button
                    size="compact-xs"
                    variant="default"
                    onClick={() =>
                      setDraft({
                        kind: 'prompt',
                        source: SELF,
                        anchor: data.own ? { study: { project: project.id, snapshot: data.own, element: o.component, kind: 'component' } } : null,
                        body: `The group study and the study of ${o.component} describe ${o.name} differently:\n\nGroup: ${o.group_summary}\nMember: ${o.member_summary}\n\nWhich is right, and what should change?`,
                      })
                    }
                  >
                    Discuss
                  </Button>
                </Group>
              ))}
          </Stack>
        </Alert>
      )}

      <SegmentedControl
        size="xs"
        value={flat ? 'flat' : 'top'}
        onChange={(v) => set({ scope: v === 'flat' ? 'flat' : null })}
        data={[
          { value: 'top', label: 'Top level' },
          { value: 'flat', label: 'Flattened', disabled: !data?.model },
        ]}
        style={{ alignSelf: 'flex-start' }}
      />

      {flat ? (
        <Stack gap="xs">
          <Text size="xs" c="dimmed">
            Composed from the group&apos;s own study and the latest study of each member, as they are now. Flows, logic,
            states and findings stay in each member&apos;s own study.
          </Text>
          {composed.isPending && <Loader size="sm" />}
          {data && data.problems.length > 0 && <Alert color="orange">{data.problems.join('; ')}</Alert>}
          {model && renderFlat({ model, params, set })}
        </Stack>
      ) : (
        own
      )}
      <FeedbackForm draft={draft} onClose={() => setDraft(null)} />
    </Stack>
  )
}
