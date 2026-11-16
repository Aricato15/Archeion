---
name: design
description: Design and plan a registered project from Archeion (ADR 0022) with the rest of the system in view, and keep the result in the private registry as a living design (brief, architecture, plan, decisions, model) that the user reviews, approves and hands off to the project. Checks its own setup first and fixes it after asking. Use when the user says "/design <project>", "design <project>", "plan <project>", "work out how <project> should be built", or an inbox item is a design conversation.
argument-hint: <project> [--slug <name>] [--yes]
allowed-tools: PowerShell(powershell -NoProfile -ExecutionPolicy Bypass -File scripts/archeion.ps1 design:*), Bash(powershell -NoProfile -ExecutionPolicy Bypass -File scripts/archeion.ps1 design:*), PowerShell(powershell -NoProfile -ExecutionPolicy Bypass -File scripts/archeion.ps1 projects:*), Bash(powershell -NoProfile -ExecutionPolicy Bypass -File scripts/archeion.ps1 projects:*), PowerShell(powershell -NoProfile -ExecutionPolicy Bypass -File scripts/archeion.ps1 study:*), Bash(powershell -NoProfile -ExecutionPolicy Bypass -File scripts/archeion.ps1 study:*)
---

# Design and plan a project

A **design** says what a project is for and how it should be built, with the other projects in view. It lives in the private registry, in `registry/designs/<project>/<slug>/` ([ADR 0022](../../../docs/decisions/0022-design-and-plan-a-project.md)): prose (`brief.md`, `architecture.md`, `plan.md`, `questions.md`, `decisions/NNNN-title.md`) and `model.json`, the intended system in the study schema plus a `structure` block. The viewer's **Design** tab shows it, draws its diagrams from the model, and lets the user move it through `brief` → `architecture` → `plan`, approve it and hand it off. You write the content, the user decides every stage move and the approval.

Every command runs from the repo root:

```
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/archeion.ps1 <command>
```

| Command | What it does |
|---|---|
| `design preflight <p> [--for design\|handoff] [--slug s] [--json]` | what stands in the way, each problem with its fix. Exit 4 when something blocks |
| `design context <p> [--json]` | the project's own `CLAUDE.md`, registry facts, its neighbours (group, `depends_on`, `used_by`) with what their studies say they expose, ports in use, groups, registered projects, the workspace rules |
| `design init <p> [--slug s] [--thread n] [--summary text]` | start a design (stage `brief`) |
| `design list [<p>] [--json]` / `design show <p> [--slug s] [--revision n] [--json]` | designs, and one design's state, files and problems |
| `design validate <p> --dir <folder>` | check a work folder without saving it |
| `design save <p> [--slug s] --dir <folder> [--thread n]` | replace the working copy with the folder's files (files the folder lacks stay as they are). The only way a design is written |
| `design stage <p> brief\|architecture\|plan` | **only when the user asks** |
| `design approve <p> [--slug s] [--yes] [--no-registry]` | without `--yes`: shows the revision and the registry lines it would change, and changes nothing |
| `design handoff <p> [--slug s]` | asks Archeion's `/inbox` to deliver the latest revision to the project |
| `projects scan`, `projects show`, `projects inbox-edits <p> on\|off\|auto`, `projects ports` | the registry |
| `study list <p>`, `study show <p> --json` | whether the project has been studied, and what it exposes |

## Hard rules
- **The user moves the stages and approves.** Never run `design stage` or `design approve --yes` unless they said to, in the thread or the chat. Propose the move instead ("I think the brief is ready").
- **Never write into `registry/designs/` yourself.** Write files in your scratchpad and `design save` them.
- **Nothing about a project goes into Archeion's committed files** (ADR 0007). Designs are in the private `registry/`.
- **No secrets and no absolute paths** in anything you write. Paths are relative to the project. `design save` refuses both.
- **Don't edit the project.** Designing is read-only on it. Delivering a handoff is a separate step, done by `/inbox` (below).
- **Ask, don't guess.** What you can't know (who uses it, how big, what it must never do) goes in `questions.md` and in your reply.

## Preflight: the skill owns the setup (point 11 of the ADR)
Run `design preflight <p> --json` first, every time. Never send the user to a menu for something a command can fix.
- `not-registered`: offer `projects scan --write --only <p>`, and on a yes run it.
- `unknown-project` or `no-folder`: the folder isn't under a granted root. This is the one thing you can't fix: tell them to add the root on the Settings page, and stop.
- `no-study` (a warning): the project already has code. Offer `/study <p>` first, so the design starts from what is built. If they say to go on without, do.
- `no-claude-md` (info): the project has no `CLAUDE.md`. Ask for the tech stack in your first reply. Not a problem.
- Anything else with a `fix`: show it and offer it.

## Steps (in the terminal)
1. **Preflight**, as above.
2. **Context.** Run `design context <p>` and read all of it. If the project has code, also read its `CLAUDE.md`, `README.md` and `docs/`, and the latest study (`study show <p> --json`). The neighbours' exposed endpoints are what this project can call; what it should expose is part of the design.
3. **Start or continue.** `design list <p>`. With no design, `design init <p>` (add `--slug` for a feature design on a project that already has one). Otherwise `design show <p> --json` and continue from the stage it's at.
4. **Work the stage the design is at**, in a scratchpad folder (the work folder). Write only the files that change.
   - **brief:** `brief.md`. Purpose, users and who calls it, scope, non-goals, constraints, success. Ask what you need, a few numbered questions at a time.
   - **architecture:** `architecture.md` and `model.json`. Components (nested with `parent`), relations, what it exposes and calls (target other registered projects by `target_project`), entities with every column, flows for the key paths, states for lifecycles, plus `structure`. See the model below. Use the neighbours' real endpoints, and put what's missing in your reply as a request to the neighbour (never edit it).
   - **plan:** `plan.md` (phases, each with a goal, what's in it and a **date**, never "next week"), and `decisions/NNNN-title.md` for each real decision, in ADR shape (context, decision, consequences). These are written for the project's own `docs/decisions/`, so they don't mention Archeion or other registry facts beyond what the project needs.
   - **questions.md** always holds what's still open.
5. **Validate and save.** `design validate <p> --dir <work>`, fix everything it reports, then `design save <p> --slug <s> --dir <work>` (add `--thread <n>` in a conversation).
6. **Summarise** what changed, what's open, and where to look (the project page's **Design** tab). When the content looks ready for the next stage, say so and wait for the user.
7. **Approve** (when the user says so): run `design approve <p>` and show them the registry lines it would change. On a yes, `design approve <p> --yes`. Then offer the handoff.
8. **Hand off** (when the user says so): `design preflight <p> --for handoff`; fix what it reports (typically `projects inbox-edits <p> on`, after asking); then `design handoff <p>`. It creates an inbox thread for Archeion, which `/inbox` carries out by delivering the package into the project's `.archeion/designs/<slug>/`. Tell the user to run `/archeion:consume-design` in the project's own session.

## Conversation mode (inbox threads)
`inbox show` prints `task: a design of <p> '<slug>' (ADR 0022)` for a design thread started by **Ask Claude to design** on the Design tab. Each message is one round, and nobody may be at the terminal:
- **First round:** preflight (fix what you can; if you must ask, ask in the reply and stop). `design init <p> --slug <s> --thread <thread id>` if there's no design. Read the context and write the brief. Save it. Reply with what you understood, what you drafted and **numbered questions**.
- **Later rounds:** read the whole thread and `design show <p> --json`. Apply the answers, move the content on, save. Reply with what changed and the questions still open. Don't ask again what's answered.
- **Comments on design docs** (an inbox item anchored to a doc under `designs/<p>/<slug>/` in the registry source) are answered the same way: edit the content through a work folder and `design save`, then reply.
- **When the user approves** ("approve", "looks good, approve it"), run steps 7. **When they ask to hand off**, step 8. Never on your own.
- Keep each reply short. The detail belongs in the files, which the Design tab shows.
- An on-demand run can't approve arbitrary commands. Use the design, projects and study commands, read files, and write to your scratchpad and `registry/`. If something needs more, say so.

## Handoff tasks (for `/inbox`)
`inbox show` prints `task: a handoff-design of <p> '<slug>'` for a thread `design handoff` or the viewer's **Hand off to the project** created. It's a plain delivery:
1. `design preflight <p> --for handoff --slug <slug>`. If it blocks, say what and the fix in your reply, and stop. Don't turn `inbox_edits` on yourself in a conversation nobody is watching unless the thread says to.
2. `design package <p> --slug <slug> --revision <n>`: a plain copy of the revision's package into the project. No interpretation, no other files.
3. Reply with the files delivered, and that the project's session should now run `/archeion:consume-design`. Say they're uncommitted in that project.

## The model (`model.json`)
The study schema (see the `study` skill) with these differences: `meta` has `project`, `date`, `summary` and `stack` and **no commit**; there are no `findings` to cite code for (use `questions` and `structure`), and `cites` are rarely needed since nothing is built yet. Add:

```json
"structure": {
  "ports": [20101],                 // in the workspace range for its category, not in use (design context lists them)
  "depends_on": ["other-project"],  // registered projects it will call or import
  "group": "a-group-id",            // an existing group, only if the page has none
  "kind": "service",
  "status": "planned"               // optional
}
```

`design save` refuses a port outside the ranges or already recorded for another project, a `depends_on` that isn't registered, a group that doesn't exist, and a model whose references don't resolve. Approval writes `ports` and `depends_on` (added to what the page has), and `group`, `kind` and `status` when set, into the project's registry page. Nothing else.

Component kinds: service, package, module, class, function, library, database, external, ui, cli, job, store. Relation kinds: imports, calls, http, sql, event, reads, writes. Use `kind: external` for another registered project in the diagrams, with its id equal to the project name.
