import {
  Alert,
  Badge,
  Button,
  Checkbox,
  Grid,
  Group,
  Loader,
  Modal,
  ScrollArea,
  Select,
  Stack,
  Switch,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useQueryClient } from '@tanstack/react-query'
import { notifications } from '@mantine/notifications'
import { IconDownload, IconEye, IconFileTypePdf } from '@tabler/icons-react'
import { useEffect, useMemo, useState } from 'react'
import {
  reportFileUrl,
  useBuildJob,
  useDeleteReportPreset,
  useReportCatalog,
  useReportPreflight,
  useReportPresets,
  useSaveReportPreset,
  useStartBuild,
  type ReportOptions,
} from '../api/reports'
import {
  DEFAULT_OPTIONS,
  GROUP_TITLES,
  NAME_PATTERN,
  defaultSelection,
  fromPreset,
  groupEntries,
  groupState,
  slugName,
  toPreset,
  toggle,
  toggleGroup,
} from './config'
import { PdfPreview } from './PdfPreview'
import { SortableSections } from './SortableSections'

/** The standard report (ADR 0025): choose and order sections, set the page, generate a PDF. No Claude. */
export function ReportDialog({ project, opened, onClose }: { project: string; opened: boolean; onClose: () => void }) {
  return (
    <Modal opened={opened} onClose={onClose} title="Standard report" size="xl" keepMounted={false}>
      <StandardReport project={project} />
    </Modal>
  )
}

function StandardReport({ project }: { project: string }) {
  const qc = useQueryClient()
  const catalog = useReportCatalog(project)
  const presets = useReportPresets(project)
  const preflight = useReportPreflight(project)
  const savePreset = useSaveReportPreset(project)
  const deletePreset = useDeleteReportPreset(project)
  const start = useStartBuild(project)

  const entries = useMemo(() => catalog.data ?? [], [catalog.data])
  const byId = useMemo(() => new Map(entries.map((e) => [e.id, e])), [entries])

  // Until the reader changes something, the report is every section that has a source.
  const [chosen, setChosen] = useState<string[] | null>(null)
  const selection = chosen ?? defaultSelection(entries)
  const [options, setOptions] = useState<ReportOptions>(DEFAULT_OPTIONS)
  const [title, setTitle] = useState('')
  const [nameText, setNameText] = useState('full')
  const name = slugName(nameText)

  const [jobId, setJobId] = useState<string | null>(null)
  const job = useBuildJob(project, jobId)
  const status = job.data?.status
  useEffect(() => {
    if (status === 'done') qc.invalidateQueries({ queryKey: ['report-files', project] })
  }, [status, qc, project])
  const [preview, setPreview] = useState<string | null>(null)

  const busy = start.isPending || savePreset.isPending || status === 'running'
  const canGenerate = selection.length > 0 && NAME_PATTERN.test(name) && !busy && preflight.data?.ok !== false

  const loadPreset = (presetName: string | null) => {
    const found = presets.data?.find((p) => p.name === presetName)
    if (!found) return
    const { selection: next, dropped } = fromPreset(found, entries)
    setChosen(next)
    setOptions({ ...DEFAULT_OPTIONS, ...found.options })
    setTitle(found.title)
    setNameText(found.name)
    if (dropped.length > 0)
      notifications.show({
        color: 'orange',
        title: 'Some sections are gone',
        message: `${dropped.length} section(s) of this preset no longer have a source and were left out.`,
      })
  }

  const current = () => toPreset({ name, title, options, selection })
  const save = () =>
    savePreset.mutate(current(), {
      onSuccess: () => notifications.show({ color: 'green', title: 'Preset saved', message: name }),
      onError: (err) => notifications.show({ color: 'red', title: 'Not saved', message: err.message }),
    })
  const generate = async () => {
    try {
      await savePreset.mutateAsync(current())
      const started = await start.mutateAsync(name)
      setJobId(started.id)
    } catch (err) {
      notifications.show({
        color: 'red',
        title: 'Could not start the report',
        message: err instanceof Error ? err.message : String(err),
      })
    }
  }

  if (catalog.isPending) return <Loader size="sm" />
  if (catalog.isError) return <Alert color="red">{catalog.error.message}</Alert>

  return (
    <Stack>
      <Text size="sm" c="dimmed">
        The same choices always give the same PDF. Nothing here asks Claude to write anything.
      </Text>

      {preflight.data && preflight.data.problems.length > 0 && (
        <Alert color="orange" title="A report can't be built yet">
          {preflight.data.problems.map((p) => (
            <Text key={p} size="sm">
              {p}
            </Text>
          ))}
        </Alert>
      )}

      <Grid gap="md">
        <Grid.Col span={{ base: 12, md: 6 }}>
          <Title order={5} mb="xs">
            Sections
          </Title>
          <ScrollArea h={380} type="auto" offsetScrollbars>
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
                      onChange={(e) => setChosen(toggleGroup(selection, entries, group, e.currentTarget.checked))}
                    />
                    {items.map((entry) => (
                      <Group key={entry.id} gap="xs" ml={entry.parent ? 56 : 28} wrap="nowrap">
                        <Checkbox
                          size="xs"
                          label={entry.title}
                          checked={selection.includes(entry.id)}
                          disabled={!entry.available}
                          onChange={() => setChosen(toggle(selection, entry, entries))}
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
        </Grid.Col>

        <Grid.Col span={{ base: 12, md: 6 }}>
          <Group justify="space-between" mb="xs">
            <Title order={5}>Order</Title>
            <Badge variant="light">{selection.length} sections</Badge>
          </Group>
          <ScrollArea h={380} type="auto" offsetScrollbars>
            {selection.length === 0 ? (
              <Text size="sm" c="dimmed">
                Tick a section on the left to add it.
              </Text>
            ) : (
              <SortableSections selection={selection} byId={byId} onChange={setChosen} />
            )}
          </ScrollArea>
        </Grid.Col>
      </Grid>

      <Grid gap="sm" align="end">
        <Grid.Col span={{ base: 12, sm: 6 }}>
          <TextInput
            label="Report title"
            description="Leave empty to use the project's name."
            value={title}
            maxLength={200}
            onChange={(e) => setTitle(e.currentTarget.value)}
          />
        </Grid.Col>
        <Grid.Col span={{ base: 6, sm: 3 }}>
          <Select
            label="Page size"
            data={['A4', 'Letter']}
            allowDeselect={false}
            value={options.page_size}
            onChange={(v) => v && setOptions({ ...options, page_size: v as ReportOptions['page_size'] })}
          />
        </Grid.Col>
        <Grid.Col span={{ base: 6, sm: 3 }}>
          <Select
            label="Orientation"
            data={[
              { value: 'portrait', label: 'Portrait' },
              { value: 'landscape', label: 'Landscape' },
            ]}
            allowDeselect={false}
            value={options.orientation}
            onChange={(v) => v && setOptions({ ...options, orientation: v as ReportOptions['orientation'] })}
          />
        </Grid.Col>
      </Grid>
      <Group>
        <Switch
          label="Cover page"
          checked={options.cover}
          onChange={(e) => setOptions({ ...options, cover: e.currentTarget.checked })}
        />
        <Switch
          label="Contents"
          checked={options.toc}
          onChange={(e) => setOptions({ ...options, toc: e.currentTarget.checked })}
        />
        <Text size="xs" c="dimmed">
          Wide diagrams always get a landscape page, so they stay readable.
        </Text>
      </Group>

      <Group align="end" gap="xs">
        <Select
          label="Saved presets"
          placeholder={presets.data?.length ? 'Load one' : 'None yet'}
          data={(presets.data ?? []).map((p) => ({ value: p.name, label: p.name }))}
          value={null}
          onChange={loadPreset}
          disabled={!presets.data?.length}
          w={180}
        />
        <TextInput
          label="Preset name"
          value={nameText}
          onChange={(e) => setNameText(e.currentTarget.value)}
          error={name === '' ? 'Needs a letter or digit' : undefined}
          w={180}
        />
        <Button variant="default" onClick={save} disabled={!NAME_PATTERN.test(name) || selection.length === 0} loading={savePreset.isPending}>
          Save preset
        </Button>
        <Button
          variant="subtle"
          color="red"
          disabled={!presets.data?.some((p) => p.name === name)}
          loading={deletePreset.isPending}
          onClick={() => deletePreset.mutate(name)}
        >
          Delete preset
        </Button>
      </Group>

      {status === 'error' && (
        <Alert color="red" title="The report wasn't built">
          {job.data?.error}
        </Alert>
      )}
      {status === 'done' && job.data?.result && (
        <Alert color={job.data.result.failed ? 'orange' : 'green'} title="Report built">
          <Group justify="space-between">
            <Text size="sm">
              {job.data.result.file}: {job.data.result.pages} pages, {job.data.result.sections} sections
              {job.data.result.failed ? `, ${job.data.result.failed} diagram(s) failed to draw` : ''}.
            </Text>
            <Group gap="xs">
              <Button size="xs" leftSection={<IconEye size={14} />} onClick={() => setPreview(job.data!.result!.file)}>
                Preview
              </Button>
              <Button
                size="xs"
                variant="default"
                component="a"
                href={reportFileUrl(project, job.data.result.file)}
                download={job.data.result.file}
                leftSection={<IconDownload size={14} />}
              >
                Download
              </Button>
            </Group>
          </Group>
        </Alert>
      )}

      <Group justify="flex-end">
        <Button leftSection={<IconFileTypePdf size={16} />} onClick={generate} disabled={!canGenerate} loading={busy}>
          {status === 'running' ? 'Building the PDF…' : 'Generate PDF'}
        </Button>
      </Group>

      <PdfPreview project={project} file={preview} onClose={() => setPreview(null)} />
    </Stack>
  )
}
