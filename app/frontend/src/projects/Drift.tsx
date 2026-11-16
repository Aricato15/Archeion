import { Alert, Anchor, List, Text } from '@mantine/core'
import { IconArrowsDiff } from '@tabler/icons-react'
import { Link } from 'react-router'
import { useSystemLinks } from '../api/queries'

const projectLink = (id: string) => (
  <Anchor key={id} component={Link} to={`/projects/${encodeURIComponent(id)}`} size="sm">
    {id}
  </Anchor>
)

const join = (ids: string[]) =>
  ids.flatMap((id, i) => (i === 0 ? [projectLink(id)] : [<span key={`s${id}`}>, </span>, projectLink(id)]))

/**
 * Where a studied project's code and its registry page disagree (ADR 0019): calls to projects
 * that `depends_on` doesn't list, and `depends_on` entries the code never calls. Shown for one
 * project, or for all of them when `project` is left out.
 */
export function DriftAlert({ project }: { project?: string }) {
  const links = useSystemLinks()
  const drift = (links.data?.drift ?? []).filter((d) => !project || d.project === project)
  if (drift.length === 0) return null
  const line = (d: (typeof drift)[number]) => (
    <>
      {d.code_only.length > 0 && (
        <Text span size="sm">
          calls {join(d.code_only)}, which <code>depends_on</code> doesn't list.{' '}
        </Text>
      )}
      {d.registry_only.length > 0 && (
        <Text span size="sm">
          <code>depends_on</code> lists {join(d.registry_only)}, which the code never calls.
        </Text>
      )}
    </>
  )
  return (
    <Alert color="orange" icon={<IconArrowsDiff size={18} />} title="The code and the registry disagree">
      {project ? (
        <Text size="sm">
          According to its latest study, {project} {line(drift[0])} Fix the registry page, or study it again if the
          study is old.
        </Text>
      ) : (
        <List size="sm">
          {drift.map((d) => (
            <List.Item key={d.project}>
              {projectLink(d.project)} {line(d)}
            </List.Item>
          ))}
        </List>
      )}
    </Alert>
  )
}
