# Plan: Archeion viewer app

- Date: 2026-11-15
- Status: Accepted (2026-11-15)
- Implements: [ADR 0002](../decisions/0002-viewer-app-and-claude-feedback-loop.md), within the hard rules in [`CLAUDE.md`](../../CLAUDE.md)

This plan covers building the viewer app. The other projects' docs are out of scope for now.

## Goal
When this is done, running `start.bat` brings up a password-protected local web app. In it you can:
- browse and read every doc under `docs/`, with Mermaid diagrams rendered,
- see the git history and diffs of each doc,
- see pages update live when files change,
- leave prompts, reviews and comments that a Claude Code session picks up through `/inbox`,
- read Claude's replies in the app.

## Phases at a glance

| Phase | Delivers | You can... |
|---|---|---|
| 0. Scaffolding | Backend and frontend skeletons, `.env.example`, lint and test setup | run `uv run pytest` and `npm test` |
| 1. Auth and root scripts | Password CLI, login and sessions, `start.bat`, `stop.bat`, `set_admin_password.bat`, login page | set a password, start the app, log in and out |
| 2. Docs viewer | Doc tree, file view, Markdown and Mermaid rendering, live updates | read the docs in a browser while they change |
| 3. History, roadmap, diagrams | Git history and diffs, roadmap view, diagram gallery, search | see what changed and when |
| 4. Feedback loop (option A) | Feedback API and UI, `inbox` CLI, `/inbox` skill, SessionStart hook | comment in the browser, get Claude's reply in the browser |
| 5. Ask Claude (option B) | Agent SDK runs from the browser, a diff to accept or discard | *later, needs its own go-ahead* |

Each phase finishes with its tests and linters passing, `CLAUDE.md` updated and one or more small commits.

---

## Phase 0: Scaffolding and decisions

### Decisions to record
- Accept ADR 0002 and record that option A gets built first. Option B stays proposed.
- New ADR 0004, "Viewer app stack and layout". It covers:
  - the backend venv lives in `app/backend/venv/` (`UV_PROJECT_ENVIRONMENT=venv`), a deliberate exception to the workspace default of `.venv/`,
  - in development the Vite dev server proxies `/api` to the backend, so the browser sees one origin: no CORS, and cookies just work,
  - the libraries chosen below.

### Backend (`app/backend/`)
```
app/backend/
  pyproject.toml          # name "archeion-backend"; python pinned to 3.12
  .python-version
  uv.lock
  app/
    __init__.py
    __main__.py           # CLI entry: serve | password set|status|clear-sessions | inbox ...
    config.py             # pydantic-settings; reads the repo-root .env
    db.py                 # connection factory (pragmas), migrations via PRAGMA user_version
    main.py               # FastAPI app factory: middleware, routers, lifespan (watcher)
    security.py           # scrypt hashing, session tokens, auth dependency
    paths.py              # repo root, docs root, safe path resolution
    routers/              # health, auth, docs, history, events, feedback
    services/             # docs_fs, git, watcher, events bus, feedback
  tests/
    conftest.py           # temp git repo with docs/, temp db, logged-in client fixture
```
- Runtime dependencies: `fastapi`, `uvicorn[standard]`, `pydantic-settings`, `watchfiles`. Use the `sqlite3` and `hashlib.scrypt` from the standard library, with no ORM.
- Dev dependencies: `pytest`, `httpx`, `ruff`. `mypy` is optional.

### Frontend (`app/frontend/`)
```
app/frontend/
  package.json, package-lock.json, vite.config.ts, tsconfig*.json, eslint.config.js
  src/
    main.tsx, App.tsx     # MantineProvider, QueryClientProvider, router
    api/                  # fetch wrapper (credentials, 401 handling), typed endpoints
    auth/                 # useSession, LoginPage, RequireAuth
    layout/               # AppShell: sidebar tree, header (feedback badge, logout)
    docs/                 # DocPage, MarkdownView, MermaidBlock, DocTree
    history/              # HistoryDrawer, DiffView
    feedback/             # FeedbackPanel, FeedbackList, FeedbackForm
    roadmap/, diagrams/, search/
    events/               # SSE hook -> invalidates TanStack Query caches
```
- Libraries:
  - UI and data: `@mantine/core`, `@mantine/hooks`, `@mantine/notifications`, `react-router-dom`, `@tanstack/react-query`.
  - Markdown: `react-markdown`, `remark-gfm`, `rehype-slug`.
  - Diagrams: `mermaid`, lazy-loaded.
  - Diffs: `diff2html`.
- Dev tools: `vitest`, `@testing-library/react`, `eslint`, `typescript`.
- Vite settings: port from `ARCHEION_FRONTEND_PORT` (20301), `strictPort: true`, host `127.0.0.1`, and a proxy from `/api` to `http://127.0.0.1:${ARCHEION_PORT}`.

### Config (`.env.example`, committed; `.env` at repo root, gitignored)
```
ARCHEION_HOST=127.0.0.1
ARCHEION_PORT=20300
ARCHEION_FRONTEND_PORT=20301
ARCHEION_DB_PATH=app/backend/data/archeion.db   # relative to repo root
ARCHEION_SESSION_IDLE_HOURS=12
ARCHEION_SESSION_MAX_DAYS=7
```
All paths are relative to the repo root and resolved in `paths.py`. Nothing absolute is ever written to a committed file.

### Done when
`uv run pytest` and `ruff check` pass on an empty test, `npm run lint`, `npm run typecheck` and `npm test` pass, and the `CLAUDE.md` Commands section is filled in.

---

## Phase 1: Authentication and root scripts

### Database (migration 1)
```sql
CREATE TABLE admin (
  id            INTEGER PRIMARY KEY CHECK (id = 1),
  pw_hash       TEXT NOT NULL,          -- "scrypt$n$r$p$<salt b64>$<hash b64>"
  updated_at    TEXT NOT NULL
);
CREATE TABLE sessions (
  token_hash    TEXT PRIMARY KEY,       -- sha256 of the cookie value; the raw token is never stored
  created_at    TEXT NOT NULL,
  last_seen_at  TEXT NOT NULL,
  expires_at    TEXT NOT NULL
);
```
- Every connection sets `journal_mode=WAL`, `busy_timeout=5000` and `foreign_keys=ON`. Writes use `BEGIN IMMEDIATE`.
- Migrations are numbered functions applied in order, with `PRAGMA user_version` recording which have run.

### Password CLI (`python -m app password ...`)
- `set` prompts twice with `getpass` (input is hidden) and requires at least 12 characters. It stores the scrypt hash (n=2^15, r=8, p=1, a 16-byte salt) and **deletes all sessions** in the same transaction.
- `status` exits 0 when a password is set and 3 when not. `start.bat` relies on these exit codes.
- `clear-sessions` logs everyone out.

### API
| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/health` | none | `{"status":"ok"}`, shows nothing else |
| POST | `/api/auth/login` | none | `{password}` returns 204 and sets the cookie; a wrong password returns 401 |
| POST | `/api/auth/logout` | session | deletes the session and clears the cookie |
| GET | `/api/auth/session` | session | 200 `{expires_at}`, or 401. The frontend calls this on load. |

- **Cookie:** `archeion_session`, a 32-byte random token, `HttpOnly`, `SameSite=Strict`, `Path=/`. It isn't marked `Secure` because the app runs on plain http on localhost.
- **Session lifetime:** each request pushes `last_seen_at` forward, but a session ends after 12 idle hours or 7 days in total.
- **Login rate limit:** kept in memory and counted per client IP, so it resets when the backend restarts. After 5 failures in 10 minutes, further attempts get 429 with backoff. Every failed attempt waits a fixed delay so timing reveals nothing, and the hash comparison uses `hmac.compare_digest`.
- **Auth by default:** a router-level dependency guards the whole app. The two public routes are explicitly marked as exceptions. A test walks `app.routes` and asserts that every route except those two returns 401 without a cookie, so a new endpoint can't be left unprotected by accident.
- **CSRF and DNS rebinding:** the `SameSite=Strict` cookie stops cross-site requests from carrying the session. On top of that, state-changing methods must send an `Origin` header that matches the frontend origin, and `TrustedHostMiddleware` only accepts `127.0.0.1` and `localhost`.

### Root scripts
- `start.bat` (`cd /d "%~dp0"`) calls `scripts/start.ps1`, which:
  1. loads `.env`, falling back to the defaults when it's missing,
  2. checks for `app/backend/venv` and `app/frontend/node_modules`, and if either is missing, prints the exact install commands and exits,
  3. runs `password status` and stops with "run set_admin_password.bat first" when no password is set,
  4. checks that both ports are free,
  5. opens a "Archeion backend" window running `uv run python -m app serve` and a "Archeion frontend" window running `npm run dev`,
  6. prints the URL.
- `stop.bat` calls `scripts/stop.ps1`. It finds the processes listening on the two ports (`Get-NetTCPConnection -State Listen`) and stops only those whose process name is `python`/`uvicorn` or `node`. It reports what it stopped and says so when nothing was running.
- `set_admin_password.bat` runs the backend venv's python with `-m app password set` directly, since it is too short to need a PowerShell helper. That also logs out every session.envScriptspython.exe -m app password set` in the backend folder directly (it is short enough not to need a PowerShell helper). That also logs out every session.
- Every script sets `UV_PROJECT_ENVIRONMENT=venv` before calling `uv`.
- Optional, see the open questions: `setup.bat`, which runs `uv sync` and `npm install`.

### Frontend
- A login page: a password field, a submit button, and error and rate-limit messages.
- `RequireAuth` wraps every other route. Any 401 from the API clears the query cache and returns you to `/login`. Nothing but the login page renders before the session check succeeds.
- A header with a logout button.

### Tests
- Hashing round-trip and wrong-password checks.
- Setting a password invalidates sessions.
- Expired sessions are rejected.
- The rate limiter kicks in.
- The "every route requires auth" test.
- The CLI exit codes.

### Done when
From a fresh clone, these steps work end to end:
1. install,
2. `set_admin_password.bat`,
3. `start.bat`,
4. log in and log out,
5. `stop.bat`.

---

## Phase 2: Docs viewer and live updates

### Backend
| Method | Path | Returns |
|---|---|---|
| GET | `/api/docs/tree` | nested `{name, path, type: "dir"|"file", children}`, covering `.md` files plus images under `docs/`; dotfiles are skipped |
| GET | `/api/docs/file?path=` | `{path, content, sha, modified_at, dirty}` (raw Markdown; `dirty` means it differs from HEAD) |
| GET | `/api/docs/raw?path=` | images (png, jpg, gif, webp, svg) with their own content type and a strict CSP |
| GET | `/api/events` | SSE stream (see below) |

- **Path safety (`paths.py`), one function every route uses:**
  - reject absolute paths, drive letters, `..`, NUL characters and backslashes,
  - resolve the path and require it to sit under `docs/` after symlinks are followed,
  - allow only known extensions,
  - cap the file size at 2 MB.
- **Watcher:** `watchfiles.awatch(docs/)` runs as a background task in the lifespan. Changes are debounced by 200 ms and published on an in-process event bus.
- **SSE:** `/api/events` uses the session cookie (`EventSource` sends it on the same origin). Event types:
  - `docs.changed {paths, kind: added|modified|deleted}`,
  - `feedback.changed {ids}` (from phase 4),
  - `ping` every 20 s, which keeps the connection alive and catches expired sessions.

### Frontend
- **Sidebar:** the `DocTree` built from `/api/docs/tree`, with the current doc highlighted. The URL is `/docs/<path>`.
- **`MarkdownView`:** renders GFM with heading anchors (`rehype-slug`), turns relative links into in-app routes, loads images through the API and puts a `data-line` attribute on each block (taken from the Markdown source position, which phase 4 uses as the comment anchor).
- **`MermaidBlock`:** loads `mermaid` lazily. It renders with `securityLevel: "strict"` and a theme that follows Mantine's color scheme. On a render error it shows the error and the source instead of a blank box.
- **Live updates:** the `useEvents` hook turns `docs.changed` into query invalidation. The page re-renders in place and keeps the scroll position, a small "updated" notification appears, and a doc that gets deleted shows a notice.
- Includes a table of contents for long docs and light and dark mode.

### Tests
- Backend: the path traversal cases (`../`, `..%2f`, absolute paths, a drive path, a symlink pointing outside, a wrong extension), the tree contents, and an SSE event arriving after a file write in the temp repo.
- Frontend: `MarkdownView` rewrites links and `MermaidBlock` shows its error state.

### Done when
You can read every current doc in the browser, and editing a doc in an editor updates the open page within about a second.

---

## Phase 3: History, roadmap, diagrams, search

### Backend
| Method | Path | Returns |
|---|---|---|
| GET | `/api/docs/history?path=&limit=50` | `[{rev, short, author_name, date, subject}]` from `git log --follow` |
| GET | `/api/docs/diff?path=&rev=` | unified diff of that commit for that path, or of the working tree against HEAD when `rev=WORKTREE` |
| GET | `/api/docs/at?path=&rev=` | file content at a revision |
| GET | `/api/roadmap` | `docs/roadmap/roadmap.md` parsed into `{updated, now[], next[], later[]}` with each item's links, plus a list of the dated plans in `docs/roadmap/` |
| GET | `/api/diagrams` | every Mermaid block under `docs/`: `{path, heading, index, source}` |
| GET | `/api/search?q=` | case-insensitive matches in docs: `{path, line, snippet}`, capped at 200 |

- **Git calls:** done through `subprocess` with an argument list, never a shell. `rev` must match `^[0-9a-f]{7,40}$` or be `WORKTREE`, and paths go through the phase 2 safety check and come after `--`. Each call has a 5 s timeout.
- **Privacy:** author emails are never sent to the frontend. The log format has no `%ae`.

### Frontend
- A history drawer on each doc lists commits. Choosing one shows the diff from `diff2html` (side by side or inline) and offers "view this version".
- A banner says "uncommitted changes" when the working tree differs from HEAD, and links to that diff.
- A roadmap page shows Now / Next / Later as three columns, each item linking to the doc it references.
- A diagrams page shows every diagram in a grid, each linking to the doc and section it comes from.
- A search box sits in the header, with keyboard shortcut `/`.

### Done when
For any doc you can see who changed it, when and what changed. The roadmap and diagrams pages render from the real docs.

---

## Phase 4: Feedback loop, option A (`/inbox`)

### Database (migration 2)
```sql
CREATE TABLE feedback (
  id           INTEGER PRIMARY KEY,
  kind         TEXT NOT NULL CHECK (kind IN ('prompt','review','comment')),
  doc_path     TEXT,                 -- NULL for a general prompt
  anchor       TEXT,                 -- JSON: {"heading": "...", "lines": [start, end], "quote": "..."}
  body         TEXT NOT NULL,
  status       TEXT NOT NULL DEFAULT 'open'
               CHECK (status IN ('open','in_progress','answered','resolved')),
  reply        TEXT,
  parent_id    INTEGER REFERENCES feedback(id) ON DELETE SET NULL,  -- follow-ups
  doc_rev      TEXT,                 -- git HEAD when the item was written
  created_at   TEXT NOT NULL,
  updated_at   TEXT NOT NULL,
  claimed_at   TEXT,
  answered_at  TEXT
);
CREATE INDEX feedback_status ON feedback(status, created_at);
```
- **Allowed status changes:**
  - `open → in_progress` through a claim,
  - `in_progress → answered` through a reply,
  - `answered → resolved` or back to `open` (reopen), changed by you,
  - `in_progress → open` (release).
  - Each change is one `UPDATE ... WHERE id=? AND status=?`, so two claims can't both win.
- **Follow-ups:** a follow-up is a new item with `parent_id` set. The UI shows a chain of items as one thread. This keeps ADR 0002's single `reply` column.

### API (all need a session)
| Method | Path | Notes |
|---|---|---|
| POST | `/api/feedback` | `{kind, doc_path?, anchor?, body, parent_id?}` |
| GET | `/api/feedback?status=&doc_path=` | list, newest first |
| GET | `/api/feedback/{id}` | one item plus its thread |
| POST | `/api/feedback/{id}/claim` | 409 if it isn't open |
| POST | `/api/feedback/{id}/reply` | `{reply}`; 409 if it isn't in progress |
| PATCH | `/api/feedback/{id}` | `{status}` (resolve, reopen, release) or `{body}` while still open |
| DELETE | `/api/feedback/{id}` | allowed only while open |

### Reaching Claude
- **CLI (`python -m app inbox ...`):** this works on the database directly. It's the same service on the same machine, so it needs no token (ADR 0002). Commands:
  - `list [--status open] [--json]`,
  - `show <id>`, which includes the doc excerpt around the anchor,
  - `claim <id>`,
  - `reply <id> --file <path>` or `reply <id> -`, which reads the reply from stdin,
  - `release <id>`,
  - `count`.
- **Telling the browser about CLI changes:** the CLI writes to the database without going through the API, so the backend can't see those changes directly. It checks `PRAGMA data_version` every 2 s and publishes `feedback.changed` when the number changes. Replies show up in the browser within a couple of seconds, without a page reload.
- **`/inbox` skill (`.claude/skills/inbox/SKILL.md`):**
  1. Run `inbox list --json`.
  2. For each item, oldest first: `claim`, then `show`, read the doc, and do what was asked (edit docs, answer the question).
  3. Write a reply that summarizes what changed, which files and why, and send it with `reply`.
  4. Leave committing to `/workspace-core:commit`, with your confirmation.
  - If the session can't finish an item, it `release`s it with a note.
- **SessionStart hook (`.claude/settings.json`):** runs `scripts/inbox-count.ps1`, which prints "Archeion: N open feedback items, run /inbox" when N > 0 and nothing otherwise. It stays silent when the backend environment isn't installed. This automates the existing `CLAUDE.md` rule to check feedback first.

### Frontend
- **On a doc:** hovering a block or heading shows a "comment" button, and selecting text adds a "comment on selection" option. Both open a form with the anchor already filled in (heading, lines, quoted text). The doc page has a side panel listing its items, and each item highlights its anchor.
- **Feedback page:** a list filtered by status and kind, a "new prompt" button for prompts not tied to a doc, and a thread view (item, Claude's reply rendered as Markdown, follow-up, resolve or reopen).
- **Header badge:** shows the number of open and answered items. A notification appears when a reply arrives.

### Tests
- The status changes, including two claims racing.
- The CLI round-trip against a temp database.
- The `data_version` check publishing an event.
- Anchor JSON validation.
- Frontend: the form fills in the anchor, and the thread renders.

### Done when
You leave a comment on a section in the browser, run `/inbox` in Claude Code, and the reply (plus the doc edit, live) appears in the browser.

---

## Phase 5: Ask Claude from the browser (option B), later
This phase starts only after phases 1 to 4 are stable and you've confirmed it. It's sketched here so the earlier phases don't block it.
- **Runs:** a `runs` table: `id`, `feedback_id`, `sdk_session_id`, `status`, `started_at`, `ended_at`, `changed_files`, `error`.
- **Starting a run:** `POST /api/feedback/{id}/run` starts the Python `claude-agent-sdk` with `cwd` set to the repo.
  - Only the Read, Glob, Grep, Edit and Write tools are allowed, with no shell.
  - A `can_use_tool` callback rejects any write outside `docs/`.
  - Only one run happens at a time (a lock), and a run starts only when `docs/` has no uncommitted changes, so "discard" can't destroy your own edits.
- **Streaming:** messages stream to the UI over the same SSE channel, and following up on a thread resumes `sdk_session_id`.
- **After a run:** the UI shows `git diff -- docs/`.
  - **Accept** commits through `git commit`, so the pre-commit hook still runs.
  - **Discard** restores only the files the run changed.
- **Credentials:** these come from the local Claude Code login or a key in `.env`, never from the database or a commit. Usage costs are covered in ADR 0002.

---

## Cross-cutting

### Security checklist (reviewed at the end of every phase)
- Every route except health and login requires auth, and a test enforces it.
- Only `docs/` is readable, and every path goes through one function.
- Git and other external commands are called with argument lists and validated input. No shell is ever used.
- No author emails, absolute paths or secrets appear in responses, logs or commits. Run `check-sensitive.ps1 -All` before each push.
- **Hook gotcha:** code like `password = "..."` with a long literal trips the secret pattern. Tests use short or generated values, and fixtures build passwords at runtime.

### Commit plan
Commits are small, follow Conventional Commits, and go through `/workspace-core:commit`. Examples:
- `build(backend): scaffold fastapi project with uv`
- `feat(auth): add scrypt password cli and session login`
- `feat(scripts): add start, stop and set_admin_password helpers`
- `feat(docs-api): serve doc tree and file content`
- `feat(viewer): render markdown and mermaid docs`
- `feat(events): push doc changes over sse`
- `feat(feedback): add feedback api and inbox cli`
- `feat(skills): add /inbox skill and session start hook`

### Docs to keep current
- `CLAUDE.md`: Commands, Environment, Architecture (drop the "not built yet" notes as things land) and Gotchas.
- `docs/roadmap/roadmap.md`: links to this plan, with the current phase under Now.
- A handoff note in `docs/notes/` at the end of each long session.

## Decisions on the open questions (2026-11-15)
1. **Install script:** add a root `setup.bat` (`uv sync` plus `npm install`). It's the fourth root helper.
2. **Windows:** keep two windows (backend and frontend dev server).
3. **What can be commented on:** only docs under `docs/`.
4. **Session length:** 12 hours idle and 7 days in total.
5. **Versioning:** Semantic Versioning `MAJOR.MINOR.PATCH`. See [ADR 0005](../decisions/0005-semantic-versioning.md).
