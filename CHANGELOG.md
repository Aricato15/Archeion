# Changelog

All notable changes to Archeion are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html) (see
[ADR 0005](docs/decisions/0005-semantic-versioning.md)).

## [Unreleased]

## [0.5.0] - 2026-11-15

### Added
- **A Settings page in the viewer** ([ADR 0010](docs/decisions/0010-manage-roots-and-registration-in-the-viewer.md)): add and remove named roots, applied without a restart and saved to `ARCHEION_ROOTS` in `.env` (the previous file is kept as `.env.bak`). Before a root that registered projects use is removed, the page says which projects.
- The same page lists the projects in each root, shows which are registered, and registers the others with a stub page in `registry/projects/`. It never overwrites a page and never touches the project.
- API: `GET`/`PUT /api/settings/roots`, `GET /api/registry/roots`, `POST /api/registry/projects`.
- **A Claude CLI panel in the viewer**: a panel on the right, opened and closed from the header (or Ctrl+I), that shows how to work with Claude from the terminal. Its content is the doc `docs/guides/claude-cli.md`, so it updates live and has a page of its own. The browser remembers whether it's open.
- **First-run setup in the viewer** ([ADR 0011](docs/decisions/0011-create-the-admin-password-in-the-viewer.md)): on a fresh start the login page asks you to create the admin password, then logs you in. It works only while no password exists, and only when the backend listens on this machine. `GET`/`POST /api/auth/setup`.

### Changed
- **No root is granted by default** ([ADR 0012](docs/decisions/0012-no-root-granted-by-default.md)). `ARCHEION_WORKSPACE_ROOT` is now empty by default, so a fresh start reads no projects until you add a root on the Settings page. When it's set, it still works as the root named `workspace`, and the Settings page can remove it. The CLI says when no root is granted.
- `start.bat` starts without an admin password, and says to create it in the viewer.
- Stub pages, from the viewer or `projects scan --write`, no longer set `verified`: nobody has checked them yet.
- `configure.bat` writes roots with forward slashes, so a folder in quotes (one with a space) can't be read back with `\n` or `\t` turned into escapes.

### Removed
- `set_admin_password.bat`. The first password is created in the viewer; to change or reset it, run `scripts/archeion.ps1 password set`.

### Fixed
- Registry pages saved with a UTF-8 byte-order mark (as PowerShell 5.1 and older Notepad save them) lost their frontmatter without a warning, so the project's path and root were ignored. The mark is now skipped.
- `--here` in a project whose root isn't granted on this machine said to register it. It now says the project may be registered with a root that isn't configured, and names it.

## [0.4.0] - 2026-11-15

### Added
- **The Archeion plugin** ([ADR 0009](docs/decisions/0009-archeion-plugin-for-project-sessions.md)), version 0.1.0, in `plugins/archeion/`. This repo is now also a plugin marketplace (`.claude-plugin/marketplace.json`) that you add at user scope. It gives every registered project's session `/archeion:inbox`, `/archeion:context`, `/archeion:ports` and `/archeion:report`, plus a SessionStart hook that announces waiting feedback. A launcher finds Archeion (`ARCHEION_HOME`, the marketplace's folder, or `../archeion`) and checks its version. The plugin is turned off in this repo.
- CLI commands for the plugin: `projects show --here|--project <name> [--json]`, `projects ports [--json]`, `inbox create [--to <project>] [--kind ...] --file <path>` and `version`.
- Migration 4: feedback items record the project whose session sent them (`origin`). The CLI and the viewer show it as "from <project>".
- The plugin has its own version: `scripts/bump-version.ps1 -Target plugin -Part ...` bumps `plugin.json`, the marketplace entry and the plugin's changelog together. The pre-commit hook refuses plugin changes without a version change (`.githooks/check-plugin-version.ps1`), and a test checks that the three agree.

### Removed
- `integrations/workspace-core/skills/project-inbox/`: replaced by the plugin's `/archeion:inbox`.

## [0.3.0] - 2026-11-15

### Added
- **Named roots** ([ADR 0008](docs/decisions/0008-named-project-roots.md)): `ARCHEION_ROOTS` (`name=folder;...`, edited and checked by `configure.bat`) grants Archeion more folders to read projects from, so a project can stay outside the workspace. A registry page picks one with `root: <name>`, and its `path` is then relative to that root. Bad entries and roots that aren't configured show as registry problems instead of failing. The viewer shows a project's root and why it's unavailable.
- `projects scan --root <name>` scans one root, and `--only <name> ...` registers just the named folders instead of every candidate.
- `backups/` is gitignored and blocked by the commit hook, for local copies of the registry and the database.
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
