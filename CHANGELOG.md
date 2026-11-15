# Changelog

All notable changes to Archeion are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html) (see
[ADR 0005](docs/decisions/0005-semantic-versioning.md)).

## [Unreleased]

### Added
- README section "Registering a project", with diagrams of where projects must sit (next to Archeion, in the workspace root), what `projects scan` finds or skips, and the steps from folder to registry page to viewer.
- Proposed [ADR 0008](docs/decisions/0008-named-project-roots.md): named roots granted in `.env`, so projects outside the workspace can be registered without moving.
- Proposed [ADR 0009](docs/decisions/0009-archeion-plugin-for-project-sessions.md): an Archeion plugin, installed at user level with its own version, for project sessions. The README describes the plan.

### Changed
- `stop.bat` shuts the servers down cleanly: it sends Ctrl+C, then Ctrl+Break, and kills a server only if it hasn't exited after 10 seconds. It then closes the two console windows `start.bat` opened, checks that both ports are free, and exits non-zero (and pauses) if something is still running. `start.bat` tags each window with its port so `stop.bat` can find it.

## [0.2.0] - 2026-11-15

Many projects, some related and some not, some with sub-projects ([ADR 0006](docs/decisions/0006-multi-project-registry.md)).

### Added
- **Project registry:** a page per project or sub-project in `registry/projects/`, with YAML frontmatter (`path`, `parent`, `group`, `status`, `kind`, `ports`, `depends_on`, `docs_dir`, `verified`), and a page per group in `registry/groups/`. The backend checks it and reports problems instead of failing.
- **Private registry folder** ([ADR 0007](docs/decisions/0007-keep-project-information-out-of-the-repo.md)): `registry/` is gitignored, and only the empty template `registry.example/` is committed. `setup.bat` creates `registry/` from the template, and the viewer shows it as the private "registry" source. The commit hook blocks files under `registry/` and the names of registered projects and workspace folders in committed text. `ARCHEION_REGISTRY_DIR` moves the folder.
- **Generated maps:** Mermaid diagrams drawn from the registry, one overall, one per group and one per project, so they can't drift.
- **Read-only project sources:** each registered project's README, CLAUDE.md, CHANGELOG, ROADMAP and docs folder are shown live, with history and diffs from its own git repo. Links between docs follow into other projects. Every docs route takes `source`.
- **Projects UI:** a projects overview (with warnings and unregistered folders), group pages, project pages (facts, map, sub-projects, notes, README, CLAUDE.md, docs and feedback), a project tree in the sidebar, and `/p/<project>/...` doc views.
- **Per-project feedback:** items record their project (migration 3), follow-ups inherit it, and the list can be filtered by project. The inbox CLI gains `--project` and `--here`. A portable `project-inbox` skill is in `integrations/workspace-core/`.
- **Roadmaps:** Archeion's cross-project roadmap plus each project's own, filterable by group or project.
- `projects list` and `projects scan [--write]` CLI commands, and the `ARCHEION_WORKSPACE_ROOT` setting (in `configure.bat`).
- Search and diagrams cover every source and can be filtered by one.
- `configure.bat`: an interactive editor for `.env`. It prompts for each setting (Enter keeps the current value), validates it (workspace port ranges, relative paths, numbers, distinct ports), shows a summary, and writes `.env`, keeping any unknown keys and saving the old file as `.env.bak`. Secret settings are prompted hidden.
- `scripts/settings.schema.json`: the single definition of every setting. `.env.example`, the script defaults and Vite's defaults all come from it, and a backend test keeps it in line with `config.py`.

### Changed
- `GET /api/roadmap` returns `{cross, projects}`, and diagram entries carry `source` and `code`.
- Archeion's `/inbox` and its SessionStart hook only handle Archeion's own items.
- The system overview, project pages and interaction notes moved from `docs/` into the private registry folder. The hand-drawn interaction map is replaced by the generated maps.
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
