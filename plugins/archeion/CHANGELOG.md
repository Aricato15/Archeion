# Changelog: Archeion plugin

The plugin's own versions, separate from Archeion's ([ADR 0009](../../docs/decisions/0009-archeion-plugin-for-project-sessions.md)). The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.1] - 2026-11-20

### Added
- `/archeion:design-consumed`: tells Archeion on its own that a design revision was consumed (`design consumed`, then a report in the handoff thread, resolving it). It reads `slug`, `revision`, `thread` and `reported` from the receipt, so it can be run again whenever the report didn't get through. `/archeion:consume-design` now writes those lines in the receipt and calls this skill as its last step.

### Fixed
- `/archeion:consume-design` now spells out the launcher command for its last step (`design consumed`, the thread report). It used to give only the sub-commands, so a session could call Archeion's own `archeion.ps1` directly, hit PowerShell's execution policy and skip telling Archeion. Update the plugin (`/plugin marketplace update archeion`) and open a new session.

## [0.5.0] - 2026-11-20

### Added
- `/archeion:consume-design` reads the design's checklist when the package has one (Archeion's ADR 0029). A package with a `roadmap.md` (the roadmap generated from the items the user confirmed) and a `checklist.json` puts its Now / Next / Later items into the project's `ROADMAP.md`, in the project's own layout and after asking, and a later revision is shown as what moved, finished or was dropped. Done items are history and are not added as tasks. The files are removed with the rest of the package, and the receipt lists what was written. A package without them is consumed as before, and no newer Archeion is needed.

## [0.4.0] - 2026-11-18

### Changed
- **`/archeion:report` is now `/archeion:notify`.** The old name clashed with Archeion's own `/report`, which makes a PDF report of a project (Archeion's ADR 0025). The skill does what it did: it tells Archeion about a change, or asks it a question, in Archeion's inbox, and carries on a thread when there is one. Only the name and its wording changed. `/archeion:context` and `/archeion:ports` now offer `/archeion:notify`. Update the plugin and open a new session: a session that is already running keeps the old name until then.

## [0.3.0] - 2026-11-17

### Added
- `/archeion:consume-design`: turns a design package that Archeion delivered into `.archeion/designs/<slug>/` into the project's own docs (Archeion's ADR 0022). It reads the package and the project's `CLAUDE.md`, shows what it will write and asks, then writes the design doc, the decisions as ADRs with the next free numbers, the plan into `ROADMAP.md` and additions to `CLAUDE.md`. It runs the project's checks, never commits, leaves a `receipt.md`, and tells Archeion (`design consumed`, a report in the handoff thread, resolving it) when Archeion is there and recent enough. With no package it says so and does nothing at all. A later revision is consumed as a change against the receipt.
- `/archeion:report` says what to include when a change goes against a design that was handed off: the design's slug and revision, what it said, what the project does now and why.
- The SessionStart hook mentions a design package waiting in `.archeion/designs/`. It needs no Archeion to find it.

No newer Archeion is required: only the reporting back to Archeion needs one with the `design` commands, and the skill skips it when it's missing.

## [0.2.0] - 2026-11-17

### Changed
- `/archeion:report` carries on a conversation. It lists the threads this project started (`inbox threads --from-here`), and a report on the same matter, or an answer to Archeion's reply, goes into that thread (`inbox create --in <id>`) instead of starting a new one, as a reply in the viewer would. It can show Archeion's answer and resolve the thread.
- `/archeion:inbox` keeps a follow-up typed in the chat in the item's thread: it records the message already claimed (`inbox create --in <id> --claim`), answers it with `inbox reply`, and resolves the thread when the user says it's done. The viewer shows the same conversation either way.
- Both read the item and thread ids from the `ids: item #N, thread #T` line every inbox command now prints (or `--json`), name them to the user so a later call in the same chat finds the thread, and look the thread up with `inbox threads` when the ids are gone.
- Both need an Archeion with `inbox threads`, `create --in` and `resolve`. With an older one they work as before and say so.

## [0.1.2] - 2026-11-16

### Changed
- `/archeion:inbox` reads a reply in a thread with the whole conversation that `inbox show` prints, and answers the newest message (Archeion's ADR 0018). With an older Archeion it works as before.

## [0.1.1] - 2026-11-15

### Changed
- `/archeion:context` explains projects and modules: a module is a part of a project, inside its repository, and the project's session covers it (Archeion's ADR 0016).

## [0.1.0] - 2026-11-15

Requires Archeion 0.4.0 or later.

### Added
- `/archeion:inbox`: the project's feedback from the viewer. It replaces the portable `project-inbox` skill that was kept in Archeion's `integrations/`.
- `/archeion:context`: the project's place in the system, from `projects show --here`.
- `/archeion:ports`: the ports the registry records, with clashes flagged.
- `/archeion:report`: sends a change to Archeion's inbox, marked with the project it came from.
- A SessionStart hook that announces open feedback for the project.
- `scripts/archeion.ps1`: finds Archeion (`ARCHEION_HOME`, the marketplace's folder, or `../archeion`) and checks its version.
