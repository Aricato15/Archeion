import { useEffect, useMemo, useRef } from 'react'
import { useParams, useSearchParams } from 'react-router'
import { useReportContent, type ReportContent, type ReportSection } from '../api/reports'
import { useRegistry } from '../api/queries'
import type { Registry } from '../api/types'
import { MarkdownView } from '../docs/MarkdownView'
import { MermaidBlock } from '../docs/MermaidBlock'
import { PrintContext, type PrintContextValue } from '../docs/PrintContext'
import './print.css'
import { diagramCode, heading, pageCss } from './sections'

/**
 * The page a report is printed from (ADR 0025): every section of a preset laid out in order,
 * always light, one section per page. The viewer's "Save as PDF" prints it, and the backend's
 * headless Edge reads `document.body.dataset.reportState` ("loading", "ready" or "error") to
 * know when every diagram has been drawn.
 */
export function PrintReport() {
  const { project = '' } = useParams()
  const [params] = useSearchParams()
  const preset = params.get('preset') ?? ''
  const content = useReportContent(project, preset)
  const registry = useRegistry()

  const pending = useRef(0)
  const failed = useRef(0)
  const tracker = useMemo<PrintContextValue>(
    () => ({
      track() {
        pending.current += 1
        return (ok) => {
          pending.current -= 1
          if (!ok) failed.current += 1
        }
      },
    }),
    [],
  )

  // The report is always light, whatever theme the viewer is in.
  useEffect(() => {
    const root = document.documentElement
    const before = root.getAttribute('data-mantine-color-scheme')
    root.setAttribute('data-mantine-color-scheme', 'light')
    return () => {
      if (before) root.setAttribute('data-mantine-color-scheme', before)
    }
  }, [])

  const loaded = content.data !== undefined && !registry.isPending
  const state = content.isError ? 'error' : loaded ? 'drawing' : 'loading'
  useEffect(() => {
    const body = document.body
    if (state === 'error') {
      body.dataset.reportState = 'error'
      body.dataset.reportError = content.error instanceof Error ? content.error.message : 'unknown error'
      return
    }
    body.dataset.reportState = 'loading'
    if (state !== 'drawing') return
    // Ready once every diagram has settled and nothing new started for two checks in a row.
    let quiet = 0
    const timer = window.setInterval(() => {
      quiet = pending.current === 0 ? quiet + 1 : 0
      if (quiet >= 2) {
        window.clearInterval(timer)
        void (document.fonts?.ready ?? Promise.resolve()).then(() => {
          body.dataset.reportFailed = String(failed.current)
          body.dataset.reportSections = String(content.data?.sections.length ?? 0)
          body.dataset.reportState = 'ready'
        })
      }
    }, 250)
    return () => {
      window.clearInterval(timer)
      delete body.dataset.reportState
    }
  }, [state, content.data, content.error])

  if (content.isError) {
    return (
      <div className="report">
        <h1>This report can't be built</h1>
        <p>{content.error instanceof Error ? content.error.message : 'Unknown error'}</p>
      </div>
    )
  }
  if (!content.data) return <div className="report">Loading the report…</div>

  const { data } = content
  return (
    <PrintContext.Provider value={tracker}>
      <style>{pageCss(data.preset.options)}</style>
      <article className="report">
        {data.preset.options.cover && <Cover data={data} />}
        {data.preset.options.toc && <Toc sections={data.sections} />}
        {data.sections.map((s, i) => (
          <section key={s.id} id={`sec-${i}`} className="report-section">
            <h2>{heading(i, s)}</h2>
            <Body section={s} data={data} registry={registry.data} />
          </section>
        ))}
      </article>
    </PrintContext.Provider>
  )
}

/** A summary is plain text in a header or a table, so its Markdown emphasis marks are dropped. */
const plain = (text: string) => text.replace(/^[_*]+|[_*]+$/g, '').replace(/`/g, '').trim()

function Cover({ data }: { data: ReportContent }) {
  const p = data.project
  const study = data.study
  return (
    <header className="report-cover">
      <h1>{data.preset.title || p.title}</h1>
      <div className="subtitle">{plain(p.summary)}</div>
      <dl>
        <dt>Project</dt>
        <dd>{p.id}</dd>
        <dt>Generated</dt>
        <dd>{data.generated}</dd>
        {study && (
          <>
            <dt>Code study</dt>
            <dd>
              {study.date}, commit {(study.commit ?? '').slice(0, 7)}
            </dd>
          </>
        )}
        <dt>Report</dt>
        <dd>{data.preset.mode === 'guided' ? 'Guided (parts written by Claude are labeled)' : 'Standard'}</dd>
      </dl>
    </header>
  )
}

function Toc({ sections }: { sections: ReportSection[] }) {
  return (
    <nav className="report-toc">
      <h2>Contents</h2>
      <ol>
        {sections.map((s, i) => (
          <li key={s.id}>
            <a href={`#sec-${i}`}>{heading(i, s)}</a>
            {s.type === 'authored' && <span className="group">written by Claude</span>}
          </li>
        ))}
      </ol>
    </nav>
  )
}

function Body({ section, data, registry }: { section: ReportSection; data: ReportContent; registry?: Registry }) {
  switch (section.type) {
    case 'facts':
      return <Facts project={data.project} />
    case 'markdown':
      return section.markdown.trim() ? (
        <MarkdownView
          content={section.markdown}
          docPath={section.path ?? 'README.md'}
          source={data.project.id}
          compact
        />
      ) : (
        <p>Nothing written.</p>
      )
    case 'authored':
      return (
        <>
          <div className="written-by">Written by Claude</div>
          <MarkdownView content={section.markdown} docPath="README.md" compact />
          <div className="sources">Sources: {section.cites.map((c) => c.title).join('; ')}</div>
        </>
      )
    case 'diagram': {
      const code = diagramCode(section, data.study, registry)
      return code ? (
        <MermaidBlock code={code} />
      ) : (
        <p className="failed">This diagram's source is no longer in the study, so it can't be drawn.</p>
      )
    }
    case 'interfaces':
      return (
        <>
          <h3>Exposes</h3>
          <Table
            head={['Kind', 'Entry', 'Summary']}
            rows={section.exposes.map((e) => [e.kind, [e.method, e.path ?? e.name].filter(Boolean).join(' '), e.summary ?? ''])}
          />
          <h3>Calls</h3>
          <Table
            head={['Kind', 'Target', 'Summary']}
            rows={section.calls.map((c) => [
              c.kind,
              [c.target_project ?? c.target_url, c.port, c.method, c.path].filter(Boolean).join(' '),
              c.summary ?? '',
            ])}
          />
        </>
      )
    case 'findings':
      return (
        <Table
          head={['Severity', 'Finding', 'Detail']}
          rows={section.items.map((f) => [f.severity, f.title, f.detail ?? ''])}
        />
      )
    case 'glossary':
      return (
        <Table
          head={['Term', 'Also called', 'Definition']}
          rows={section.terms.map((t) => [t.term, t.aliases.join(', '), t.definition])}
        />
      )
    case 'dependencies':
      return (
        <Table
          head={['Direction', 'Projects']}
          rows={[
            ['Depends on', section.depends_on.join(', ') || 'none'],
            ['Used by', section.used_by.join(', ') || 'none'],
          ]}
        />
      )
  }
}

function Facts({ project: p }: { project: ReportContent['project'] }) {
  return (
    <>
      {p.summary && <p>{plain(p.summary)}</p>}
      <Table
        head={['Fact', 'Value']}
        rows={[
          ['Name', p.id],
          ['Type', p.type],
          ['Kind', p.kind ?? ''],
          ['Status', p.status],
          ['Group', p.group ?? ''],
          ['Ports', p.ports.join(', ')],
          ['Depends on', p.depends_on.join(', ')],
          ['Used by', p.used_by.join(', ')],
          ['Registry facts checked', p.verified ?? ''],
        ].filter(([, v]) => v !== '')}
      />
    </>
  )
}

function Table({ head, rows }: { head: string[]; rows: (string | number)[][] }) {
  if (rows.length === 0) return <p>None recorded.</p>
  return (
    <table>
      <thead>
        <tr>
          {head.map((h) => (
            <th key={h}>{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i}>
            {r.map((c, j) => (
              <td key={j}>{c}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}
