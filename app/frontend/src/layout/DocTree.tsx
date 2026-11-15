import { NavLink } from '@mantine/core'
import { IconFileText, IconFolder, IconPhoto } from '@tabler/icons-react'
import { Link, useLocation } from 'react-router'
import type { TreeNode } from '../api/types'
import { docUrl, rawUrl } from '../docs/links'

function TreeItem({ node, current, onNavigate }: { node: TreeNode; current: string; onNavigate: () => void }) {
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
          <TreeItem key={c.path} node={c} current={current} onNavigate={onNavigate} />
        ))}
      </NavLink>
    )
  }
  if (!node.name.toLowerCase().endsWith('.md')) {
    return (
      <NavLink
        component="a"
        href={rawUrl(node.path)}
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
      to={docUrl(node.path)}
      label={node.name.replace(/\.md$/i, '')}
      leftSection={<IconFileText size={16} />}
      active={current === node.path}
      onClick={onNavigate}
      py={4}
    />
  )
}

export function DocTree({ tree, onNavigate }: { tree: TreeNode; onNavigate: () => void }) {
  const { pathname } = useLocation()
  let current = ''
  if (pathname.startsWith('/docs/')) {
    try {
      current = decodeURIComponent(pathname.slice('/docs/'.length))
    } catch {
      current = ''
    }
  }
  return (
    <>
      {(tree.children ?? []).map((c) => (
        <TreeItem key={c.path} node={c} current={current} onNavigate={onNavigate} />
      ))}
    </>
  )
}
