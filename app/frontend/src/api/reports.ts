/** Project PDF reports (ADR 0025): the section catalog, presets and the content a report is drawn from. */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
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

export type ReportPreflight = {
  project: string
  browser: boolean
  /** Whether the viewer's frontend answers (the PDF is printed from it); null when not checked. */
  frontend: boolean | null
  study: string | null
  sections: number
  available: number
  unavailable: { id: string; reason: string }[]
  problems: string[]
  ok: boolean
}

export type BuiltReport = {
  file: string
  preset: string
  mode: 'standard' | 'guided'
  title: string
  built: string
  sections: number
  options: ReportOptions
  study: string | null
  pages: number
  failed: number
  bytes?: number
}

export type BuildJob = {
  id: string
  project: string
  preset: string
  status: 'running' | 'done' | 'error'
  result?: BuiltReport
  error?: string
}

export type ReportCheck = { file: string; pages: number; bytes: number; problems: string[]; ok: boolean }

const enc = encodeURIComponent

export const reportFileUrl = (project: string, file: string, inline = false) =>
  `/api/reports/${enc(project)}/files/${enc(file)}${inline ? '?inline=true' : ''}`

export const useReportPreflight = (project: string, enabled = true) =>
  useQuery({
    queryKey: ['report-preflight', project],
    queryFn: () => api<ReportPreflight>(`/reports/${enc(project)}/preflight`),
    enabled,
    staleTime: 0,
  })

export const useReportPresets = (project: string) =>
  useQuery({
    queryKey: ['report-presets', project],
    queryFn: () => api<ReportPreset[]>(`/reports/${enc(project)}/presets`),
  })

export function useSaveReportPreset(project: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (preset: ReportPreset) =>
      api<ReportPreset>(`/reports/${enc(project)}/presets`, { method: 'PUT', json: preset }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['report-presets', project] }),
  })
}

export function useDeleteReportPreset(project: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (name: string) =>
      api<void>(`/reports/${enc(project)}/presets/${enc(name)}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['report-presets', project] }),
  })
}

/** Starts building a saved preset; the job it returns is followed with `useBuildJob`. */
export const useStartBuild = (project: string) =>
  useMutation({
    mutationFn: (preset: string) =>
      api<BuildJob>(`/reports/${enc(project)}/presets/${enc(preset)}/build`, { method: 'POST' }),
  })

/** Follows a build until it finishes. */
export const useBuildJob = (project: string, job: string | null) =>
  useQuery({
    queryKey: ['report-build', project, job],
    queryFn: () => api<BuildJob>(`/reports/${enc(project)}/builds/${job}`),
    enabled: job !== null,
    refetchInterval: (q) => (q.state.data && q.state.data.status !== 'running' ? false : 1000),
    gcTime: 0,
  })

export const useReportFiles = (project: string) =>
  useQuery({
    queryKey: ['report-files', project],
    queryFn: () => api<BuiltReport[]>(`/reports/${enc(project)}/files`),
  })

export function useDeleteReportFile(project: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (file: string) => api<void>(reportFileUrl(project, file).replace(/^\/api/, ''), { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['report-files', project] }),
  })
}

export const checkReportFile = (project: string, file: string) =>
  api<ReportCheck>(`/reports/${enc(project)}/files/${enc(file)}/verify`)

/** The guided report in progress (ADR 0025): the plan Claude drafted, and the thread it belongs to. */
export type ReportPlan = { plan: ReportPreset; thread: number | null; updated: string }

export const useReportPlan = (project: string, poll = true) =>
  useQuery({
    queryKey: ['report-plan', project],
    queryFn: () => api<ReportPlan | null>(`/reports/${enc(project)}/plan`),
    // Claude saves the plan from another process, so look again now and then.
    refetchInterval: poll ? 3000 : false,
  })

/** The reader's edits to the plan: reordering and dropping sections. The thread is kept. */
export function useSaveReportPlan(project: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (plan: ReportPreset) =>
      api<ReportPlan>(`/reports/${enc(project)}/plan`, { method: 'PUT', json: plan }),
    onSuccess: (saved) => qc.setQueryData(['report-plan', project], saved),
  })
}

export function useDiscardReportPlan(project: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api<void>(`/reports/${enc(project)}/plan`, { method: 'DELETE' }),
    onSuccess: () => qc.setQueryData(['report-plan', project], null),
  })
}

/** Approves the plan (it becomes a saved preset) and starts building it. */
export function useApproveReportPlan(project: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api<BuildJob>(`/reports/${enc(project)}/plan/approve`, { method: 'POST' }),
    onSuccess: () => {
      qc.setQueryData(['report-plan', project], null)
      qc.invalidateQueries({ queryKey: ['report-presets', project] })
    },
  })
}

/** Follows a build until it finishes, and tells the Reports tab when a new PDF exists. */
export function useFollowBuild(project: string, jobId: string | null) {
  const qc = useQueryClient()
  const job = useBuildJob(project, jobId)
  const status = job.data?.status
  useEffect(() => {
    if (status === 'done') qc.invalidateQueries({ queryKey: ['report-files', project] })
  }, [status, qc, project])
  return job.data
}
