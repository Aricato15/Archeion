# 0004: Viewer app stack and layout

- Status: Accepted
- Date: 2026-11-15

## Context
[ADR 0002](0002-viewer-app-and-claude-feedback-loop.md) settles the shape of the viewer app. Before writing code, the stack and a few layout choices need pinning down so later sessions don't drift.

## Decision
- **Backend:** `app/backend/`, Python 3.12, FastAPI, uvicorn, pydantic-settings and watchfiles. The database is the standard-library `sqlite3` with migrations numbered by `PRAGMA user_version`, and no ORM. Password hashing uses `hashlib.scrypt`. Lint with ruff and test with pytest.
- **Backend environment:** the venv lives in `app/backend/venv/` (`UV_PROJECT_ENVIRONMENT=venv`). That's a deliberate exception to the workspace default `.venv/`, matching the workspace's other backends. Every script sets the variable before calling `uv`.
- **CLI:** `python -m app` (run from `app/backend/`) is the single entry point: `serve`, `password ...` and `inbox ...`. The root scripts and the `/inbox` skill go through `scripts/archeion.ps1`, which runs the venv's python directly.
- **Frontend:** `app/frontend/`, Vite, React, TypeScript, Mantine, React Router, TanStack Query, react-markdown with remark-gfm and rehype-slug, mermaid (lazy-loaded) and diff2html. Lint with oxlint and test with vitest. The versions match the workspace's other UIs.
- **One origin in development:** the Vite dev server (20301) proxies `/api` to the backend (20300). The browser only ever talks to one origin, so there's no CORS, and the `SameSite=Strict` session cookie works without extra setup.
- **Config:** a single `.env` at the repo root (gitignored). Paths in it are relative to the repo root. Every setting is defined in `scripts/settings.schema.json`: `configure.bat` uses it to prompt for, validate and write `.env`, and generates `.env.example` from it, so adding a setting later only means adding a schema entry.

## Consequences
- Running the app needs two processes, which `start.bat` opens in two windows.
- Anything the CLI changes in the database reaches the browser through the backend's `PRAGMA data_version` check, not through the API.
