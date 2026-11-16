# 0020: Study conversations, and Claude on demand

- Status: Accepted (2026-11-16)
- Date: 2026-11-16
- Amended by: [ADR 0021](0021-claude-jobs-windows-headless-and-limits.md) (2026-11-16): runs are watchable sessions or headless, and up to 2 Claude instances may run.
- Builds on: [ADR 0019](0019-code-studies.md) (code studies), [ADR 0018](0018-feedback-threads.md) (threads), [ADR 0013](0013-start-the-inbox-terminal-from-the-viewer.md) (the inbox terminal)

## Context
A study ran in one go: Claude planned, waited for a yes in the terminal, then read and saved. What it finds often needs the user, who knows why a module exists, which flows matter and what a finding really means. The viewer already has threads, but a thread only moves when someone runs `/inbox`. The inbox terminal (ADR 0013) does that on a timer, which is slow for a conversation and wasteful when nothing is waiting.

## Decision
1. **A study is a conversation.** **Ask Claude to study** on the project page's Study tab starts a thread for Archeion. Its first message is anchored to the task (`anchor.task = {type: "study", project}`), so it needs no doc. Being Archeion's item keeps it away from the project's own session. Each round, Claude reports what it found, shows the draft, and asks what it needs to know. The user answers in the thread, and the next round builds on the answer. When the user approves, Claude saves the snapshot and updates the registry page.
2. **A draft carries the study between rounds.** `study draft save <project>` keeps a validated work-in-progress model in `registry/studies/<project>/draft/`, with the thread it belongs to. The Study tab shows it as **Draft**, diagrams included, so the user reviews the real thing, not a description. `study save <project> --from-draft` turns it into a dated snapshot (which records the thread) and removes the draft. `study draft discard` drops it.
3. **Claude on demand.** A second, separate Claude process can answer the inbox as soon as something is waiting: **Settings → On-demand Claude**. When it's switched on, the backend starts `claude -p "/inbox"` in its own console window whenever a new message is waiting (a new thread, a reply, a reopen), and the window closes when that run ends. A message written during a run starts another run after it. Messages Claude released (left open on purpose) don't start a run, so it can't loop. **Run now** starts one run by hand. It's tracked like the inbox terminal, by PID plus process start time, in its own `responder` table.
4. **One Claude job at a time.** On-demand Claude can't be switched on or run while the inbox terminal runs, and the inbox terminal can't be started while on-demand Claude is switched on or running. Both need a loopback backend, like ADR 0013.
5. **What a run may do.** It runs at the repo root with `--permission-mode acceptEdits` and `--add-dir` for every granted root. It may edit files and run the commands the skills allow, such as the backend CLI. Other commands, a project's tests among them, aren't approved without a person there, so Claude says in its reply what it couldn't run. Each run's output goes to a log in `app/backend/data/responder/` (gitignored) and appears in its window.

## Consequences
- A study usually takes two or three rounds instead of one terminal session. With on-demand Claude on, each round is answered within seconds of the reply.
- Unattended runs can't approve arbitrary commands. Work that needs them belongs in a terminal session.
- New API: `GET`/`PUT /api/responder`, `POST /api/responder/run`, `POST /api/responder/stop`. Database migration 8 adds the `responder` table.
