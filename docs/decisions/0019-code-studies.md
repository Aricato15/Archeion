# 0019: Code studies, as dated snapshots in the registry

- Status: Accepted (2026-11-16)
- Date: 2026-11-16
- Builds on: [ADR 0006](0006-multi-project-registry.md), [ADR 0007](0007-keep-project-information-out-of-the-repo.md), [ADR 0014](0014-diagrams-for-system-design.md)
- Amends: the convention "a project's own facts stay in its own docs" in `CLAUDE.md`, for studies only.

## Context
The registry records projects as boxes: their group, ports and `depends_on`. It says nothing about what's inside a project, such as its packages and modules, the libraries it uses, how a request travels through its functions, which tables it keeps or which other services it calls over HTTP. A registry page is also written by hand, so it drifts from the code without anyone noticing.

Claude can read a codebase in depth, but what it learns ends up in the conversation and is gone afterwards. Whatever it learns should be kept, dated, checked against the code and shown in the viewer as diagrams.

## Decision
1. **A study is a dated, immutable snapshot.** `/study <project>` (a skill in Archeion's own session) reads one registered project read-only and writes a snapshot to `registry/studies/<project>/<YYYY-MM-DD>-<commit7>/`. Each snapshot is tied to the commit it studied, so its age is known (commits since). Snapshots are never edited. A new study adds a new snapshot, and the oldest are pruned beyond `ARCHEION_STUDY_KEEP` (default 10).
2. **The facts are a structured model, and the diagrams are generated from it.** `study.json` follows a versioned schema that the backend validates. It holds components (packages, modules, classes, libraries, databases and outside services), relations (imports, calls, HTTP, SQL, events), interfaces (what the project exposes and what it calls), entities (tables), flows (sequences), activities, states and findings. Every element carries citations (`path:line`), with optional short snippets. `notes.md` holds the narrative. The viewer generates sequence, ER, state, activity and component diagrams from the model, so the diagrams can't drift from the facts.
3. **The backend is the only writer.** `study save` validates the model, refuses snippets that look like secrets, allocates the snapshot folder and prunes old ones. Claude never writes into `registry/studies/` directly.
4. **Grounded in an inventory.** `study scan` is a deterministic, read-only inventory of the project's code. For Python and TypeScript/JavaScript it lists languages, manifests, entry points, an import graph, route declarations, outgoing HTTP calls, SQL tables and environment variable names. The study builds on it rather than on memory. Other languages are read by Claude without an inventory.
5. **Read-only and private.** A study never runs, installs or edits anything in the project, and never reads `.env` files, keys or databases. Snapshots live only in the gitignored `registry/` (ADR 0007), so nothing about a project reaches a commit. The viewer still serves only a project's docs (ADR 0006). Code appears in the viewer only as the snippets a study cited.
6. **Confirmation by default.** The skill shows its plan and the registry frontmatter changes before writing, unless it was called with `--yes`. From `/inbox`, the plan goes out as the reply, and the user approves in the thread (ADR 0018).
7. **The convention changes for studies.** A project's own facts still belong in its own docs. A study is a generated, dated view of them, kept only in the private registry and regenerated rather than edited, so it's allowed.

## Consequences
- The project page gets a **Study** tab with components, flows, logic, data, states, interfaces, findings and notes, a snapshot picker and a staleness badge. The API gets `GET /api/studies`, `GET /api/studies/{project}`, `GET /api/studies/{project}/{snapshot}`, `GET /api/studies/{project}/diff` and `GET /api/system/links`.
- Studies connect projects through their code: a call to another registered project's port and path is matched to what that project exposes. Where the code and the registry's `depends_on` disagree, the viewer shows it as drift.
- A study is a snapshot, so it goes stale. The staleness badge and `--refresh` (studying only what changed since the last snapshot's commit) keep it useful.
- Studies take space in `registry/`. Pruning keeps it bounded.

## Plan
[The code studies plan](../roadmap/2026-11-16-code-studies-plan.md).
