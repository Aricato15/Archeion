# 0029: A checklist in every design

- Status: Accepted (2026-11-20)
- Date: 2026-11-20
- Builds on: [ADR 0022](0022-design-and-plan-a-project.md), [ADR 0018](0018-feedback-threads.md), [ADR 0020](0020-study-conversations-and-on-demand-claude.md)
- Amends: [ADR 0022](0022-design-and-plan-a-project.md) points 1, 6, 7 and 8 (one more file in the design, one more writer path, frozen in revisions, carried in the package).

## Context
A design says what a project is (`brief.md`), how it's built (`architecture.md`, `model.json`) and in what order (`plan.md`). What it lacks is the running list of **what has been agreed**: the features we decided to build, the ideas we haven't decided on, the decisions that are made, and where each one stands. Today that lives in chat, in `questions.md` and in a few lines of `plan.md`, and nothing says "this was an idea in round 2, became a decision in round 4, and is done". The roadmap is then written by hand from memory, and gets cluttered.

## Decision
1. **A design has a checklist**, `checklist.json` in `registry/designs/<project>/<slug>/`, next to `model.json`. It is structured data, with stable item ids, so items can be tracked, linked and turned into a roadmap. Like the rest of the design it's private (ADR 0007).
2. **An item is rich data, shown minimal or rich.** Fields: `id` (stable, `c1`, `c2`, never reused), `title`, `note`, `kind` (`feature`, `idea`, `decision`, `task`, `question`), `status` (`idea`, `decided`, `doing`, `done`, `dropped`), `phase` (a phase of `plan.md`, optional), `priority` (`high`, `medium`, `low`, optional), `refs` (a component or decision of the design, optional), `depends_on` (item ids), and `history` (each change with its date, who made it and why). The viewer has a **Minimal / Rich** switch (remembered in the browser): minimal shows a tick, the title and the status, rich shows everything. Both read the same data.
3. **Claude proposes and maintains, you decide, then you confirm.** Nothing changes the checklist directly. A change is staged in `pending`, as one set keyed by item id: an add, an update or a removal, with the reason and who staged it (`claude` or `user`).
   - **Claude** stages changes (`design checklist propose`) when it finds a feature, an idea or a decision in a conversation, or when the built project shows an item is done. It never applies them.
   - **You** go through the pending changes in the Design tab: **accept**, **reject** or **comment** on each, and stage your own (add an item, change a status, drop one). A comment goes into the design's thread, so Claude reads it with the rest of the conversation (ADR 0018) and revises the pending change: the next round shows the new wording, with your comment answered.
   - **Confirm** applies every accepted change at once, and writes the history. Rejected changes are dropped and remembered in the item's history. Nothing unconfirmed ever reaches the roadmap, a revision or a handoff.
4. **The backend is the only writer**, as for the rest of the design (ADR 0022 point 6). `design checklist` (CLI) and `/api/designs/<project>/<slug>/checklist` validate (known kinds and statuses, ids exist, `depends_on` names items that exist and has no cycle, no secrets or absolute paths, size limits) and replace the file atomically. A save of the design (`design save`) leaves the checklist as it is.
5. **A roadmap is generated from it**, never written by hand. A pure function turns the confirmed items into **Now** (doing), **Next** (decided), **Later** (ideas) and **Done**, each most important first (an item without a priority counts as medium), and groups the same items by `phase` for the timeline (phases sort naturally, so Phase 2 comes before Phase 10). Dropped items are left out. The Design tab gets two new sections of equal standing, **Checklist** and **Roadmap**, next to Brief, Architecture and Plan. The Roadmap section is read-only and always current: it's drawn from the confirmed items, in columns (Now / Next / Later / Done) or as a timeline by phase, and each card links back to its checklist item, so a change is made in the checklist and confirmed there. It shows how many changes are pending ("3 pending changes aren't in this roadmap"), and a revision's roadmap can be viewed beside the working one. `design checklist roadmap <project>` prints the same as Markdown, and **Copy as Markdown** does too. Claude can fold it into `plan.md` through the usual validated save when you ask; the roadmap itself is never written anywhere by itself.
6. **Approving freezes the checklist** into the revision (ADR 0022 point 7), and pending changes aren't frozen: approving with pending changes asks first, as for any unfinished work. The **handoff package** gets `checklist.json` and the generated `roadmap.md`, and `/archeion:consume-design` turns the roadmap into the project's own `ROADMAP.md` (it asks, as it does for the rest). After the handoff the project's own docs own the facts.
7. **Items can come back from the project.** When a later `/study` shows an item's component exists, or `/archeion:notify` reports the project built it, Claude stages `done` for you to confirm. It never marks anything done by itself.
8. **Archeion's own roadmap is split by version.** This is a different file (`docs/roadmap/roadmap.md`, committed) and not generated from a design: a registered project's checklist can't write there (ADR 0007). The file keeps **Now / Next / Later** for open work, and adds **Released** with one `### X.Y.Z (date)` section per version, newest first. The viewer's Roadmap page shows the current one first, and the released versions below it, scrolling back. A roadmap without a **Released** section reads as before.

## Settled
- **Where the checklist lives.** In a design, not at project level: a feature slug gets its own list, as it gets its own brief. A project-wide view comes from listing its designs, if wanted later.
- **Why not `checklist.md`.** Items need ids, so that history, `depends_on`, phases and the generated roadmap stay stable when a title is reworded.
- **Why changes are staged.** You asked for Claude to propose and maintain while you choose and comment, then confirm. The same mechanism covers your own edits, so there's one path and one history.

## Consequences
- New: `services/design_checklist.py` (schema, validate, stage, apply, roadmap), routes under `/api/designs/.../checklist`, a `design checklist` CLI group (`show`, `propose`, `decide`, `confirm`, `roadmap`; your own edits are made in the viewer), a **Checklist** section and a **Roadmap** section of the Design tab in `app/frontend/src/design/`, and changes to the `/design` skill and the plugin's `consume-design` skill (a plugin minor version).
- No database migration: it's a file in the design folder. A design with no `checklist.json` shows an empty checklist.
- A change to the RoadmapPage and `docs_fs.parse_roadmap` (`releases`), covered by tests with the old and the new layout.
- The CLI guide, use cases and CHANGELOG change in the same release, and the release has an update note (the plugin changes).

## Plan
[The design checklist plan](../roadmap/2026-11-20-design-checklist-plan.md).
