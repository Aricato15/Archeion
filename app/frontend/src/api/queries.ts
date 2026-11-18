import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, isUnauthorized, qs } from './client'
import type {
  RemovedProject,
  Commit,
  Diagram,
  DiffResult,
  DocAt,
  DocFile,
  FeedbackItem,
  FeedbackKind,
  FeedbackStatus,
  FeedbackSummary,
  FeedbackThread,
  NewFeedback,
  Project,
  ProjectType,
  Registry,
  ResponderStatus,
  RootSurvey,
  RootsSettings,
  RunnerStatus,
  Roadmaps,
  SearchHit,
  Source,
  SourceId,
  TreeNode,
} from './types'
import type { Approval, BuiltVsDesigned, DesignFull, DesignRow, Impact, Preflight } from './design'
import type { SnapshotFull, SnapshotRow, StudyDiff, StudyHit, SystemLinks } from './study'

// --- session ---------------------------------------------------------------------------

export function useSession() {
  return useQuery({
    queryKey: ['session'],
    queryFn: async () => {
      try {
        return await api<{ expires_at: string }>('/auth/session')
      } catch (error) {
        if (isUnauthorized(error)) return null
        throw error
      }
    },
    staleTime: 60_000,
    retry: false,
  })
}

export function useLogin() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (secret: string) => api<void>('/auth/login', { method: 'POST', json: { password: secret } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['session'] }),
  })
}

/** Whether the admin password still has to be created: a fresh start (ADR 0011). */
export const useSetupStatus = () =>
  useQuery({
    queryKey: ['setup'],
    queryFn: () => api<{ needed: boolean; allowed: boolean; min_length: number }>('/auth/setup'),
    retry: false,
  })

export function useSetup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (secret: string) => api<void>('/auth/setup', { method: 'POST', json: { password: secret } }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['setup'] })
      qc.invalidateQueries({ queryKey: ['session'] })
    },
  })
}

export function useLogout() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api<void>('/auth/logout', { method: 'POST' }),
    onSettled: () => {
      qc.clear()
      qc.setQueryData(['session'], null)
    },
  })
}

export function useVersion() {
  return useQuery({
    queryKey: ['version'],
    queryFn: () => api<{ version: string }>('/version'),
    staleTime: Infinity,
  })
}

// --- registry and sources ----------------------------------------------------------------

export const useRegistry = () => useQuery({ queryKey: ['registry'], queryFn: () => api<Registry>('/registry') })
export const useSources = () => useQuery({ queryKey: ['sources'], queryFn: () => api<Source[]>('/sources') })

// Keyed under 'registry', so registry.changed refreshes them too (useEvents).
export const useRootsSettings = () =>
  useQuery({ queryKey: ['registry', 'settings-roots'], queryFn: () => api<RootsSettings>('/settings/roots') })

export const useRootSurvey = () =>
  useQuery({ queryKey: ['registry', 'survey'], queryFn: () => api<RootSurvey[]>('/registry/roots') })

function useRegistryMutation<V, R>(fn: (vars: V) => Promise<R>) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      for (const key of ['registry', 'sources', 'tree', 'roadmap', 'diagrams']) qc.invalidateQueries({ queryKey: [key] })
    },
  })
}

export const useSaveRoots = () =>
  useRegistryMutation(
    ({ roots, keepWorkspace = true }: { roots: { name: string; folder: string }[]; keepWorkspace?: boolean }) =>
      api<RootsSettings>('/settings/roots', { method: 'PUT', json: { roots, keep_workspace: keepWorkspace } }),
  )

export const useRegisterProject = () =>
  useRegistryMutation((item: { root: string | null; path: string; name: string; type?: ProjectType | null }) =>
    api<{ page: string; project: Project | null }>('/registry/projects', { method: 'POST', json: item }),
  )

/** Take a project out of the registry; its page moves to registry/removed/ (ADR 0026). */
export const useRemoveProject = () =>
  useRegistryMutation((id: string) =>
    api<{ moved_to: string; used_by: string[] }>(`/registry/projects/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  )

export const useRemoved = () =>
  useQuery({ queryKey: ['registry', 'removed'], queryFn: () => api<RemovedProject[]>('/registry/removed') })

export const useRestoreProject = () =>
  useRegistryMutation((id: string) =>
    api<{ page: string }>(`/registry/removed/${encodeURIComponent(id)}/restore`, { method: 'POST' }),
  )

/** Delete a removed project for good, with the studies, designs, glossary and reports kept for it. */
export const usePurgeProject = () =>
  useRegistryMutation((id: string) =>
    api<{ deleted: string[] }>(`/registry/removed/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  )

/** Set a project's type on its registry page, or null to go back to detection (ADR 0016). */
export const useSetProjectType = () =>
  useRegistryMutation(({ id, type }: { id: string; type: ProjectType | null }) =>
    api<Project>(`/registry/projects/${encodeURIComponent(id)}/type`, { method: 'PUT', json: { type } }),
  )

/** Allow or forbid Archeion's /inbox editing a project's files, or null for the default (ADR 0017). */
export const useSetInboxEdits = () =>
  useRegistryMutation(({ id, value }: { id: string; value: boolean | null }) =>
    api<Project>(`/registry/projects/${encodeURIComponent(id)}/inbox-edits`, {
      method: 'PUT',
      json: { inbox_edits: value },
    }),
  )

// --- inbox terminal (ADR 0013) ------------------------------------------------------------

/** Polled, so the page notices when the window is closed by hand. */
export const useRunner = () =>
  useQuery({ queryKey: ['runner'], queryFn: () => api<RunnerStatus>('/runner'), refetchInterval: 5000 })

function useRunnerMutation<V>(fn: (vars: V) => Promise<RunnerStatus>) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: (data) => {
      qc.setQueryData(['runner'], data)
      // One Claude job at a time (ADR 0020): the other card's buttons depend on this one.
      qc.invalidateQueries({ queryKey: ['responder'] })
    },
  })
}

export const useSetRunnerInterval = () =>
  useRunnerMutation((interval: string) => api<RunnerStatus>('/runner', { method: 'PUT', json: { interval } }))

export const useStartRunner = () =>
  useRunnerMutation((interval?: string) =>
    api<RunnerStatus>('/runner/start', { method: 'POST', json: interval ? { interval } : {} }),
  )

export const useStopRunner = () =>
  useRunnerMutation<void>(() => api<RunnerStatus>('/runner/stop', { method: 'POST', json: {} }))

// --- on-demand Claude (ADR 0020) -------------------------------------------------------------

export const useResponder = () =>
  useQuery({ queryKey: ['responder'], queryFn: () => api<ResponderStatus>('/responder'), refetchInterval: 5000 })

function useResponderMutation<V>(fn: (vars: V) => Promise<ResponderStatus>) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: (data) => {
      qc.setQueryData(['responder'], data)
      qc.invalidateQueries({ queryKey: ['runner'] })
    },
  })
}

export const useSetResponder = () =>
  useResponderMutation((settings: { enabled?: boolean; headless?: boolean; max_instances?: number; accept_edits?: boolean }) =>
    api<ResponderStatus>('/responder', { method: 'PUT', json: settings }),
  )

export const useRunResponder = () =>
  useResponderMutation<void>(() => api<ResponderStatus>('/responder/run', { method: 'POST', json: {} }))

export const useStopResponder = () =>
  useResponderMutation<void>(() => api<ResponderStatus>('/responder/stop', { method: 'POST', json: {} }))

// --- docs ------------------------------------------------------------------------------
// Every doc query is keyed by [kind, source, path, ...] so live updates can target them.

export const useTree = (source: SourceId, enabled = true) =>
  useQuery({
    queryKey: ['tree', source],
    queryFn: () => api<TreeNode>(`/docs/tree${qs({ source })}`),
    enabled,
  })

export const useDoc = (source: SourceId, path: string, enabled = true) =>
  useQuery({
    queryKey: ['doc', source, path],
    queryFn: () => api<DocFile>(`/docs/file${qs({ source, path })}`),
    enabled: enabled && path.endsWith('.md'),
    retry: false,
  })

export const useHistory = (source: SourceId, path: string, enabled = true) =>
  useQuery({
    queryKey: ['history', source, path],
    queryFn: () => api<Commit[]>(`/docs/history${qs({ source, path })}`),
    enabled,
  })

export const useDiff = (source: SourceId, path: string, rev: string | null) =>
  useQuery({
    queryKey: ['diff', source, path, rev],
    queryFn: () => api<DiffResult>(`/docs/diff${qs({ source, path, rev })}`),
    enabled: rev !== null,
  })

export const useDocAt = (source: SourceId, path: string, rev: string | null) =>
  useQuery({
    queryKey: ['at', source, path, rev],
    queryFn: () => api<DocAt>(`/docs/at${qs({ source, path, rev })}`),
    enabled: rev !== null,
    staleTime: Infinity,
  })

export const useRoadmap = () => useQuery({ queryKey: ['roadmap'], queryFn: () => api<Roadmaps>('/roadmap') })

export const useDiagrams = (source?: SourceId) =>
  useQuery({ queryKey: ['diagrams', source ?? 'all'], queryFn: () => api<Diagram[]>(`/diagrams${qs({ source })}`) })

export const useSearch = (q: string, source?: SourceId) =>
  useQuery({
    queryKey: ['search', q, source ?? 'all'],
    queryFn: () => api<SearchHit[]>(`/search${qs({ q, source })}`),
    enabled: q.trim().length >= 2,
    placeholderData: keepPreviousData,
  })

// --- feedback --------------------------------------------------------------------------

export type FeedbackFilters = {
  status?: FeedbackStatus
  kind?: FeedbackKind
  source?: SourceId
  doc_path?: string
}

export const useFeedbackList = (filters: FeedbackFilters, enabled = true) =>
  useQuery({
    queryKey: ['feedback', 'list', filters],
    queryFn: () => api<FeedbackThread[]>(`/feedback${qs(filters)}`),
    enabled,
  })

export const useFeedbackSummary = () =>
  useQuery({ queryKey: ['feedback', 'summary'], queryFn: () => api<FeedbackSummary>('/feedback/summary') })

export const useFeedbackItem = (id: number) =>
  useQuery({
    queryKey: ['feedback', 'item', id],
    queryFn: () => api<{ item: FeedbackItem; thread: FeedbackItem[] }>(`/feedback/${id}`),
    enabled: Number.isFinite(id),
    retry: false,
  })

function useFeedbackMutation<V, R>(fn: (vars: V) => Promise<R>) {
  const qc = useQueryClient()
  return useMutation({ mutationFn: fn, onSuccess: () => qc.invalidateQueries({ queryKey: ['feedback'] }) })
}

export const useCreateFeedback = () =>
  useFeedbackMutation((item: NewFeedback) => api<FeedbackItem>('/feedback', { method: 'POST', json: item }))

export const usePatchFeedback = () =>
  useFeedbackMutation(({ id, ...patch }: { id: number; status?: FeedbackStatus; body?: string }) =>
    api<FeedbackItem>(`/feedback/${id}`, { method: 'PATCH', json: patch }),
  )

/** Send a thread back to Claude: adds a "Reopened" message after its latest one (ADR 0018). */
export const useReopenFeedback = () =>
  useFeedbackMutation((id: number) => api<FeedbackItem>(`/feedback/${id}/reopen`, { method: 'POST', json: {} }))

export const useDeleteFeedback = () =>
  useFeedbackMutation((id: number) => api<void>(`/feedback/${id}`, { method: 'DELETE' }))

// --- code studies (ADR 0019) -----------------------------------------------------------------

// Keyed under 'studies', so studies.changed refreshes them all (useEvents).
export const useStudyIndex = () => useQuery({ queryKey: ['studies'], queryFn: () => api<SnapshotRow[]>('/studies') })

export const useSnapshots = (project: string, enabled = true) =>
  useQuery({
    queryKey: ['studies', project],
    queryFn: () => api<SnapshotRow[]>(`/studies/${encodeURIComponent(project)}`),
    enabled,
  })

export const useSnapshot = (project: string, snapshot: string | null) =>
  useQuery({
    queryKey: ['studies', project, 'snapshot', snapshot],
    queryFn: () => api<SnapshotFull>(`/studies/${encodeURIComponent(project)}/${encodeURIComponent(snapshot ?? '')}`),
    enabled: Boolean(snapshot),
    placeholderData: keepPreviousData,
  })

export const useStudyDiff = (project: string, from: string | null, to: string | null) =>
  useQuery({
    queryKey: ['studies', project, 'diff', from, to],
    queryFn: () => api<StudyDiff>(`/studies/${encodeURIComponent(project)}/diff${qs({ from, to })}`),
    enabled: Boolean(from && to),
  })

export const useStudySearch = (q: string) =>
  useQuery({
    queryKey: ['studies', 'search', q],
    queryFn: () => api<StudyHit[]>(`/studies/search${qs({ q })}`),
    enabled: q.trim().length >= 2,
    placeholderData: keepPreviousData,
  })

export const useSystemLinks = () =>
  useQuery({ queryKey: ['studies', 'system-links'], queryFn: () => api<SystemLinks>('/system/links') })

// --- designs (ADR 0022) ----------------------------------------------------------------------

// Keyed under 'designs', so designs.changed refreshes them all (useEvents).
export const useDesignIndex = () => useQuery({ queryKey: ['designs'], queryFn: () => api<DesignRow[]>('/designs') })

export const useDesigns = (project: string) =>
  useQuery({
    queryKey: ['designs', project],
    queryFn: () => api<DesignRow[]>(`/designs/${encodeURIComponent(project)}`),
  })

export const useDesign = (project: string, slug: string | null, revision: number | null) =>
  useQuery({
    queryKey: ['designs', project, 'design', slug, revision],
    queryFn: () =>
      api<DesignFull>(
        `/designs/${encodeURIComponent(project)}/${encodeURIComponent(slug ?? '')}${qs({ revision })}`,
      ),
    enabled: Boolean(slug),
    placeholderData: keepPreviousData,
  })

export const useDesignPreflight = (project: string, purpose: 'design' | 'handoff', slug: string) =>
  useQuery({
    queryKey: ['designs', project, 'preflight', purpose, slug],
    queryFn: () =>
      api<Preflight>(`/designs/${encodeURIComponent(project)}/preflight${qs({ for: purpose, slug })}`),
  })

export const useDesignApproval = (project: string, slug: string, enabled: boolean) =>
  useQuery({
    queryKey: ['designs', project, 'approval', slug],
    queryFn: () => api<Approval>(`/designs/${encodeURIComponent(project)}/${encodeURIComponent(slug)}/approval`),
    enabled,
  })

function useDesignMutation<V, R>(fn: (v: V) => Promise<R>) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['designs'] })
      qc.invalidateQueries({ queryKey: ['registry'] })
      qc.invalidateQueries({ queryKey: ['feedback'] })
    },
  })
}

const designPath = (project: string, slug: string) => `/designs/${encodeURIComponent(project)}/${encodeURIComponent(slug)}`

export const useSetDesignStage = (project: string, slug: string) =>
  useDesignMutation((stage: string) => api<DesignRow>(`${designPath(project, slug)}/stage`, { method: 'PUT', json: { stage } }))

export const useApproveDesign = (project: string, slug: string) =>
  useDesignMutation(() => api<DesignRow>(`${designPath(project, slug)}/approve`, { method: 'POST' }))

export const useHandoffDesign = (project: string, slug: string) =>
  useDesignMutation(() => api<FeedbackItem>(`${designPath(project, slug)}/handoff`, { method: 'POST' }))

export const useDesignImpact = (project: string, slug: string) =>
  useQuery({
    queryKey: ['designs', project, 'impact', slug],
    queryFn: () => api<Impact[]>(`${designPath(project, slug)}/impact`),
  })

export const useBuiltVsDesigned = (project: string, slug: string) =>
  useQuery({
    queryKey: ['designs', project, 'built', slug],
    queryFn: () => api<BuiltVsDesigned>(`${designPath(project, slug)}/built`),
  })

// --- glossary (ADR 0023) ------------------------------------------------------------------

export type GlossaryTerm = { id: string; term: string; aliases: string[]; definition: string }
export type GlossaryInput = { term: string; definition: string; aliases: string[] }

export const useGlossary = (project: string) =>
  useQuery({
    queryKey: ['glossary', project],
    queryFn: () => api<GlossaryTerm[]>(`/glossary/${encodeURIComponent(project)}`),
  })

/** Add a term, or change the one with id `replace`. */
export function useSaveTerm(project: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ replace, ...json }: GlossaryInput & { replace?: string }) =>
      api<GlossaryTerm>(`/glossary/${encodeURIComponent(project)}${replace ? `/${encodeURIComponent(replace)}` : ''}`, {
        method: replace ? 'PUT' : 'POST',
        json,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['glossary', project] }),
  })
}

export function useDeleteTerm(project: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      api<void>(`/glossary/${encodeURIComponent(project)}/${encodeURIComponent(id)}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['glossary', project] }),
  })
}

/** Archeion's own CHANGELOG.md, of the commit that's checked out. */
export const useChangelog = () =>
  useQuery({ queryKey: ['changelog'], queryFn: () => api<{ content: string }>('/changelog'), retry: false })
