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
  Roadmap,
  SearchHit,
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

// --- docs ------------------------------------------------------------------------------

export const useTree = () => useQuery({ queryKey: ['tree'], queryFn: () => api<TreeNode>('/docs/tree') })

export const useDoc = (path: string) =>
  useQuery({
    queryKey: ['doc', path],
    queryFn: () => api<DocFile>(`/docs/file${qs({ path })}`),
    enabled: path.endsWith('.md'),
    retry: false,
  })

export const useHistory = (path: string, enabled = true) =>
  useQuery({
    queryKey: ['history', path],
    queryFn: () => api<Commit[]>(`/docs/history${qs({ path })}`),
    enabled,
  })

export const useDiff = (path: string, rev: string | null) =>
  useQuery({
    queryKey: ['diff', path, rev],
    queryFn: () => api<DiffResult>(`/docs/diff${qs({ path, rev })}`),
    enabled: rev !== null,
  })

export const useDocAt = (path: string, rev: string | null) =>
  useQuery({
    queryKey: ['at', path, rev],
    queryFn: () => api<DocAt>(`/docs/at${qs({ path, rev })}`),
    enabled: rev !== null,
    staleTime: Infinity,
  })

export const useRoadmap = () => useQuery({ queryKey: ['roadmap'], queryFn: () => api<Roadmap>('/roadmap') })

export const useDiagrams = () =>
  useQuery({ queryKey: ['diagrams'], queryFn: () => api<Diagram[]>('/diagrams') })

export const useSearch = (q: string) =>
  useQuery({
    queryKey: ['search', q],
    queryFn: () => api<SearchHit[]>(`/search${qs({ q })}`),
    enabled: q.trim().length >= 2,
    placeholderData: keepPreviousData,
  })

// --- feedback --------------------------------------------------------------------------

export type FeedbackFilters = { status?: FeedbackStatus; kind?: FeedbackKind; doc_path?: string }

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
