# 0030: A committed example project for show and tell

- Status: Accepted (2026-11-20)
- Date: 2026-11-20
- Builds on: [ADR 0007](0007-keep-project-information-out-of-the-repo.md), [ADR 0022](0022-design-and-plan-a-project.md), [ADR 0029](0029-design-checklist.md)

## Context
Archeion's views (project page, design, checklist, roadmap, glossary) are only seen on real projects, whose data is private (ADR 0007). There's nothing to show someone, to try a feature on, or to test the views against without a real project, and nothing to point at in the docs.

## Decision
1. **`demo-example-data/` is committed, and holds everything about the demo.** One made-up project, **Example-Project** (an online bookshop): `registry/` in the registry's own layout (the project page, a design with an approved revision, a checklist with confirmed and pending changes, a glossary) and `example-project/`, the project's own folder (`README.md`, `CLAUDE.md`, `ROADMAP.md` with released versions, `CHANGELOG.md`, `docs/`). It names no real project, path or person, so the commit hook has nothing to block.
2. **It is read in place, never copied into the private registry.** The registry loader adds the page under `demo-example-data/registry/projects/` to the projects it loaded (flagged `demo`), and the design and glossary routes read the demo's data from `demo-example-data/registry/` (`demo.root_for`). The user's `registry/` is never touched, and nothing about the demo can mix with their projects.
3. **A page may point into `demo-example-data/`.** The registry refuses a page that points at this repo itself. The one exception is a path under `demo-example-data/`, resolved inside that folder and nowhere else.
4. **It's listed apart from the user's projects.** The sidebar has a **Demo** entry, below the Projects section, that opens the project's page, with the same tabs and views as a real project (docs, design, checklist, roadmap, glossary). The Projects page, the sidebar's project tree, the maps, the groups and the cross-project Roadmap page leave it out.
5. **Nothing about it is written, and nothing reaches a database or Claude.** Every write to its design or glossary is refused (`demo.read_only`, a router dependency), so `demo-example-data/` is never changed by the app. The feedback service refuses any item whose source or task names the example project, and any follow-up in a thread about it, whoever asks (the API, a design conversation, a handoff, the CLI). So the inbox, the inbox terminal and on-demand Claude never see it. Its page has `inbox_edits: false`, and its project page marks it **example**, with no Prompt, Report, Registry-page, Promote or Remove buttons.
6. **No `example.db` for now.** Nothing in the demo needs a database of its own. If a view ever needs stored state, it gets its own file, never `archeion.db` (and the commit hook refuses `.db` files anyway).

## Consequences
- A fresh clone has something to show with no setup, and tests can run the real views against it.
- Accepting or confirming a checklist change in the demo is refused (the message says it's demo data, so nothing is changed). The checklist is shown as it would look at review time, with changes waiting.
- The demo's name is not in the private registry, so the commit hook's project-name check never sees it.
- Searching or browsing docs can find the demo's docs, as it is a doc source like any project's.
