# Changelog

All notable changes to Archeion are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html) (see
[ADR 0005](docs/decisions/0005-semantic-versioning.md)).

## [Unreleased]

## [1.4.0] - 2026-11-19

### Added
- **Every diagram has a full screen mode.** The component and project maps, the activity and state diagrams, the data schema and the interactive flow views get a **Full screen** button, as the Mermaid diagrams already had. The window fills the screen, keeps zoom, pan and Find, and closes with Escape. A click on a box or a participant closes it first and shows what you picked.
- **Remove a registered project** ([ADR 0026](docs/decisions/0026-remove-a-registered-project.md)): a **Remove** button on the project page and next to each registered folder in Settings, `projects remove <name>` in the CLI, and `DELETE /api/registry/projects/{name}`. Its registry page moves to `registry/removed/`, so it can be put back, and the project's own folder and its studies, designs, glossary, reports and feedback are left alone. A project that still has modules can't be removed. Settings lists removed projects under **Previously registered**, with **Restore** and **Delete permanently** (which also deletes the studies, designs, glossary and reports kept for it, after asking), and a folder that was registered before shows a *previously registered as* badge. CLI: `projects removed`, `restore`, `purge --yes`.
- **A table of contents for long threads.** A thread with more than one message has a panel on the right with a numbered button per message, which scrolls to it and marks the one you're reading, plus **Top** and **Latest** buttons. On narrow windows, where the panel is hidden, a round button at the corner goes to the latest message.

## [1.3.2] - 2026-11-18

### Added
- **`docs/updates/`**, the home of the update notes: one short how-to per release that asks the user to do something, starting with [`update-v1.3.1.md`](docs/updates/update-v1.3.1.md) (update Archeion, update the plugin, open a new session in each project, check it worked). Its README sets the convention and has a template. The viewer shows them with the other docs, and the [update guide](docs/guides/update_archeion_and_plugin.md) links to them.

### Changed
- **The Edits setting's default now launches Claude in `--permission-mode auto`** (it was `acceptEdits`), for the inbox terminal and for on-demand runs, windowed or headless. It's labeled **Auto mode** in Settings -> Claude jobs. The other choice, *Seek user confirmations*, is unchanged. The stored value is still `accept_edits`, so your setting carries over. There is no database migration ([ADR 0021](docs/decisions/0021-claude-jobs-windows-headless-and-limits.md)).

### Fixed
- **Diagrams no longer redraw by themselves** on the roadmap, changelog, user guide and every other doc. The markdown renderer rebuilt its components on each render, which remounted every Mermaid diagram on hover, on a refetch after a file change and when the window regained focus.
- **A guided report's plan now shows under the project's Reports tab**, with its approve, reorder and discard controls and the build progress, not only inside the Report dialog.

## [1.3.1] - 2026-11-18

### Changed
- **The plugin's `/archeion:report` is now `/archeion:notify`** (plugin 0.4.0). Archeion has its own `/report` now, which makes a PDF of a project ([ADR 0025](docs/decisions/0025-project-pdf-reports.md)), and the two names meant different things. The skill is unchanged apart from its name: it tells Archeion about a change, or asks it a question, in its inbox, and carries on a thread. Update the plugin and open a new session in each project ([the update guide](docs/guides/update_archeion_and_plugin.md)). The docs, the use cases and the CLI guide use the new name.

### Fixed
- The use cases guide was committed with Windows line endings while every other file uses Unix ones, which made its diff look like a rewrite of the whole file. It now matches the rest, so `git blame` and diffs show only real changes.

## [1.3.0] - 2026-11-18

### Added
- **PDF reports of a project** ([ADR 0025](docs/decisions/0025-project-pdf-reports.md), [the plan](docs/roadmap/2026-11-17-project-report-plan.md)). The **Report** button on a project page opens a dialog with two ways to make one, and a **Reports** tab lists what was built (open it in its own tab, download, check it against its build record, delete). Reports are kept in the private registry (`registry/reports/<project>/`) and never committed.
  - **Standard** (`/report <project>`): you pick the sections and drag them into order, with a checkbox per section and per sub-system diagram, a title, page size, orientation, cover page and contents, and saved presets. It needs no Claude and gives the same PDF for the same choices. Sections come from the project's registry page, docs, code study, design, glossary and place in its group. A section with no source is greyed out with the reason.
  - **Guided** (`/report-guided <project>`): you describe what you need (audience, purpose, emphasis) and may give an outline. **Ask Claude to plan the report** starts a thread; Claude reads the sources and drafts a plan with an executive summary and any other sections you asked for, each labeled "Written by Claude" and citing the sections it came from. Before asking, you can untick sections to limit what Claude may use; the request carries that list and Claude stays inside it. You review the plan in the dialog (reorder, drop, add sections back from the same checklist, read what Claude wrote), ask for changes in the thread, and press **Approve and build**. Sourced sections are never rewritten.
  - **Every diagram is in the PDF as vector.** The component map is compact (the top level), and every sub-system gets its own diagram. Flows, logic, states and the data schema are drawn in full. A diagram too wide for a portrait page gets a landscape page. Pages are numbered.
  - **How it's built:** headless Edge prints the frontend's print page (`/print/report/:project`), with a session of its own that is deleted afterwards. It needs the frontend running (`start.bat`). New setting `ARCHEION_REPORT_BROWSER` for an Edge that isn't found on its own. New process: headless Edge, for the length of a build.
  - **CLI:** `report preflight|catalog|default|validate|read|build|list|verify`, `report preset list|show|save|delete`, `report plan save|show|discard|approve`. **API:** `/api/reports/{project}/...` (catalog, preflight, presets, plan, build, builds, files). A thread can now be anchored to a `report` task.
  - New dependencies: `@dnd-kit` for dragging sections into order, and `websockets` (already installed with uvicorn) for driving Edge.
- **A home page** (the Home link, and the Archeion logo). It opens on **What's changed in Archeion**: every release in Archeion's own `CHANGELOG.md`, newest first (Unreleased notes first). It shows the file as written, from the commit that's checked out, so it follows the branch you're on. New read-only endpoint `GET /api/changelog` reads the repo's root `CHANGELOG.md`, because the docs source is `docs/` only. A switch changes it to **Projects**, which lists the releases of every registered project that keeps a `CHANGELOG.md`, newest first, with a project filter. Projects without a changelog are skipped. It used to open on the README.

### Changed
- The interactive flow view now looks like the maps: a bordered canvas with the same dotted grid, zoom controls at the bottom left and the Find box at the top left, participants with a coloured edge by component kind, and `alt`/`loop` blocks drawn as tinted containers.

## [1.2.0] - 2026-11-17

### Changed
- **Maps are easier to read** (proposal: [keeping the maps readable](docs/roadmap/2026-11-17-diagram-scaling-proposal.md)). Lines now follow the routes ELK finds around the boxes instead of cutting through them, edge labels get room in the layout, and box widths are measured from the real font. Past 40 edges the labels show only for the hovered box, and past 60 the lines are faint until you hover. Every map has a **Find a box** search that opens the boxes hiding a match and zooms to it.
- **Interactive flows, logic and states, with a Mermaid switch** ([ADR 0024](docs/decisions/0024-interactive-study-views.md)). In the Study tab (and the Design tab's components and flows) each of these opens as an interactive view, and an **Interactive / Mermaid** switch (remembered) shows the Mermaid drawing instead. Flows are an interactive sequence diagram: hover a participant to see only its messages, hover a message for who it joins and its full text, click a participant to open the component, search, zoom and pan. Logic and states are graphs like the component maps (hover, search, zoom). Clicking a box opens a side panel in place and stays on the diagram: a participant opens its component's details (with a **Show in the component map** button that opens the map around that component, highlighted), a state or an activity step shows what leads into it and out of it. The Find and zoom controls of a Mermaid diagram now sit above it instead of over its labels.
- **Mermaid diagrams are interactive.** Every one (flows, activities, ER, states, and the diagrams in docs and in the Design tab) has a **Find** box that highlights matching labels (ignoring case) and dims the rest, **Enter** pans the first match to the middle and **Esc** clears it. Hovering a box or label lights up every label with the same text, such as a participant's name at the top and bottom of a sequence diagram. Dragging no longer selects the text.
- The wheel zooms every Mermaid diagram (flows, ER, states) when the pointer is over it. It used to need Ctrl inline and scrolled the page.
- `study validate`, `study save` and `study draft save` warn when a level of the component tree holds more than 12 components, and the `/study` and `/design` skills now tell Claude to shape the tree top-down with named sub-groups of about 5 to 9.

### Added
- **A Glossary tab on each project page** ([ADR 0023](docs/decisions/0023-project-glossaries.md)). It keeps the project's terms and jargon with what they mean, and its search box matches names, aliases and meanings, ignoring case. Add, edit and delete terms in the viewer. They're kept in the private registry (`registry/glossary/<project>.json`). Claude fills it with the CLI `glossary list|set|remove <project>`. API: `GET`/`POST /api/glossary/{project}`, `PUT`/`DELETE /api/glossary/{project}/{term}`.

## [1.1.0] - 2026-11-17

### Added
- **Design and plan a project** ([ADR 0022](docs/decisions/0022-design-and-plan-a-project.md), [the plan](docs/roadmap/2026-11-17-design-and-plan-plan.md)). A registered project, empty or with just a `CLAUDE.md`, gets its purpose, architecture, plan and decisions worked out in Archeion with the rest of the system in view, then handed back to build. The project page has a **Design** tab: **Ask Claude to design** starts a conversation (a thread for Archeion, answered by the new `/design <project>` skill through `/inbox` or on-demand Claude), and the content is kept in the private registry as a living design (`registry/designs/<project>/<slug>/`: brief, architecture, plan, open questions, decisions and a model in the study schema, so the diagrams are generated). You move it through brief, architecture and plan yourself and **Approve** it, which shows which lines of the project's registry page change (ports and `depends_on` added, group and kind filled in), writes them and freezes an immutable revision. **Hand off** asks the inbox to copy the revision as a package into the project's `.archeion/designs/<slug>/`, which the project's own session turns into its docs with `/archeion:consume-design` (plugin 0.3.0): the design, its decisions as ADRs, the plan in the roadmap and additions to `CLAUDE.md`. It does nothing without a package. Skills check their own setup first (`design preflight`) and fix what they can after asking. The tab also lists what the design asks of other projects (with a button to send each a note) and compares the design with the latest study (built vs designed), and a planned project's arrows are dashed on the maps. CLI: `design preflight|context|init|show|list|validate|save|stage|approve|handoff|package|consumed|discard`. API: `/api/designs`. A slug allows several designs per project.
- **Conversations from a session** ([ADR 0018](docs/decisions/0018-feedback-threads.md)). The inbox CLI can carry on a thread, so a project session's `/archeion:report` and `/archeion:inbox` (plugin 0.2.0) work as a reply in the viewer does instead of starting a new item each time: `inbox create --in <id>` adds the next message to a thread (keeping its project and kind; `--claim` adds it already claimed, so on-demand Claude doesn't pick up a message the session answers itself), `inbox threads` lists conversations one row per thread (`--here`, `--from-here` for the threads a project started, `--status active|...|all`), and `inbox resolve <id>` closes a thread. `claim`, `release`, `reply`, `create`, `resolve` and `show` print a fixed `ids: item #N, thread #T` line, and take `--json` (`show --json` adds `id`, `thread_id` and `latest_id`), so a session reads the ids instead of guessing them. Archeion's own `/inbox` records chat follow-ups the same way.
- `restart.bat` stops Archeion (as `stop.bat` does) and starts it again (as `start.bat` does). If something couldn't be stopped, it says so and doesn't start.

## [1.0.0] - 2026-11-16

### Added
- **Studies are conversations** ([ADR 0020](docs/decisions/0020-study-conversations-and-on-demand-claude.md)). **Ask Claude to study** (and **Ask for a refresh**) on the Study tab starts a thread for Archeion anchored to the study (`anchor.task`), with an optional focus. Each round, Claude reports its findings, asks what the code doesn't answer, and keeps its work as a draft (`study draft save|show|discard`) that the Study tab shows as **Draft**, diagrams included. You answer in the thread, and when you say it's done Claude saves it (`study save --from-draft`, which keeps the thread) and updates the registry page. The Study tab links each snapshot to its conversation.
- **Claude jobs** ([ADR 0021](docs/decisions/0021-claude-jobs-windows-headless-and-limits.md)). On-demand runs now open an interactive session through `cmd /c claude "/inbox"`, so you can watch Claude think, read and edit, and approve a command it may not run alone. The Stop hook (`scripts/on-demand-done.ps1`) tells the backend when the turn ends, and the backend closes the window. **Settings → Claude jobs** has **Headless** (no window: `claude -p` with every event logged as stream-json) and **Max Claude instances** (1 or 2, default 1), which counts the inbox terminal and every on-demand run. With 2 they work side by side, or two on-demand runs answer in parallel. The inbox terminal also opens through `cmd`. `scripts/respond.ps1` is gone. Database migration 9 adds `claude_jobs`. `PUT /api/responder` takes `enabled`, `headless`, `max_instances` and `accept_edits`. **Edits** (Settings → Claude jobs): **Auto accept edits** (the default) or **Seek user confirmations**, for both the inbox terminal and on-demand runs. Confirmations can't be combined with Headless. The inbox terminal used to always ask, and now follows this setting (migration 10).
- **On-demand Claude** (ADR 0020). **Settings → On-demand Claude**: when it's switched on, the backend opens a window running `claude -p "/inbox"` as soon as a new message waits, and the window closes when the run ends. A message written during a run starts another after it, and messages Claude left open don't start one. **Run now** runs it once. Edits are accepted and Archeion's CLI is allowed; other commands aren't, and Claude says so. Logs are in `app/backend/data/responder/`. It never runs alongside the inbox terminal: each refuses to start while the other is on or running. A header badge shows it. API: `GET`/`PUT /api/responder`, `POST /api/responder/run`, `POST /api/responder/stop`. Database migration 8 adds the `responder` table.
- **Studies across projects** (ADR 0019). `GET /api/system/links` matches each latest study's outgoing calls to other registered projects, by name or port, and to the endpoints their own studies expose. The maps draw these links, and the Projects page and each project page warn when the code and `depends_on` disagree. **Search** also finds study elements (components, endpoints, tables, flows, findings) through `GET /api/studies/search`, linking straight to them. The **Diagrams** page filters by diagram kind.
- **Ask Claude about a study element.** The details of a component, flow, activity, state machine or finding have an **Ask Claude about this** button. It sends a prompt to Archeion's inbox anchored to that element (`anchor.study`, no doc needed), and `inbox show` prints the element from its snapshot. The feedback card links back to the element in the Study tab.
- **Code studies** ([ADR 0019](docs/decisions/0019-code-studies.md)). `/study <project>` in Archeion's session reads a registered project's code read-only and saves what it learns as a dated, immutable snapshot in `registry/studies/<project>/<date>-<commit7>/`. The snapshot holds a validated model (components, relations, exposed and outgoing interfaces, entities, flows, activities, states, findings, each with citations to the code) and a narrative. It shows its plan and the registry changes it proposes before writing, unless given `--yes`, and `--refresh` rereads only what changed since the last snapshot. `/inbox` routes study requests to it and sends the plan as its reply. The project page has a new **Study** tab: overview, a nested component map you can focus into, a sequence diagram per flow, activity, ER and state diagrams, interfaces, findings, notes and the changes between snapshots, with a snapshot picker and a "commits behind" badge. Every diagram is generated from the model. CLI: `study scan|validate|save|list|show|changes`. API: `GET /api/studies`, `/api/studies/{project}`, `/api/studies/{project}/{snapshot}`, `/api/studies/{project}/diff`. New setting: `ARCHEION_STUDY_KEEP` (default 10).
- **The inbox terminal, started from the viewer** ([ADR 0013](docs/decisions/0013-start-the-inbox-terminal-from-the-viewer.md)). **Settings → Inbox terminal** opens a Claude Code window at the repo root running `/loop <interval> /inbox`, and stops or restarts it. The backend tracks the window by PID and process start time, so the status survives a backend restart. The interval is set on the card. A header badge shows whether it's running. API: `GET`/`PUT /api/runner`, `POST /api/runner/start`, `POST /api/runner/stop`.
- **Diagrams for system design** ([ADR 0014](docs/decisions/0014-diagrams-for-system-design.md)): Mermaid diagrams can use the ELK layout (`layout: elk` in the diagram's frontmatter) and icons from the `logos:` and `mdi:` packs in `architecture-beta` diagrams and flowchart icon nodes. Each extra loads only when a diagram uses it. How to write them: `docs/guides/diagrams.md`.
- **Projects and modules** ([ADR 0016](docs/decisions/0016-projects-and-modules.md)). A project has its own git repository, and a module is a part of one. Without `type:` on its registry page, a page with `parent:` and no `.git` of its own is a module. Set it by hand on the project page (Auto / Project / Module), when registering on the Settings page, or with `projects type <name> project|module|auto`. Modules get a puzzle icon in the sidebar, a "module of …" badge, their own **Modules** section on their project's page, and rounded boxes on the maps. API: `PUT /api/registry/projects/{id}/type`, plus `type` on `POST /api/registry/projects`.
- **Archeion's inbox can work on any registered project** ([ADR 0017](docs/decisions/0017-inbox-may-edit-registered-projects.md)). `/inbox` now handles every project's items. For a project's item it reads that project's `CLAUDE.md`, edits its files, runs its tests and leaves the changes uncommitted there. `inbox_edits: true|false` on the registry page allows or forbids it (allowed when left out, and a module follows its project). Switch it on the project page (Auto / Allowed / Not allowed) or with `projects inbox-edits <name> on|off|auto`. New project pages get `inbox_edits: true`. `inbox show` names the target project, its folder and whether edits are allowed. API: `PUT /api/registry/projects/{id}/inbox-edits`.
- **A Use cases page** in the sidebar: everyday jobs, step by step, across the viewer, Archeion's session and a project's session. These are registering a project and keeping its docs current, reviewing changes that affect other projects, and starting a new project from a clean slate. It's the doc `docs/guides/use-cases.md`.

- **Feedback is a thread** ([ADR 0018](docs/decisions/0018-feedback-threads.md)). Reply to Claude in a box under the conversation instead of opening a new prompt. The backend hands Claude the whole conversation: `inbox show` on a reply prints every earlier message and reply in full, with the first message's quote and doc excerpt, and marks the one to answer (`conversation` in `--json`). A reply keeps its thread's project, kind and doc, so the API needs only `{body, parent_id}`.

### Changed
- **A study's data is a relational schema.** The Study tab's **Data** view now opens as a schema: each table a box listing its columns, with key icons, types and `?` for nullable ones, and each foreign key a line from its column to the column it references. Columns named like a key (`owner_id`) that the study didn't declare are linked to the matching table's primary key, dashed and marked inferred. You can zoom, pan, drag tables and use the minimap; hovering a table lights up its relations and labels its lines, and clicking a table jumps to its fields. The Mermaid ER diagram is behind a toggle.
- **Diagrams zoom and pan.** Every Mermaid diagram (docs, the Diagrams page, the Study tab and the maps' Mermaid view) has zoom buttons and a fit button in its corner, zooms with Ctrl+wheel, pans by dragging, and opens **Full screen**, where the plain wheel zooms. In a study's flows, a participant's name opens that component's details, and in its data diagram a table's name jumps to its fields.
- **The maps are interactive** ([ADR 0015](docs/decisions/0015-interactive-registry-maps.md), now accepted). The Projects, group and project pages draw their maps with React Flow and lay them out with ELK in a web worker: click a box to open its project or group, hover to light up its links, fold groups and parents, zoom, pan and use the minimap. Where projects have been studied, arrows show the calls found in their code: blue when the code confirms `depends_on`, orange for calls the registry doesn't list, dotted for dependencies the code never calls. The Mermaid version is behind a toggle on every map. The study's component map uses the same view, where a double click looks inside a component. React Flow is its own lazy chunk.
- Feedback status is per thread (ADR 0018). A thread's status is its latest message's. Under Claude's latest answer, **Resolve thread** resolves every message in it and **Reopen thread** sends it back to Claude as a new "Reopened" message you can edit (`POST /api/feedback/{id}/reopen`), and a reply to a resolved thread reopens it too. An answered message no longer goes back to open, so Claude's earlier answers are never overwritten. Database migration 7 turns items reopened the old way into a "Reopened" message. A thread takes no reply while a message in it still waits for Claude (edit that message instead). Lists, the doc panel, project pages, the summary and the header badge count threads, and `GET /api/feedback` returns one row per thread with `messages` and `latest_id`. The **Follow up** form is gone. Database migration 6 adds `thread_id` and fills it for existing items.
- The project maps on the Projects, group and project pages are laid out with ELK, so nested boxes and arrows are tidier.
- A project's inbox (`inbox --project <project>`, and `inbox --here` anywhere in its folder) now includes its modules' items, since one repository has one session (ADR 0016).

### Fixed
- In the sidebar, a project with sub-projects is a link again: clicking its name opens its page (facts, notes, sub-projects and map) and unfolds it. The chevron next to it only folds and unfolds.

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
