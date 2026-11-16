# 0013: Start the inbox terminal from the viewer

- Status: Accepted (2026-11-15)
- Amended by: [ADR 0020](0020-study-conversations-and-on-demand-claude.md) (2026-11-16): the terminal doesn't start while on-demand Claude is on or running.
- Date: 2026-11-15
- Builds on: [ADR 0002](0002-viewer-app-and-claude-feedback-loop.md) (option A, the inbox pulled by a terminal session)

## Context
The terminal is the main place to work with Claude, and the viewer is for reading and feedback. Feedback written in the viewer only reaches Claude when someone runs `/inbox`. A Claude Code session running `/loop <interval> /inbox` picks it up on its own, but only while its window is open, and nothing showed whether one was.

## Decision
1. **The backend starts the inbox terminal on request.** `POST /api/runner/start` runs `claude "/loop <interval> /inbox"` in a new console window at the repo root, so the session-start hook and the project skills apply. `POST /api/runner/stop` closes it and everything it started. `start.bat` and `stop.bat` don't touch it.
2. **The backend tracks it.** It stores the process ID and the process's start time in its database (`runner` table). The terminal counts as running only while a process with that ID *and* that start time exists, so a backend restart keeps the status and a reused PID is never mistaken for it, or killed. Closing the window by hand shows up as stopped.
3. **The interval is set in the viewer** and stored in the same table, not in `.env`. It's validated as `1m` to `24h` (minutes or hours) before it goes on the command line. A running terminal keeps its interval until it's restarted.
4. **Guard rails.** Like every endpoint, these need an admin session. Starting also needs a backend that listens on loopback (as first-run setup does, ADR 0011), because the window opens on the machine running the backend. The command is fixed: only the validated interval varies, and the process gets no shell. It's Windows only, like the root scripts.
5. **The viewer shows it:** a card on the Settings page (status, interval, Start / Stop / Restart, polled every 5 seconds) and a badge in the header.

## Consequences
- The terminal is an ordinary interactive Claude Code session: file edits and other tools still ask for approval in its window. It doesn't work unattended unless you change its permission mode yourself.
- Each check is a short Claude turn, even when the inbox is empty, so a longer interval costs less.
- The backend now starts a process. Apart from git, this is the only one, and it's limited as described above. It still never writes to a project.
- If Claude Code exits by itself, its window closes too, and the card shows the terminal as stopped.
