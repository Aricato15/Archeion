import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, isUnauthorized, qs } from './client'
import type {
  Commit,
  Diagram,
  DiffResult,
  DocAt,
  DocFile,
  FeedbackItem,
  FeedbackKind,
  FeedbackStatus,
  FeedbackSummary,
  NewFeedback,
  Project,
  Registry,
  RootSurvey,
  RootsSettings,
  Roadmaps,
  SearchHit,
  Source,
  SourceId,
  TreeNode,
} from './types'

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
  useRegistryMutation((item: { root: string | null; path: string; name: string }) =>
    api<{ page: string; project: Project | null }>('/registry/projects', { method: 'POST', json: item }),
  )

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
    queryFn: () => api<FeedbackItem[]>(`/feedback${qs(filters)}`),
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

export const useDeleteFeedback = () =>
  useFeedbackMutation((id: number) => api<void>(`/feedback/${id}`, { method: 'DELETE' }))
