# archeion

Repository (tracked on GitHub, no secrets or machine config) holding my system-wide point of view: how my projects interact with each other, architecture overviews, and the roadmap. It also has a local web app (backend + frontend) where I view these docs, plans and diagrams, and send prompts, reviews and feedback to Claude.

## Hard rules (never break these)
1. **Tracked on GitHub, so no configuration in commits.** The repo will be pushed to GitHub, but **I** set up the remote: don't add or change remotes. Never commit API keys, tokens, passwords, absolute paths (`<drive>:\...`, `/Users/...`, `/home/...`), email addresses or other personal information, `.env` files, databases or keys. Machine-specific values go in a gitignored `.env`, with a committed `.env.example` holding placeholders. Use paths relative to the repo. `.githooks/pre-commit` (running `.githooks/check-sensitive.ps1`) enforces this. Never skip it (`--no-verify`, `-n`) or change `core.hooksPath`. If it flags a harmless example, put `sensitive-ok` on that line. See `docs/decisions/0003-track-on-github-keep-configuration-out.md`.
2. **Root helper scripts.** The project root has `start.bat` (starts backend and frontend, each in its own window), `stop.bat` (stops them by port) and `set_admin_password.bat` (hidden prompt, stores only a hash). They work from any folder (`cd /d "%~dp0"`), and longer logic lives in `scripts/*.ps1`. `start.bat` refuses to start until an admin password is set. Keep these scripts working whenever the app changes.
3. **Authentication is enforced.** Every backend endpoint requires a logged-in admin session, except `GET /api/health` and `POST /api/auth/login`. The password is stored only as a salted scrypt hash in the backend's SQLite database, never in a file or `.env`. Sessions use an HttpOnly cookie. Changing the password logs out every session. The backend listens on `127.0.0.1` by default. The frontend shows a login page and nothing else until you're logged in. Claude's local access (`/inbox`) goes through the backend's own CLI, not an unauthenticated API.
4. **Backend + frontend.** The viewer is two parts that talk over HTTP: `app/backend/` (API) and `app/frontend/` (UI). The frontend never reads the filesystem directly. It goes through the backend API.
5. **The frontend shows my docs, plans and diagrams**, and the backend serves everything it needs: the doc tree, file content, Mermaid diagrams, roadmap, git history of each doc, and live updates when a file changes.
6. **Feedback loop with Claude.** Prompts, reviews and comments I write in the frontend are stored by the backend and reach Claude. Claude's replies and doc changes show up back in the frontend. See `docs/decisions/0002-viewer-app-and-claude-feedback-loop.md`.

## Purpose
Sessions here should:
- Build and maintain the system-level picture: what each project is, what it owns, and how they connect.
- Document cross-project interactions: APIs called, data owned, ports, events, dependencies.
- Plan the roadmap: what gets built next, in what order, and why.
- Build and maintain the viewer app in `app/`.

Don't edit sibling projects from this repo. When a sibling project's facts are needed (ports, APIs, stack), read them from that project's `CLAUDE.md`/`docs/` or `../PROJECTS.md`, and record what you learned here with a pointer to the source.

## Stack
- Docs: Markdown, diagrams as Mermaid code blocks.
- Backend (`app/backend/`): Python 3.12, FastAPI, uv, environment in `venv/`. SQLite for admin credentials, sessions, feedback and Claude runs. *(Proposed, not built yet.)*
- Frontend (`app/frontend/`): TypeScript, React, Vite, npm, Mantine (same as the workspace's other UIs). *(Proposed, not built yet.)*

## Ports
- Backend: **20300** (AI / Agent APIs range, because it drives Claude), set by `AOP_PORT`.
- Frontend dev server: **20301**, set by `AOP_FRONTEND_PORT`.

## Environment
- Docs: none.
- Backend: `app/backend/venv/`, created by `uv sync` with `UV_PROJECT_ENVIRONMENT=venv`. Database at `app/backend/data/archeion.db` (gitignored).
- Frontend: `app/frontend/node_modules/`, created by `npm install`.
- All of these must be listed in `.gitignore`.

## Commands
TODO: fill in once `app/` is scaffolded (install, run, test, lint for backend and frontend).
- Docs: before finishing, check that relative links between docs resolve.

## Architecture
- `docs/system/`: the system point of view. `overview.md` (the big picture) and `projects/<project>.md` (one page per project: purpose, owns, exposes, depends on).
- `docs/interactions/`: how projects talk to each other. `map.md` holds the dependency/interaction diagram; one file per notable flow or integration.
- `docs/roadmap/`: `roadmap.md` (now / next / later) plus dated plans for larger initiatives.
- `docs/decisions/`: architecture decisions as `NNNN-title.md` (ADRs).
- `docs/notes/`: session handoffs.
- `app/backend/`, `app/frontend/`: the viewer app (not built yet).
- `.githooks/pre-commit` + `check-sensitive.ps1`: blocks commits with secrets, absolute paths or personal info. Activated with `git config core.hooksPath .githooks`. Scan everything by hand with `powershell -NoProfile -ExecutionPolicy Bypass -File .githooks/check-sensitive.ps1 -All`.
- `start.bat`, `stop.bat`, `set_admin_password.bat` (root) and `scripts/` (their PowerShell helpers): not built yet.

## Conventions
- One fact lives in one place; link to it rather than copying it.
- Each project page records the date it was last verified against the real project.
- Use the workspace port ranges and database rules (`../CLAUDE.md`) as the baseline when describing or planning services.
- Roadmap items use absolute dates, never "next week".
- When starting a session, check for open feedback from the frontend (see ADR 0002) before other work.

## Gotchas
- `core.hooksPath` lives in `.git/config`, which isn't versioned. After every fresh clone, run `git config core.hooksPath .githooks`, or the sensitive-content check won't run.
- The check also runs on docs: describe other projects by repo-relative path (`../example-gateway`), never by drive path.
