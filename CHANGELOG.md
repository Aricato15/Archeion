# Changelog

All notable changes to Archeion are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html) (see
[ADR 0005](docs/decisions/0005-semantic-versioning.md)).

## [Unreleased]

### Added
- `configure.bat`: an interactive editor for `.env`. It prompts for each setting (Enter keeps the current value), validates it (workspace port ranges, relative paths, numbers, distinct ports), shows a summary, and writes `.env`, keeping any unknown keys and saving the old file as `.env.bak`. Secret settings are prompted hidden.
- `scripts/settings.schema.json`: the single definition of every setting. `.env.example`, the script defaults and Vite's defaults all come from it, and a backend test keeps it in line with `config.py`.

### Changed
- `setup.bat` regenerates `.env.example` from the schema instead of copying it to `.env`. Without a `.env`, the defaults apply.

## [0.1.0] - 2026-11-15

First version of the viewer app, covering phases 0–4 of the
[viewer app plan](docs/roadmap/2026-11-15-viewer-app-plan.md).

### Added
- **Backend** (`app/backend/`, FastAPI on port 20300): the doc tree, Markdown files and images from `docs/`
  only, git history and diffs of each doc (author emails never sent), the parsed roadmap, every Mermaid
  diagram, full-text search, and live updates over server-sent events.
- **Authentication:** one admin account with a salted scrypt hash in SQLite, HttpOnly `SameSite=Strict`
  session cookies (12 h idle, 7 days at most), a login rate limit, an Origin check on every state-changing
  request, a trusted-host check, and a test that fails if any route other than health and login answers
  without a session.
- **Frontend** (`app/frontend/`, React, Vite and Mantine on port 20301): a login page, a doc tree, rendered
  Markdown with Mermaid diagrams, a table of contents, history and diffs (inline or side by side), the
  doc as of any commit, an "uncommitted changes" badge, and roadmap, diagram and search pages, all updating
  live.
- **Feedback loop (ADR 0002, option A):** comments on a block or a text selection, reviews and prompts,
  threads of follow-ups, and resolve, reopen, edit and delete. The backend CLI `inbox` commands, the `/inbox`
  skill and a SessionStart hook let a Claude Code session pick items up and reply, and the replies appear
  in the browser within seconds.
- **Root scripts:** `setup.bat`, `start.bat`, `stop.bat` and `set_admin_password.bat`, plus
  `scripts/archeion.ps1` (backend CLI) and `scripts/bump-version.ps1`.
- `VERSION` as the single source of the version number, checked against the manifests by a test.
