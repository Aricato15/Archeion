import { Anchor, Badge, Card, Group, Highlight, Loader, Stack, Text, TextInput, Title } from '@mantine/core'
import { useDebouncedValue } from '@mantine/hooks'
import { IconSearch } from '@tabler/icons-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation, useSearchParams } from 'react-router'
import { useSearch } from '../api/queries'
import { SELF, type SearchHit } from '../api/types'
import { docUrl } from '../docs/links'

export function SearchPage() {
  const [params, setParams] = useSearchParams()
  const [q, setQ] = useState(params.get('q') ?? '')
  const [debounced] = useDebouncedValue(q, 250)
  const results = useSearch(debounced)

  useEffect(() => {
    if ((params.get('q') ?? '') !== debounced) setParams(debounced ? { q: debounced } : {}, { replace: true })
  }, [debounced, params, setParams])

  const grouped = useMemo(() => {
    const map = new Map<string, SearchHit[]>()
    for (const hit of results.data ?? []) map.set(`${hit.source}:${hit.path}`, [...(map.get(`${hit.source}:${hit.path}`) ?? []), hit])
    return [...map.entries()]
  }, [results.data])

  return (
    <Stack maw={900}>
      <Title order={2}>Search</Title>
      <TextInput
        leftSection={<IconSearch size={16} />}
        placeholder="Search Archeion and every project's docs (at least 2 characters)"
        value={q}
        onChange={(e) => setQ(e.currentTarget.value)}
        autoFocus
        rightSection={results.isFetching ? <Loader size="xs" /> : null}
      />
      {debounced.trim().length >= 2 && results.data?.length === 0 && <Text c="dimmed">No matches.</Text>}
      {results.data?.length === 200 && (
        <Text size="sm" c="dimmed">
          Showing the first 200 matches. Narrow the search to see more.
        </Text>
      )}
      {grouped.map(([key, hits]) => {
        const { source, path } = hits[0]
        return (
        <Card key={key} withBorder padding="sm" radius="md">
          <Group gap="xs" mb={4}>
            {source !== SELF && (
              <Badge variant="dot" color="grape" size="sm">
                {source}
              </Badge>
            )}
            <Anchor component={Link} to={docUrl(source, path)} fw={600}>
              {path}
            </Anchor>
          </Group>
          <Stack gap={2}>
            {hits.map((h) => (
              <Anchor key={h.line} component={Link} to={`${docUrl(source, path)}?line=${h.line}`} c="inherit" underline="never">
                <Text size="sm" ff="monospace">
                  <Text span c="dimmed" size="xs" mr="xs">
                    {h.line}
                  </Text>
                  <Highlight component="span" highlight={debounced} size="sm" ff="monospace">
                    {h.snippet}
                  </Highlight>
                </Text>
              </Anchor>
            ))}
          </Stack>
        </Card>
        )
      })}
    </Stack>
  )
}

/** The header search box navigates with a fresh nonce, which remounts the page with the new query. */
export function SearchRoute() {
  const state = useLocation().state as { nonce?: number } | null
  return <SearchPage key={state?.nonce ?? 'search'} />
}
