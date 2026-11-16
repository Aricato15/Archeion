---
name: consume-design
description: Turn a design package that Archeion delivered into this project's own docs - the design, its decisions as ADRs, the plan in the roadmap and additions to CLAUDE.md - then record it with Archeion. Looks for the package in .archeion/designs/ and does nothing at all when there is none. Use when the user says "/archeion:consume-design", "consume the design", "pick up the design from Archeion", or the session start says a design package is waiting.
argument-hint: [slug] [--yes]
allowed-tools: PowerShell(powershell -NoProfile -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/scripts/archeion.ps1" projects show:*), Bash(powershell -NoProfile -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/scripts/archeion.ps1" projects show:*), PowerShell(powershell -NoProfile -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/scripts/archeion.ps1" design consumed:*), Bash(powershell -NoProfile -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/scripts/archeion.ps1" design consumed:*), PowerShell(powershell -NoProfile -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/scripts/archeion.ps1" inbox:*), Bash(powershell -NoProfile -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/scripts/archeion.ps1" inbox:*)
---

# Consume a design

The user designed this project in Archeion (its **Design** tab), approved a revision and handed it off. Archeion delivered a **design package** into this project's folder: `.archeion/designs/<slug>/`. This skill turns the package into the project's own docs, so that from here on the project owns the facts and Archeion only keeps the revision as history (Archeion's ADR 0022).

**If there is no package, do nothing.** Don't look for the design anywhere else, don't ask Archeion for it, don't write anything. Say so and stop.

## The package

`.archeion/designs/<slug>/` holds the revision as it was approved:

| File | What it is |
|---|---|
| `handoff.json` | `project`, `slug`, `revision`, `date`, `thread` (the Archeion thread the handoff was requested in). Its presence means "waiting to be consumed" |
| `brief.md` | purpose, users, scope, non-goals |
| `architecture.md`, `model.json` | the intended system: components, interfaces, data, flows, and a `structure` block (ports, `depends_on`, kind) |
| `plan.md` | phases with dates |
| `decisions/NNNN-title.md` | the decisions, in ADR shape |
| `questions.md` | what was still open |
| `receipt.md` | only after an earlier consume: what it wrote (revision, date, files) |

## Steps

1. **Find the package.** Look in `.archeion/designs/` at the project's root (the folder this session runs in, or its git root). A package is a folder with `handoff.json`.
   - **None** (no `.archeion/designs/`, or no `handoff.json` in it): reply *"No design package here, so there's nothing to consume. A package arrives when a design is handed off from the Design tab in Archeion."* and **stop**. Change nothing, run nothing else, don't call Archeion.
   - **Several** and no `<slug>` argument: list them (slug, revision, date) and ask which.
2. **Read** the whole package and the project: `CLAUDE.md` (stack, conventions, where docs and ADRs go, how to test), `README.md`, `ROADMAP.md`, `docs/` and its ADR numbering, and `receipt.md` if there is one (this is then a later revision, see below). Don't read `.env` files or secrets.
3. **Check it fits.** Compare the package with the project: the stack against `CLAUDE.md`, ports against files that already use them, folders and names that already exist, decisions that contradict an existing ADR. Note each mismatch. Never silently pick a side.
4. **Plan and confirm** (skip the asking with `--yes`, but still show it). Show the user, as a list:
   - **Design doc:** where it goes (whatever `CLAUDE.md` says, else `docs/design.md`), written from `brief.md` and `architecture.md` with the diagrams kept.
   - **Decisions:** each `decisions/*.md` as an ADR in the project's decisions folder, with the next free numbers (renumbered, links fixed), dated today, status `Accepted`.
   - **Plan:** the phases into `ROADMAP.md` (or the project's equivalent), with their dates.
   - **CLAUDE.md:** the additions, as before/after: tech stack, the port (and where it's configured, never hard-coded), commands once known, conventions the design sets. Nothing the file already says is repeated.
   - **Open questions** from `questions.md`, and every mismatch from step 3.
   Wait for a yes. Anything they change, apply.
5. **Write** exactly what was confirmed. Follow the project's own rules: its doc layout, ADR format, commit conventions (you never commit), contained environments, port ranges and database rules in the workspace `CLAUDE.md`. One fact lives in one place: the design doc links to the ADRs and the roadmap instead of repeating them. Don't name Archeion's registry or other projects' internals beyond what the design itself says about their interfaces.
6. **Check.** Run the project's tests and linters as its `CLAUDE.md` says, if the docs change could affect them, and check that relative links in what you wrote resolve. Report failures as they are.
7. **Leave a receipt.** Remove the package's copied content (`handoff.json`, `brief.md`, `architecture.md`, `model.json`, `plan.md`, `questions.md`, `decisions/`) from `.archeion/designs/<slug>/` and write `receipt.md` there: revision, today's date, and each file you created or changed. The receipt's job is to make a later revision a change instead of a rewrite. Keep `.archeion/` out of the project's commits unless the user wants it in; say which you did.
8. **Tell Archeion** (best effort; if Archeion can't be found, or is too old to have `design consumed`, say so and skip this: the project's docs are already done):
   1. `projects show --here --json` for this project's id.
   2. `design consumed <project> --slug <slug> --revision <n>`: the design becomes *handed off* in the Design tab.
   3. In the handoff thread (`thread` in `handoff.json`): write a short report of what you wrote to a scratchpad file, `inbox create --in <thread> --claim --file <it>`, read the new message's id from the `ids:` line, answer it with `inbox reply <id> --file <short note>`, and `inbox resolve <thread>`. If Archeion refuses because the thread's last message still waits, leave the thread and say so.
9. **Summarise** in a few lines: the files written (relative to this project), the decisions recorded, the first phase of the plan, what's still open. Never commit; tell the user the changes are uncommitted here. Then offer to start the first phase of the plan, with `/archeion:ports` and `/archeion:context` available as usual.

## A later revision (a `receipt.md` exists)
The user changed the design in Archeion and handed off the new revision. Treat it as a change against what the receipt lists:
- Read the files the receipt names, as they are now. The project may have moved on since, so the project's current docs win where the package would overwrite finished work: show the difference and ask.
- **Decisions:** a new decision gets a new ADR. One that changes an earlier decision gets a new ADR that supersedes it, and the old ADR's status line is set to `Superseded by NNNN`. Never rewrite an accepted ADR's body.
- **Plan:** update `ROADMAP.md`, keeping phases already done, and say which are new, moved or dropped.
- **CLAUDE.md:** only what changed.
- Write a new `receipt.md` that lists this revision above the earlier one.

## Notes
- This skill reads the package and the project. Archeion's registry, its other projects and its private files aren't available here, and aren't needed.
- The package may name other projects in `depends_on` and in the model's interfaces. That's the design's own dependency list; keep it as the design has it.
- If the package looks wrong (it's for another project, `handoff.json` is missing fields, files are empty), say what's wrong and stop before writing.
