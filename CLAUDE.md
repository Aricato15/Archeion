# archeion

Private documentation-only repository holding my system-wide point of view: how my projects interact with each other, architecture overviews, and the roadmap.

## Purpose
This repo is where I think about the whole system, not any single project. Sessions here should:
- Build and maintain the system-level picture: what each project is, what it owns, and how they connect.
- Document cross-project interactions: APIs called, data owned, ports, events, dependencies.
- Plan the roadmap: what gets built next, in what order, and why.

Don't write application code here, and don't edit sibling projects from this repo. When a sibling project's facts are needed (ports, APIs, stack), read them from that project's `CLAUDE.md`/`docs/` or `../PROJECTS.md`, and record what you learned here with a pointer to the source.

## Stack
Markdown documentation only (no code, no runtime). Diagrams as Mermaid code blocks inside Markdown.

## Environment
- Location: none. There are no dependencies or environment folders.
- Created by: n/a.
- If tooling is ever added (e.g. a Markdown linter), keep it inside this folder and list its environment folder in `.gitignore`.

## Commands
- Install: none
- Run / dev: none
- Test: none
- Lint / format: none yet. Before finishing, check that relative links between docs resolve.

## Architecture
- `docs/system/`: the system point of view. `overview.md` (the big picture) and `projects/<project>.md` (one page per project: purpose, owns, exposes, depends on).
- `docs/interactions/`: how projects talk to each other. `map.md` holds the dependency/interaction diagram; one file per notable flow or integration.
- `docs/roadmap/`: `roadmap.md` (now / next / later) plus dated plans for larger initiatives.
- `docs/decisions/`: cross-project architecture decisions as `NNNN-title.md` (ADRs).
- `docs/notes/`: session handoffs.

## Conventions
- One fact lives in one place; link to it rather than copying it.
- Each project page records the date it was last verified against the real project.
- Use the workspace port ranges and database rules (`../CLAUDE.md`) as the baseline when describing or planning services.
- Roadmap items use absolute dates, never "next week".

## Gotchas
- None yet.
