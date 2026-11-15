import { Alert, Code, Loader, Stack, Text, useComputedColorScheme } from '@mantine/core'
import { useEffect, useId, useState } from 'react'

type State = { svg: string; error: null } | { svg: null; error: string } | { svg: null; error: null }

type Mermaid = (typeof import('mermaid'))['default']
let loading: Promise<Mermaid> | null = null

/**
 * Loads mermaid once, with the ELK layout (`layout: elk` in a diagram's frontmatter) and icon
 * packs for architecture diagrams (`logos:` for products, `mdi:` for generic icons). Each extra
 * is fetched only when a diagram first asks for it.
 */
function loadMermaid(): Promise<Mermaid> {
  loading ??= Promise.all([import('mermaid'), import('@mermaid-js/layout-elk')])
    .then(([{ default: mermaid }, { default: elkLayouts }]) => {
      // A tiny module: the ELK engine itself is another chunk, loaded by the first ELK diagram.
      mermaid.registerLayoutLoaders(elkLayouts)
      mermaid.registerIconPacks([
        { name: 'logos', loader: () => import('@iconify-json/logos').then((m) => m.icons) },
        { name: 'mdi', loader: () => import('@iconify-json/mdi').then((m) => m.icons) },
      ])
      return mermaid
    })
    .catch((err: unknown) => {
      loading = null
      throw err
    })
  return loading
}

/** Renders a Mermaid diagram. mermaid is loaded only when the first diagram appears. */
export function MermaidBlock({ code }: { code: string }) {
  const scheme = useComputedColorScheme('light')
  const reactId = useId()
  const [state, setState] = useState<State>({ svg: null, error: null })

  useEffect(() => {
    let cancelled = false
    const id = `mermaid-${reactId.replace(/[^a-zA-Z0-9]/g, '')}`
    loadMermaid()
      .then(async (mermaid) => {
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: 'strict',
          theme: scheme === 'dark' ? 'dark' : 'default',
        })
        await mermaid.parse(code)
        const { svg } = await mermaid.render(id, code)
        if (!cancelled) setState({ svg, error: null })
      })
      .catch((err: unknown) => {
        // mermaid leaves its scratch element behind when rendering fails.
        document.getElementById(`d${id}`)?.remove()
        document.getElementById(id)?.remove()
        if (!cancelled) setState({ svg: null, error: err instanceof Error ? err.message : String(err) })
      })
    return () => {
      cancelled = true
    }
  }, [code, scheme, reactId])

  if (state.error !== null) {
    return (
      <Alert color="red" variant="light" title="This diagram has an error" my="md">
        <Stack gap="xs">
          <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
            {state.error}
          </Text>
          <Code block>{code}</Code>
        </Stack>
      </Alert>
    )
  }
  if (state.svg === null) return <Loader size="sm" my="md" aria-label="Rendering diagram" />
  return <div className="mermaid-block" role="img" dangerouslySetInnerHTML={{ __html: state.svg }} />
}
