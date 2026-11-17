import { ActionIcon, Alert, Badge, Group, Loader, Stack, Table, Text, Tooltip } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconCertificate, IconDownload, IconEye, IconTrash } from '@tabler/icons-react'
import { useState } from 'react'
import { checkReportFile, reportFileUrl, useDeleteReportFile, useReportFiles } from '../api/reports'
import { PdfPreview } from './PdfPreview'

const KB = 1024

const size = (bytes: number | undefined) =>
  bytes === undefined ? '' : bytes > KB * KB ? `${(bytes / KB / KB).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / KB))} KB`

const when = (iso: string | undefined) => (iso ? iso.replace('T', ' ').replace('Z', ' UTC') : '')

/** The PDFs built for a project, newest first (ADR 0025). They live in the private registry. */
export function ReportTab({ project }: { project: string }) {
  const files = useReportFiles(project)
  const remove = useDeleteReportFile(project)
  const [preview, setPreview] = useState<string | null>(null)

  const verify = async (file: string) => {
    try {
      const result = await checkReportFile(project, file)
      notifications.show({
        color: result.ok ? 'green' : 'orange',
        title: result.ok ? 'This report is sound' : 'This report has problems',
        message: result.ok ? `${result.pages} pages.` : result.problems.join('; '),
      })
    } catch (err) {
      notifications.show({ color: 'red', title: 'Not checked', message: err instanceof Error ? err.message : String(err) })
    }
  }

  if (files.isPending) return <Loader size="sm" />
  if (files.isError) return <Alert color="red">{files.error.message}</Alert>
  if (files.data.length === 0)
    return (
      <Text c="dimmed" size="sm">
        No reports built yet. Use <b>Report</b> at the top of this page to make one.
      </Text>
    )

  return (
    <Stack>
      <Text size="sm" c="dimmed">
        Kept in the private registry, never committed.
      </Text>
      <Table highlightOnHover withTableBorder>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Report</Table.Th>
            <Table.Th>Built</Table.Th>
            <Table.Th>Pages</Table.Th>
            <Table.Th>Size</Table.Th>
            <Table.Th />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {files.data.map((f) => (
            <Table.Tr key={f.file}>
              <Table.Td>
                <Group gap="xs">
                  <Text size="sm">{f.file}</Text>
                  {f.mode && (
                    <Badge size="xs" variant="light" color={f.mode === 'guided' ? 'grape' : 'gray'}>
                      {f.mode}
                    </Badge>
                  )}
                  {f.failed ? (
                    <Badge size="xs" color="orange">
                      {f.failed} diagram(s) failed
                    </Badge>
                  ) : null}
                </Group>
              </Table.Td>
              <Table.Td>
                <Text size="sm">{when(f.built)}</Text>
              </Table.Td>
              <Table.Td>{f.pages ?? ''}</Table.Td>
              <Table.Td>{size(f.bytes)}</Table.Td>
              <Table.Td>
                <Group gap={4} justify="flex-end" wrap="nowrap">
                  <Tooltip label="Preview">
                    <ActionIcon variant="subtle" aria-label={`Preview ${f.file}`} onClick={() => setPreview(f.file)}>
                      <IconEye size={16} />
                    </ActionIcon>
                  </Tooltip>
                  <Tooltip label="Download">
                    <ActionIcon
                      variant="subtle"
                      aria-label={`Download ${f.file}`}
                      component="a"
                      href={reportFileUrl(project, f.file)}
                      download={f.file}
                    >
                      <IconDownload size={16} />
                    </ActionIcon>
                  </Tooltip>
                  <Tooltip label="Check it against its build record">
                    <ActionIcon variant="subtle" aria-label={`Check ${f.file}`} onClick={() => verify(f.file)}>
                      <IconCertificate size={16} />
                    </ActionIcon>
                  </Tooltip>
                  <Tooltip label="Delete">
                    <ActionIcon
                      variant="subtle"
                      color="red"
                      aria-label={`Delete ${f.file}`}
                      loading={remove.isPending && remove.variables === f.file}
                      onClick={() => {
                        if (window.confirm(`Delete ${f.file}? This can't be undone.`)) remove.mutate(f.file)
                      }}
                    >
                      <IconTrash size={16} />
                    </ActionIcon>
                  </Tooltip>
                </Group>
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
      <PdfPreview project={project} file={preview} onClose={() => setPreview(null)} />
    </Stack>
  )
}
