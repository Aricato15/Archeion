import { NavLink } from '@mantine/core'
import { IconFileText, IconFolder, IconPhoto } from '@tabler/icons-react'
import { Link, useLocation } from 'react-router'
import { SELF, type SourceId, type TreeNode } from '../api/types'
import { docUrl, rawUrl } from '../docs/links'

type ItemProps = { node: TreeNode; source: SourceId; current: string; onNavigate: () => void }

function TreeItem({ node, source, current, onNavigate }: ItemProps) {
  if (node.type === 'dir') {
    const inside = current.startsWith(`${node.path}/`)
    return (
      <NavLink
        label={node.name}
        leftSection={<IconFolder size={16} />}
        defaultOpened={inside}
        childrenOffset={14}
        py={4}
      >
        {(node.children ?? []).map((c) => (
          <TreeItem key={c.path} node={c} source={source} current={current} onNavigate={onNavigate} />
        ))}
      </NavLink>
    )
  }
  if (!node.name.toLowerCase().endsWith('.md')) {
    return (
      <NavLink
        component="a"
        href={rawUrl(source, node.path)}
        target="_blank"
        label={node.name}
        leftSection={<IconPhoto size={16} />}
        py={4}
      />
    )
  }
  return (
    <NavLink
      component={Link}
      to={docUrl(source, node.path)}
      label={node.name.replace(/\.md$/i, '')}
      leftSection={<IconFileText size={16} />}
      active={current === node.path}
      onClick={onNavigate}
      py={4}
    />
  )
}

export function DocTree({ tree, source = SELF, onNavigate }: { tree: TreeNode; source?: SourceId; onNavigate: () => void }) {
  const { pathname } = useLocation()
  let current = ''
  const prefix = source === SELF ? '/docs/' : `/p/${encodeURIComponent(source)}/`
  if (pathname.startsWith(prefix)) {
    try {
      current = decodeURIComponent(pathname.slice(prefix.length))
    } catch {
      current = ''
    }
  }
  return (
    <>
      {(tree.children ?? []).map((c) => (
        <TreeItem key={c.path} node={c} source={source} current={current} onNavigate={onNavigate} />
      ))}
    </>
  )
}
