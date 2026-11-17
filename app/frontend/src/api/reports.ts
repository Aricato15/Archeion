/** Project PDF reports (ADR 0025): the section catalog, presets and the content a report is drawn from. */

import { useQuery } from '@tanstack/react-query'
import { api } from './client'
import type { Exposed, Finding, Outgoing, StudyModel } from './study'
import type { Project } from './types'

export type CatalogEntry = {
  id: string
  group: 'overview' | 'docs' | 'study' | 'design' | 'glossary' | 'system'
  title: string
  kind: 'text' | 'diagram'
  available: boolean
  /** Why it has no source, when it hasn't. */
  reason: string | null
  /** A sub-system diagram's parent entry (the compact map). */
  parent: string | null
}

export type ReportOptions = {
  page_size: 'A4' | 'Letter'
  orientation: 'portrait' | 'landscape'
  cover: boolean
  toc: boolean
}

/** A section of a preset: a catalog entry, or text Claude wrote (guided reports only). */
export type PresetSection = { id: string } | { id: string; title: string; body: string; cites: string[] }

export type ReportPreset = {
  name: string
  mode: 'standard' | 'guided'
  title: string
  options: ReportOptions
  sections: PresetSection[]
  prompt?: string
  outline?: string
}

export type DiagramKind = 'map' | 'flow' | 'activity' | 'state' | 'schema' | 'group'

export type SectionBody =
  | { type: 'facts' }
  | { type: 'markdown'; markdown: string; path?: string }
  | { type: 'diagram'; diagram: DiagramKind; focus?: string | null; ref?: string; group?: string | null }
  | { type: 'interfaces'; exposes: Exposed[]; calls: Outgoing[] }
  | { type: 'findings'; items: Finding[] }
  | { type: 'glossary'; terms: { id: string; term: string; aliases: string[]; definition: string }[] }
  | { type: 'dependencies'; depends_on: string[]; used_by: string[] }
  | { type: 'authored'; markdown: string; cites: { id: string; title: string }[] }

export type ReportSection = { id: string; title: string } & SectionBody

export type ReportContent = {
  project: Project
  preset: ReportPreset
  /** The day the content was resolved (ISO date). */
  generated: string
  study: { id: string; date: string | null; commit: string | null; model: StudyModel } | null
  sections: ReportSection[]
}

export const useReportCatalog = (project: string) =>
  useQuery({ queryKey: ['report-catalog', project], queryFn: () => api<CatalogEntry[]>(`/reports/${project}/catalog`) })

export const useReportContent = (project: string, preset: string) =>
  useQuery({
    queryKey: ['report-content', project, preset],
    queryFn: () => api<ReportContent>(`/reports/${project}/presets/${preset}/content`),
    retry: false,
    staleTime: 0,
    gcTime: 0,
    refetchOnWindowFocus: false,
  })
