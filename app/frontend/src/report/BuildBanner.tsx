import { Alert, Button, Group, Text } from '@mantine/core'
import { IconDownload, IconEye } from '@tabler/icons-react'
import { reportFileUrl, type useFollowBuild } from '../api/reports'

/** What a build came to: the PDF to open or download, or why there isn't one. */
export function BuildBanner({ project, job }: { project: string; job: ReturnType<typeof useFollowBuild> }) {
  if (job?.status === 'error')
    return (
      <Alert color="red" title="The report wasn't built">
        {job.error}
      </Alert>
    )
  if (job?.status !== 'done' || !job.result) return null
  const r = job.result
  return (
    <Alert color={r.failed ? 'orange' : 'green'} title="Report built">
      <Group justify="space-between">
        <Text size="sm">
          {r.file}: {r.pages} pages, {r.sections} sections
          {r.failed ? `, ${r.failed} diagram(s) failed to draw` : ''}.
        </Text>
        <Group gap="xs">
          <Button
            size="xs"
            component="a"
            href={reportFileUrl(project, r.file, true)}
            target="_blank"
            rel="noopener noreferrer"
            leftSection={<IconEye size={14} />}
          >
            Open
          </Button>
          <Button
            size="xs"
            variant="default"
            component="a"
            href={reportFileUrl(project, r.file)}
            download={r.file}
            leftSection={<IconDownload size={14} />}
          >
            Download
          </Button>
        </Group>
      </Group>
    </Alert>
  )
}
