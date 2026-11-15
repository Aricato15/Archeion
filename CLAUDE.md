# Archeion

Repository (tracked on GitHub, no secrets or machine config) holding my system-wide point of view: how my projects interact with each other, architecture overviews, and the roadmap. It also has a local web app (backend + frontend) where I view these docs, plans and diagrams, and send prompts, reviews and feedback to Claude.

## Hard rules (never break these)
1. **Tracked on GitHub, so no configuration and no project information in commits.** Anything that names or describes a specific project goes in the gitignored `registry/` folder, never in `docs/`, code, tests or commit messages (ADR 0007). The repo is pushed to GitHub. Claude may add or change the remote and push only when I ask for it. Never commit API keys, tokens, passwords, absolute paths (`<drive>:\...`, `/Users/...`, `/home/...`), email addresses or other personal information, `.env` files, databases or keys. Machine-specific values go in a gitignored `.env`, with a committed `.env.example` holding placeholders. Use paths relative to the repo. `.githooks/pre-commit` (running `.githooks/check-sensitive.ps1`) enforces this. Never skip it (`--no-verify`, `-n`) or change `core.hooksPath`. If it flags a harmless example, put `sensitive-ok` on that line. See `docs/decisions/0003-track-on-github-keep-configuration-out.md`.
2. **Root helper scripts.** The project root has `setup.bat` (installs the backend venv and frontend node_modules), `configure.bat` (interactive editor for `.env`), `start.bat` (starts backend and frontend, each in its own window), and `stop.bat` (stops them by port). They work from any folder (`cd /d "%~dp0"`), and longer logic lives in `scripts/*.ps1`. `start.bat` always starts. On a fresh start the viewer asks for the admin password (ADR 0011). Keep these scripts working whenever the app changes.
3. **Authentication is enforced.** Every backend endpoint requires a logged-in admin session, except `GET /api/health`, `POST /api/auth/login` and first-run setup (`GET`/`POST /api/auth/setup`, which only creates the first password, only while none exists and only when the backend listens on loopback; ADR 0011). The password is stored only as a salted scrypt hash in the backend's SQLite database, never in a file or `.env`. Sessions use an HttpOnly cookie. Changing or resetting the password is done with the CLI (`password set`) and logs out every session. The backend listens on `127.0.0.1` by default. The frontend shows a login page and nothing else until you're logged in. Claude's local access (`/inbox`) goes through the backend's own CLI, not an unauthenticated API.
4. **Backend + frontend.** The viewer is two parts that talk over HTTP: `app/backend/` (API) and `app/frontend/` (UI). The frontend never reads the filesystem directly. It goes through the backend API.
5. **The frontend shows my docs, plans and diagrams**, and the backend serves everything it needs: the doc tree, file content, Mermaid diagrams, roadmap, git history of each doc, and live updates when a file changes. Besides this repo's `docs/`, it serves **read-only** each registered project's `README.md`, `CLAUDE.md`, `CHANGELOG.md`, `ROADMAP.md` and docs folder, and nothing else of it, and it never writes to a project (`docs/decisions/0006-multi-project-registry.md`).
6. **Feedback loop with Claude.** Prompts, reviews and comments I write in the frontend are stored by the backend and reach Claude. Claude's replies and doc changes show up back in the frontend. Each item targets a project: this repo's `/inbox` handles Archeion's own items, and each project's session handles its own (ADR 0006). See `docs/decisions/0002-viewer-app-and-claude-feedback-loop.md`.

## Purpose
Sessions here should:
- Build and maintain the system-level picture: what each project is, what it owns, and how they connect.
- Document cross-project interactions: APIs called, data owned, ports, events, dependencies.
- Plan the roadmap: what gets built next, in what order, and why.
- Build and maintain the viewer app in `app/`.

Don't edit sibling projects from this repo. When a sibling project's facts are needed (ports, APIs, stack), read them from that project's `CLAUDE.md`/`docs/` or `../PROJECTS.md`, and record what you learned here with a pointer to the source.

## Stack
- Docs: Markdown, diagrams as Mermaid code blocks.
- Backend (`app/backend/`): Python 3.12, FastAPI, uvicorn, pydantic-settings, watchfiles, stdlib `sqlite3` (no ORM), uv with the environment in `venv/`. SQLite holds the admin credential hash, sessions and feedback. Lint with ruff, test with pytest.
- Frontend (`app/frontend/`): TypeScript, React, Vite, npm, Mantine, React Router, TanStack Query, react-markdown, mermaid, diff2html. Lint with oxlint, test with vitest (jsdom).
- Details and reasons are in `docs/decisions/0004-viewer-app-stack-and-layout.md`.
- Version: Semantic Versioning, with `VERSION` as the single source (`docs/decisions/0005-semantic-versioning.md`). Bump it with `scripts/bump-version.ps1 -Part major|minor|patch` and record every change in `CHANGELOG.md` (under `## [Unreleased]` until a release).

## Ports
- Backend: **20300** (AI / Agent APIs range, because it drives Claude), set by `ARCHEION_PORT`.
- Frontend dev server: **20301**, set by `ARCHEION_FRONTEND_PORT`.

## Environment
- Docs: none.
- Backend: `app/backend/venv/`, created by `uv sync` with `UV_PROJECT_ENVIRONMENT=venv`. Database at `app/backend/data/archeion.db` (gitignored).
- Frontend: `app/frontend/node_modules/`, created by `npm ci` (`setup.bat` does both installs).
- Config: the repo-root `.env` (gitignored, `ARCHEION_*` variables). Both the backend and Vite read it. Every setting is defined once in `scripts/settings.schema.json`: `configure.bat` prompts for and validates each one, writes `.env`, and regenerates `.env.example` from the schema (so never edit `.env.example` by hand). To add a setting, add a schema entry, plus a field in `app/backend/app/config.py` if the backend reads it. `tests/test_settings_schema.py` fails if the two drift.
- All of these must be listed in `.gitignore`.

## Commands
- Install: `setup.bat`. Change settings: `configure.bat`. Run: `start.bat`, then open the frontend at port 20301 (the first time, it asks you to create the admin password). Reset the password: `scripts/archeion.ps1 password set`. Stop: `stop.bat`.
- Backend (from `app/backend/`, with `UV_PROJECT_ENVIRONMENT=venv` set): `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`.
- Frontend (from `app/frontend/`): `npm test`, `npm run lint`, `npm run typecheck`, `npm run build`.
- Backend CLI (from the root): `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/archeion.ps1 <serve|password ...|inbox ...|projects ...|version>`.
- Versions: the app with `scripts/bump-version.ps1 -Part major|minor|patch`, the plugin with `-Target plugin -Part ...`. They're independent (ADR 0005, ADR 0009).
- Feedback: `/inbox` (project skill in `.claude/skills/inbox/`) works through what was written in the viewer.
- Docs: before finishing, check that relative links between docs resolve.

## Architecture
- `registry/` (**gitignored, private**; ADR 0007): the system point of view. It holds `overview.md` (the big picture), `projects/<project>.md` (one page per project or sub-project: structural facts in YAML frontmatter, cross-project notes in the body; format in `projects/README.md`), `groups/<group>.md` (one page per system of related projects) and `interactions/` (notable cross-project flows). The maps are generated from the frontmatter, not drawn by hand. The viewer shows the folder as the `registry` source.
- `registry.example/` (committed): the empty template `setup.bat` copies to `registry/`. Keep it generic. Only `example-*` names, never a real project.
- `docs/roadmap/`: `roadmap.md` (now / next / later) plus dated plans for larger initiatives.
- `docs/decisions/`: architecture decisions as `NNNN-title.md` (ADRs).
- `docs/notes/`: session handoffs.
- `docs/guides/claude-cli.md`: the terminal workflow, shown in the viewer's Claude CLI panel (`app/frontend/src/layout/GuidePanel.tsx`). Update it whenever a skill, plugin skill or CLI command is added, renamed or removed.
- `app/backend/app/`: `main.py` (app factory, Origin guard, error mapping, routers behind the session dependency), `config.py`, `db.py` (pragmas, `BEGIN IMMEDIATE`, migrations by `PRAGMA user_version`), `security.py` (scrypt, sessions, rate limit), `paths.py` (the one doc-path check every route uses), `routers/`, `services/` (`docs_fs`, `git`, `events`, `feedback`), `__main__.py` (CLI).
- `app/frontend/src/`: `api/` (fetch client, typed queries), `auth/`, `layout/` (shell, doc tree, feedback badge), `docs/` (Markdown, Mermaid, comment anchors, history and diffs), `feedback/`, `pages/` (roadmap, diagrams, search), `events/` (SSE → query invalidation).
- `app/backend/app/services/registry.py` (registry pages, checks, discovery), `roots.py` (the named roots from `ARCHEION_ROOTS`, ADR 0008) and `sources.py` (doc sources: `archeion` plus one read-only source per registered project, with its file allowlist). Every docs route takes `source` (default `archeion`).
- `app/backend/app/routers/manage.py` (ADR 0010): the Settings page's API. The backend's only file writes: the `ARCHEION_ROOTS` line of `.env` (`roots.py: write_env_roots`, keeps `.env.bak`) and new pages in `registry/projects/` (`registry.py: register`, create-only, only for folders discovery found). Never a project's files, never an existing page.
- `app/frontend/src/projects/`: projects overview, group and project pages, and `map.ts`, which generates the Mermaid maps from the registry. `docs/links.ts` resolves links across sources.
- Live updates: watchfiles (project roots without recursion, docs folders with recursion, restarted when the registry changes) and a `PRAGMA data_version` check on the feedback table publish to an in-process bus, which `GET /api/events` streams over SSE.
- `.claude-plugin/marketplace.json` + `plugins/archeion/` (ADR 0009): the plugin for sessions in registered projects (`/archeion:inbox`, `context`, `ports`, `report`, a SessionStart hook), installed by the user at user scope. `plugins/archeion/scripts/archeion.ps1` finds Archeion and checks its minimum version (`$MinArcheion`). It has its own SemVer and changelog. Never copy its skills into projects.
- `.githooks/pre-commit` runs `check-sensitive.ps1` (blocks commits with secrets, absolute paths or personal info) and `check-plugin-version.ps1` (blocks plugin changes without a plugin version change). Activated with `git config core.hooksPath .githooks`. Scan everything by hand with `powershell -NoProfile -ExecutionPolicy Bypass -File .githooks/check-sensitive.ps1 -All`.
- `setup.bat`, `configure.bat`, `start.bat`, `stop.bat` (root) and `scripts/` (`common.ps1`, `setup.ps1`, `configure.ps1`, `settings.schema.json`, `start.ps1`, `stop.ps1`, `send-ctrl-c.ps1`, `archeion.ps1`, `inbox-count.ps1`, `bump-version.ps1`).
- `.claude/settings.json` runs `scripts/inbox-count.ps1` as a SessionStart hook, which announces open feedback.

## Conventions
- One fact lives in one place; link to it rather than copying it.
- Each registry page records `verified:` (the date its frontmatter was last checked against the real project). Facts that belong to a project (endpoints, commands, internals) stay in that project's own docs, which the viewer shows live. Link to them, don't copy them.
- New projects: the viewer's Settings page (roots and a Register button per folder), or `scripts/archeion.ps1 projects scan` (dry run), then `--write` for stub pages. `projects list` shows the tree and problems.
- Use the workspace port ranges and database rules (`../CLAUDE.md`) as the baseline when describing or planning services.
- Roadmap items use absolute dates, never "next week".
- When starting a session, check for open feedback from the frontend (see ADR 0002) before other work: `inbox list --project archeion`.

## Gotchas
- `core.hooksPath` lives in `.git/config`, which isn't versioned. After every fresh clone, run `git config core.hooksPath .githooks`, or the sensitive-content check won't run.
- The check also runs on docs: describe other projects by repo-relative path (`../<project>`), never by drive path. It also blocks the names of registered projects and workspace folders in committed text, using names it reads from the private `registry/` at commit time (ADR 0007).
- The check also runs on code. A line like `token = something_long` or `password: some.value` trips its secret pattern even when nothing secret is in it. Name such variables `raw`, `pw`, `secret` and so on, and generate test passwords at runtime (`tests/conftest.py: make_pw`). <!-- sensitive-ok: example of what trips the check -->
- `.claude/settings.json` denies reading `.env.*`, and that covers `.env.example` too, so Claude can't write it. It's generated anyway: change `scripts/settings.schema.json`, then run `configure.bat` (or `scripts\configure.ps1 -ExampleOnly`).
- FastAPI 0.163 keeps included routers as `_IncludedRouter` objects, so `app.routes` isn't flat. `tests/test_auth_required.py` walks `app.openapi()["paths"]` instead.
- Project sources are read at runtime from the named roots in `ARCHEION_ROOTS` (ADR 0008) and, if set, `ARCHEION_WORKSPACE_ROOT` (empty by default: nothing is granted until a root is added, ADR 0012). Tests set `workspace_root=".."` themselves. Registry `path`s must be relative and stay inside their root: relative to this repo without `root:`, relative to the root with it. The commit hook doesn't read `.env`; it blocks registered projects' names whatever their root. Nothing from a project is ever copied into this repo, which is what keeps publishing Archeion from publishing the projects.
- `inbox --here` needs the caller's folder. `scripts/archeion.ps1` passes it as `ARCHEION_CALLER_DIR`, because the CLI itself runs from `app/backend/`.
- The SessionStart hook uses a relative path (`scripts/inbox-count.ps1`), so it only fires when Claude Code starts at the repo root.
- Claude Code runs the Archeion plugin from a cached copy per version, so an edit under `plugins/archeion/` reaches project sessions only after a plugin version bump, `/plugin marketplace update archeion` and a plugin update. The plugin is turned off in this repo, so test it from a registered project's session.
- uv only reads `UV_PROJECT_ENVIRONMENT` from the environment. Set it to `venv` before any `uv` command in `app/backend/`, or uv creates a second `.venv/`.
