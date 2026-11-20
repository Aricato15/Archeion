# demo-example-data

Show-and-tell data for Archeion: one made-up project, **Example-Project** (an online bookshop), with the same views a real project has: its docs, a design with a checklist and a roadmap, an approved revision, and a glossary.

It is committed on purpose, so it holds no real project, path or person ([ADR 0030](../docs/decisions/0030-example-project.md)).

## Use it
Nothing to install. Start the viewer and open **Demo** in the sidebar, below the Projects section. The viewer reads this folder in place, so it never goes into your private `registry/` and never shows among your projects.

## The rule
Nothing about the example project is written, or reaches a database or Claude:
- Every write to its design or glossary is refused by the backend, so this folder is never changed by the app.
- Feedback, prompts, comments and design conversations about it are refused too, so the inbox, the inbox terminal and on-demand Claude never see it.
- Its page has `inbox_edits: false`, and it is never a handoff target.

## What's here
- `registry/` holds what a project has in the private registry: its page (`projects/`), its design (`designs/example-project/main/`, with an approved revision and a checklist that has changes waiting for review) and its glossary.
- `example-project/` is the project's own folder, which the viewer reads as it does any project's docs: `README.md`, `CLAUDE.md`, `ROADMAP.md`, `CHANGELOG.md` and `docs/`.

Keep it generic: made-up names only, no real paths, no personal details.
