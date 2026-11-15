import { ActionIcon, Anchor, Button, Text, Tooltip, Typography } from '@mantine/core'
import { IconMessagePlus } from '@tabler/icons-react'
import type { Element as HastElement, ElementContent } from 'hast'
import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import Markdown, { type Components } from 'react-markdown'
import { Link } from 'react-router'
import rehypeSlug from 'rehype-slug'
import remarkGfm from 'remark-gfm'
import type { Anchor as FeedbackAnchor } from '../api/types'
import { anchorForBlock, anchorForSelection, blockForLine, blockOf } from './anchors'
import { imageSrc, resolveLink } from './links'
import { MermaidBlock } from './MermaidBlock'
import { rehypeLines } from './rehypeLines'

export type Heading = { id: string; text: string; level: number }
export type Flash = { line: number; key: number }

type Props = {
  content: string
  docPath: string
  compact?: boolean
  /** When set, blocks and selections get a "comment" button. */
  onComment?: (anchor: FeedbackAnchor) => void
  onHeadings?: (headings: Heading[]) => void
  flash?: Flash | null
}

function hastText(node: ElementContent | HastElement): string {
  if (node.type === 'text') return node.value
  if (node.type === 'element') return node.children.map(hastText).join('')
  return ''
}

function buildComponents(docPath: string): Components {
  return {
    a({ href = '', children, node: _node, ...rest }) {
      const link = resolveLink(docPath, href)
      switch (link.kind) {
        case 'doc':
          return (
            <Anchor component={Link} to={link.to}>
              {children}
            </Anchor>
          )
        case 'anchor':
          return <Anchor href={link.hash}>{children}</Anchor>
        case 'external':
        case 'file':
          return (
            <Anchor href={link.href} target="_blank" rel="noreferrer noopener" {...rest}>
              {children}
            </Anchor>
          )
        case 'outside':
          return (
            <Tooltip label={`${href} is outside docs/, so the viewer doesn't serve it`}>
              <Text component="span" inherit td="underline dotted">
                {children}
              </Text>
            </Tooltip>
          )
      }
    },
    img({ src, alt }) {
      const resolved = typeof src === 'string' ? imageSrc(docPath, src) : null
      if (!resolved) return <span>[{alt || 'image'}]</span>
      return <img src={resolved} alt={alt ?? ''} style={{ maxWidth: '100%' }} />
    },
    pre({ node, children }) {
      const code = node?.children.find((c): c is HastElement => c.type === 'element' && c.tagName === 'code')
      const classes = code?.properties?.className
      const lang = Array.isArray(classes) ? classes.map(String).find((c) => c.startsWith('language-')) : undefined
      if (code && lang === 'language-mermaid') return <MermaidBlock code={hastText(code).replace(/\n$/, '')} />
      return <pre>{children}</pre>
    },
  }
}

export function MarkdownView({ content, docPath, compact, onComment, onHeadings, flash }: Props) {
  const wrapperRef = useRef<HTMLDivElement>(null)
  const contentRef = useRef<HTMLDivElement>(null)
  const [hover, setHover] = useState<{ top: number; block: HTMLElement } | null>(null)
  const [selection, setSelection] = useState<{ top: number; left: number; anchor: FeedbackAnchor } | null>(
    null,
  )

  useLayoutEffect(() => {
    if (!onHeadings || !contentRef.current) return
    const found = Array.from(contentRef.current.querySelectorAll<HTMLElement>('h1, h2, h3, h4'))
      .filter((h) => h.id)
      .map((h) => ({ id: h.id, text: h.textContent ?? '', level: Number(h.tagName[1]) }))
    onHeadings(found)
  }, [content, onHeadings])

  useEffect(() => {
    if (!flash || !contentRef.current) return
    const block = blockForLine(contentRef.current, flash.line)
    if (!block) return
    block.scrollIntoView({ block: 'center', behavior: 'smooth' })
    block.classList.remove('block-flash')
    void block.offsetWidth // restart the animation
    block.classList.add('block-flash')
    const timer = window.setTimeout(() => block.classList.remove('block-flash'), 2600)
    return () => window.clearTimeout(timer)
  }, [flash])

  const offsetTop = (el: Element) =>
    el.getBoundingClientRect().top - (wrapperRef.current?.getBoundingClientRect().top ?? 0)

  const onMouseMove = (e: React.MouseEvent) => {
    if (!onComment || !contentRef.current) return
    const block = blockOf(contentRef.current, e.target as Node)
    if (block && block !== hover?.block) setHover({ block, top: offsetTop(block) })
  }

  const onMouseUp = () => {
    if (!onComment || !contentRef.current || !wrapperRef.current) return
    // Let the browser finish updating the selection first.
    window.setTimeout(() => {
      if (!contentRef.current || !wrapperRef.current) return
      const sel = window.getSelection()
      const anchor = anchorForSelection(contentRef.current, sel)
      if (!anchor || !sel) {
        setSelection(null)
        return
      }
      const rect = sel.getRangeAt(0).getBoundingClientRect()
      const box = wrapperRef.current.getBoundingClientRect()
      setSelection({ anchor, top: rect.bottom - box.top + 6, left: Math.max(0, rect.left - box.left) })
    }, 0)
  }

  const comment = (anchor: FeedbackAnchor) => {
    setSelection(null)
    window.getSelection()?.removeAllRanges()
    onComment?.(anchor)
  }

  return (
    <div
      ref={wrapperRef}
      className={compact ? 'markdown-body markdown-compact' : 'markdown-body'}
      onMouseMove={onMouseMove}
      onMouseLeave={() => setHover(null)}
      onMouseUp={onMouseUp}
    >
      {onComment && hover && (
        <Tooltip label="Comment on this block" position="left">
          <ActionIcon
            variant="subtle"
            size="sm"
            aria-label="Comment on this block"
            style={{ position: 'absolute', left: 4, top: hover.top + 2 }}
            onClick={() => comment(anchorForBlock(hover.block))}
          >
            <IconMessagePlus size={16} />
          </ActionIcon>
        </Tooltip>
      )}
      {onComment && selection && (
        <Button
          size="compact-xs"
          leftSection={<IconMessagePlus size={14} />}
          style={{ position: 'absolute', top: selection.top, left: selection.left + 40, zIndex: 5 }}
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => comment(selection.anchor)}
        >
          Comment on selection
        </Button>
      )}
      <Typography ref={contentRef}>
        <Markdown
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[rehypeSlug, rehypeLines]}
          components={buildComponents(docPath)}
        >
          {content}
        </Markdown>
      </Typography>
    </div>
  )
}

