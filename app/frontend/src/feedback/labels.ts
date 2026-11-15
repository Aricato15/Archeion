import type { FeedbackItem, FeedbackKind, FeedbackStatus } from '../api/types'
import { docUrl } from '../docs/links'

export const KIND_LABEL: Record<FeedbackKind, string> = {
  comment: 'Comment',
  review: 'Review',
  prompt: 'Prompt',
}

export const KIND_HELP: Record<FeedbackKind, string> = {
  comment: 'A remark on a specific spot',
  review: 'Feedback on the doc as a whole',
  prompt: 'A task for Claude to carry out',
}

export const STATUS_LABEL: Record<FeedbackStatus, string> = {
  open: 'Open',
  in_progress: 'In progress',
  answered: 'Answered',
  resolved: 'Resolved',
}

export const STATUS_COLOR: Record<FeedbackStatus, string> = {
  open: 'blue',
  in_progress: 'yellow',
  answered: 'green',
  resolved: 'gray',
}

/** In-app link to the spot a feedback item is about. */
export function docLink(item: FeedbackItem): string | null {
  if (!item.doc_path) return null
  const line = item.anchor?.lines?.[0]
  const url = docUrl(item.source, item.doc_path)
  return line ? `${url}?line=${line}` : url
}
