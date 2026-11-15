import { SegmentedControl, Stack, Text, useComputedColorScheme } from '@mantine/core'
import { useLocalStorage } from '@mantine/hooks'
import { html } from 'diff2html'
import 'diff2html/bundles/css/diff2html.min.css'
import type { ColorSchemeType, OutputFormatType } from 'diff2html/lib/types'
import { useMemo } from 'react'

export function DiffView({ diff }: { diff: string }) {
  const scheme = useComputedColorScheme('light')
  const [format, setFormat] = useLocalStorage<'line-by-line' | 'side-by-side'>({
    key: 'archeion.diff-format',
    defaultValue: 'line-by-line',
  })
  // diff2html escapes the diff content, so its HTML is safe to inject.
  const rendered = useMemo(
    () =>
      diff.trim()
        ? html(diff, {
            drawFileList: false,
            matching: 'lines',
            outputFormat: format as OutputFormatType,
            colorScheme: scheme as ColorSchemeType,
          })
        : '',
    [diff, format, scheme],
  )
  if (!rendered) return <Text c="dimmed">No changes to this doc.</Text>
  return (
    <Stack gap="xs">
      <SegmentedControl
        size="xs"
        w="fit-content"
        value={format}
        onChange={(v) => setFormat(v as typeof format)}
        data={[
          { label: 'Inline', value: 'line-by-line' },
          { label: 'Side by side', value: 'side-by-side' },
        ]}
      />
      <div className="diff-view" dangerouslySetInnerHTML={{ __html: rendered }} />
    </Stack>
  )
}
