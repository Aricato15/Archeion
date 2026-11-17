import { Button, Group, Modal } from '@mantine/core'
import { IconDownload } from '@tabler/icons-react'
import { reportFileUrl } from '../api/reports'

/** A built report shown in the browser's own PDF viewer. */
export function PdfPreview({
  project,
  file,
  onClose,
}: {
  project: string
  file: string | null
  onClose: () => void
}) {
  return (
    <Modal opened={file !== null} onClose={onClose} title={file ?? ''} size="90%" padding="xs" keepMounted={false}>
      {file && (
        <>
          <iframe
            title={`Preview of ${file}`}
            src={reportFileUrl(project, file, true)}
            style={{ width: '100%', height: '78vh', border: '1px solid var(--mantine-color-default-border)' }}
          />
          <Group justify="flex-end" mt="xs">
            <Button
              component="a"
              href={reportFileUrl(project, file)}
              download={file}
              size="xs"
              leftSection={<IconDownload size={14} />}
            >
              Download
            </Button>
          </Group>
        </>
      )}
    </Modal>
  )
}
