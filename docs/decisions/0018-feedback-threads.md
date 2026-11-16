# 0018: Feedback is a thread

- Status: Accepted (2026-11-16)
- Date: 2026-11-16
- Amends: [ADR 0002](0002-viewer-app-and-claude-feedback-loop.md) (the feedback loop) and the feedback part of the [viewer plan](../roadmap/2026-11-15-viewer-app-plan.md).

## Context
Feedback items could already point at a `parent_id`, and the thread page had a **Follow up** button. In practice a follow-up behaved like a separate item:
- It opened the same form as new feedback, kind picker included, instead of a reply under Claude's answer.
- It showed as its own card in every list, with its own status, so one conversation could be open, answered and resolved all at once.
- `inbox show` cut every earlier message and reply to 200 characters, so Claude answered a follow-up without the conversation it belonged to.

## Decision
1. **A thread is the unit.** It's the first item plus every reply written after Claude answered. Each item records its thread's first item in `thread_id` (migration 6, backfilled from `parent_id`). It's a plain id like the rest of the table's references.
2. **A thread's status is its latest message's status.** Claude still works message by message (claim, reply, release), so the inbox needs no new states.
3. **At most one message per thread waits for Claude, and it's always the latest.** A reply is refused while one waits (409). To add to a message Claude hasn't picked up, edit it. A reply always goes after the thread's latest message, whichever message it names.
4. **Resolving resolves the whole thread**, from any of its messages: every open or answered message becomes resolved, and dismissing a waiting message does the same. It's refused while Claude is working on the thread. Only the latest message can be released.
5. **Reopening adds a message, it never rewinds one.** **Reopen thread** (`POST /api/feedback/{id}/reopen`, optional `{body}`) adds "Reopened: please take another look at your last answer." after the latest message, which you can edit to say more. A reply to a resolved thread reopens it too. An answered message never goes back to open, so Claude's earlier answers stay in the conversation instead of being overwritten. Migration 7 turns items reopened the old way (open, with a reply) into this shape.
6. **A reply stays with its thread.** It keeps the thread's project and, unless it names its own, its kind and doc, so the API needs only `{body, parent_id}`.
7. **Lists and counts are per thread.** `GET /api/feedback` returns one row per thread: the first message's request, doc and anchor, with the thread's status, latest reply, message count (`messages`), latest message (`latest_id`) and last change. The summary and the header badge count threads.
8. **The backend builds the conversation for Claude.** `inbox show` on a reply prints the whole thread in full and in order, every message and reply, with the first message's quote and doc excerpt, and marks the message to answer. `--json` returns the same text as `conversation`. It's built each time it's read, never stored, so an edit to any message is reflected.

## Consequences
- In the viewer, the thread's actions sit under Claude's latest answer: **Resolve thread**, **Reopen thread** (a new "Reopened" message for Claude) and a box to reply in.
- `/inbox` and `/archeion:inbox` read one block of context instead of piecing the thread together. A long thread makes a long `show`, which is the point.
- Deleting is limited to a waiting message, so a thread's first message can't be deleted once it has replies. A thread with nothing but one open message can still be deleted whole.

## Addendum (2026-11-17): threads from a session
A session in a project only had `inbox create`, which always starts a thread, so `/archeion:report` and `/archeion:inbox` couldn't carry on a conversation the way a reply in the viewer does. The inbox CLI now has the same thread operations as the viewer:
- `inbox create --in <id>` adds the next message to the thread `<id>` is in, with the same rules as a viewer reply (point 3 and 6): it goes after the latest message, keeps the thread's project and kind, and is refused while a message waits. It records the caller's project as its origin.
- `--claim` writes it already in progress, for a message the session records and answers itself (a follow-up the user typed in the chat). It never shows as open, so on-demand Claude (ADR 0020) doesn't start a run for it.
- `inbox threads` lists threads as `GET /api/feedback` does (point 7); `--from-here` narrows to those a project started (the root's `origin`). `inbox resolve <id>` resolves a thread (point 4).
- A session carries on a thread only if it knows the thread's id, so every inbox command that changes an item, and `show`, prints a fixed `ids: item #N, thread #T` line (`--json`: `id`, `thread_id`; `show --json` also `latest_id`). The skills read the ids from it, name them in the chat, and fall back to `inbox threads` when the chat no longer has them.
