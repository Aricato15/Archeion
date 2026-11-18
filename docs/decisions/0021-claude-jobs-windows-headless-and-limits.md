# 0021: Claude jobs: visible sessions, headless runs and a limit

- Status: Accepted (2026-11-16)
- Date: 2026-11-16
- Amends: [ADR 0020](0020-study-conversations-and-on-demand-claude.md) (on-demand Claude) and [ADR 0013](0013-start-the-inbox-terminal-from-the-viewer.md) (the inbox terminal)

## Context
On-demand Claude ran `claude -p "/inbox"` in a PowerShell window. Print mode shows nothing until the run ends, so the window was blank while Claude worked, and there was no way to watch it think, read and edit. Some runs are better silent, with no window at all. And "one Claude job at a time" was too strict: with on-demand answers, two jobs side by side (a long study round and a quick reply, say) are useful. More than two is a cost and noise risk.

## Decision
1. **Visible sessions are interactive.** By default each on-demand run opens a console window running `cmd /c claude "/inbox"`, Claude Code's normal interactive session, so its thinking, tool calls and edits show as they happen. The person watching can also approve a command the run isn't allowed on its own.
2. **A visible session closes itself when the turn ends.** The backend starts it with `ARCHEION_ON_DEMAND_DONE` set to a marker file. The project's Stop hook (`scripts/on-demand-done.ps1`, a no-op in every other session) writes that file when Claude finishes its turn, and the backend's watcher then closes the window. A session waiting for a permission answer hasn't finished its turn, so it stays open.
3. **Headless runs.** With **Headless** on (Settings), runs open no window: `claude -p "/inbox" --output-format stream-json --verbose`, with every event (thinking, tool calls, results) written to a log in `app/backend/data/responder/`. A headless run can't ask anyone, so only edits and Archeion's own CLI are allowed, as before.
4. **The inbox terminal stays a window.** `/loop` needs an interactive session, so Headless doesn't apply to it. It now opens through `cmd /c claude` too. For silent answers, use on-demand Claude with Headless on.
5. **A limit on Claude instances.** **Max Claude instances** (Settings) is 1 or 2, 1 by default. It counts the inbox terminal and every on-demand run. Nothing starts past the limit: the inbox terminal refuses, and on-demand Claude waits for a free slot. With 1, the ADR 0020 rule stays as it was: on-demand Claude can't be switched on while the inbox terminal runs, and the terminal can't start while on-demand Claude is on. With 2, they work side by side, or two on-demand runs work in parallel. Claiming an item is atomic, so two runs never take the same message.
6. **Edits: auto mode, or seek confirmations.** One setting for both the inbox terminal and on-demand runs. **Auto mode** (the default) passes `--permission-mode auto`; v1.3.2 changed it from `acceptEdits`, so it no longer stops at each command the skills run. The stored value is still `accept_edits`. **Seek user confirmations** passes no mode, so Claude asks before each edit in its window. A headless run has no one to ask, so the two can't be combined. Before this setting, the inbox terminal always asked; with the default it now accepts edits too. Migration 10.
7. **Runs are jobs.** Each on-demand run is a row in a `claude_jobs` table (PID plus process start time, mode, log, marker). The settings are on the `responder` row. Migration 9.

## Consequences
- `scripts/respond.ps1` is gone: the backend starts `cmd` or `claude` itself.
- A visible session left waiting for an approval keeps its slot until someone answers or presses **Stop**.
- The Stop hook runs at the end of every turn of every session in this repo, and returns at once when the marker variable isn't set.
