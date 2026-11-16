---
name: study
description: Study one registered project's code in depth (ADR 0019) and save what you learn as a dated snapshot in Archeion's registry, a structured model of its components, libraries, calls, web calls, data, flows, logic and states that the viewer draws as component maps, sequence, ER, activity and state diagrams. Read-only on the project. Asks before writing unless given --yes. Use when the user says "/study <project>", "study <project>", "map out how <project> works", "refresh the study of <project>", or an inbox item asks for a study.
argument-hint: <project> [--yes] [--refresh] [--focus <area>]
allowed-tools: PowerShell(powershell -NoProfile -ExecutionPolicy Bypass -File scripts/archeion.ps1 study:*), Bash(powershell -NoProfile -ExecutionPolicy Bypass -File scripts/archeion.ps1 study:*), PowerShell(powershell -NoProfile -ExecutionPolicy Bypass -File scripts/archeion.ps1 projects show:*), Bash(powershell -NoProfile -ExecutionPolicy Bypass -File scripts/archeion.ps1 projects show:*)
---

# Study a project

A study reads one registered project's code and records what it does and how its parts connect. It's saved as a **snapshot**: `registry/studies/<project>/<date>-<commit7>/`, holding `study.json` (the model) and `notes.md` (the narrative). The viewer's **Study** tab on the project page draws the diagrams from the model. Snapshots are dated and tied to a commit, never edited, and pruned beyond `ARCHEION_STUDY_KEEP` ([ADR 0019](../../../docs/decisions/0019-code-studies.md)).

Every command runs from the repo root:

```
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/archeion.ps1 <command>
```

| Command | What it does |
|---|---|
| `projects show --project <p> --json` | the registry facts: folder, type, ports, `depends_on`, group, notes |
| `study scan <p> --out <file>` | the inventory: languages, manifests, entry points, import graph, routes, outgoing HTTP calls, SQL tables, env var names, ports (Python and TS/JS parsed, other languages only counted) |
| `study list [<p>]` | snapshots, and how many commits behind the project each one is |
| `study show <p> [<snapshot>] --json` | one snapshot's model and notes (default: latest) |
| `study changes <p>` | files changed since the latest snapshot's commit (for `--refresh`) |
| `study validate --file <f>` | check a model without saving it |
| `study save <p> --file <f> --notes <f>` | validate and store it as a new snapshot (the only way one is written) |

## Arguments
- `<project>`: a registered project or module (`projects list`). Exactly one per run.
- `--yes`: skip the confirmation in step 4 and write straight away.
- `--refresh`: start from the latest snapshot and reread only what changed since its commit.
- `--focus <area>`: go deeper on one part (a module, a flow), and keep the rest of the latest snapshot as it is.

## Hard rules
- **Read-only on the project.** Never edit, run, build, install or test anything in it. Don't run its scripts, start its servers or import its code.
- **Never read secrets.** Skip `.env` and `.env.*` (except `.env.example`), keys and certificates (`*.pem`, `*.key`, `*.pfx`), databases (`*.db`, `*.sqlite*`) and anything under `data/` that isn't code. Describe a credential by what it's for, never its value. `study save` refuses snippets that look like secrets.
- **Nothing about the project goes into Archeion's committed files** (ADR 0007). Everything you write goes to `registry/` (gitignored) or your scratchpad.
- **Facts come from the code.** Every element gets at least one citation (`path`, `line`). When the code doesn't tell you, put it in `questions` rather than guessing.

## Steps

1. **Resolve.** Run `projects show --project <p> --json`. If its folder isn't available, say so and stop. Read the project's `CLAUDE.md`, `README.md` and the relevant `docs/` first, because they say what the project is meant to do. Note the registry's `ports`, `depends_on` and `kind`.
2. **Inventory.** Run `study scan <p> --out <scratchpad>/inventory.json`, and read the text report plus whatever parts of the JSON you need. With `--refresh`, also run `study show <p> --json` and `study changes <p>`. Only the changed files, and the components they belong to, need rereading.
3. **Plan.** Decide what's worth drawing. Leave out anything that isn't, because a small, accurate study beats a large, vague one.
   - **Components:** the deployable parts (service, ui, cli, job), their packages and modules, the libraries that shape the design (a framework, an ORM, an HTTP client), and the stores and outside systems (database, files, other projects, outside APIs). Go down to classes and functions only where they carry the design.
   - **Flows** (sequence diagrams): the 3 to 8 paths that matter most, such as a request through the API to the database, a background job's cycle, start-up, or a call to another project.
   - **Activities:** branching logic worth seeing: retries, pipelines, validation, scheduling.
   - **Entities** (ER): from migrations, `CREATE TABLE`, ORM models or the shapes of stored files.
   - **States:** records with a status column or a lifecycle.
   - **Interfaces:** everything it exposes (routes, CLI commands, events, files other projects read) and everything it calls (other registered projects by port or URL, outside APIs).
   - **Findings:** check against the workspace rules in `../CLAUDE.md`. Is the port in its category's range and unused elsewhere (`projects ports`)? Does it have its own SQLite file with the required pragmas, and no shared database? Is its environment kept inside its folder? Add risks you notice too (an unbounded loop, missing error handling at a boundary, a secret read from a file), each with a citation.
4. **Confirm** (skip with `--yes`). Show the user:
   - the plan: the components, flows, activities, entities, states and interfaces you'll cover, and anything you'll leave out;
   - the registry frontmatter changes you'd make to `registry/projects/<p>.md`, such as `ports`, `depends_on` (from the calls found), `kind` and `status`, plus `verified: <today>`, as a before/after list;
   - for `--refresh`, what changed since the last snapshot.

   Wait for a yes. When the study came from `/inbox`, this plan **is** your reply: send it, and the user answers in the thread. Only a reply that approves it (or a request that said `--yes`) lets you go on.
5. **Read deeply.** Follow each chosen flow through the code, from its entry point down to the database or the outgoing call, and read every function on the way. Use the inventory's import graph and routes to find them. For a large codebase, read one top-level package at a time. Write down each element's citations as you go: `{path, line, end}`, and a short `snippet` (at most 30 lines) only where the code itself explains something the diagram can't.
6. **Write the model** to `<scratchpad>/study.json` (schema below) and the narrative to `<scratchpad>/notes.md`. The narrative covers what the project is for, how it's built, how to read the diagrams, and what surprised you. Use relative paths and no secrets. Diagrams in `notes.md` are optional, since the viewer draws them from the model.
7. **Validate** with `study validate --file <scratchpad>/study.json`. Fix every problem it reports and run it again until it passes.
8. **Save** with `study save <p> --file <scratchpad>/study.json --notes <scratchpad>/notes.md`.
9. **Update the registry page**, with only the changes the user confirmed in step 4: the frontmatter fields and `verified:`. Edit `registry/projects/<p>.md` by hand, and keep everything else on the page as it is. Cross-project notes in the body stay short: what this project means to the others. Link to the study rather than copying it.
10. **Summarise** in a few lines: the snapshot id, what's covered, the main findings, the open questions, and the registry changes. Point to the viewer: the project page, **Study** tab.

## The model (`study.json`, schema 1)

Ids match `[A-Za-z0-9_][A-Za-z0-9_.-]*` and are unique within their section. Every reference must name an existing element, which `study validate` checks. `cites` is a list of `{path, line?, end?, snippet?}` with paths relative to the project.

```json
{
  "schema": 1,
  "meta": {
    "project": "<p>", "date": "YYYY-MM-DD", "commit": "<HEAD hash from the scan>", "dirty": false,
    "summary": "One paragraph: what it is and how it's built.",
    "stack": ["python 3.12", "fastapi", "sqlite"],
    "coverage": {"files_total": 120, "files_read": 45, "note": "tests skimmed, migrations read in full"},
    "refreshed_from": "<previous snapshot id, for --refresh>"
  },
  "components": [
    {"id": "api", "name": "API server", "kind": "service", "summary": "...", "paths": ["src/api"], "tech": "FastAPI",
     "cites": [{"path": "src/api/main.py", "line": 12}]},
    {"id": "api.routes", "name": "routes", "kind": "module", "parent": "api", "cites": [...]},
    {"id": "db", "name": "app.db", "kind": "database", "tech": "SQLite"},
    {"id": "other-project", "name": "other project", "kind": "external"}
  ],
  "relations": [
    {"id": "r1", "from": "api.routes", "to": "db", "kind": "sql", "label": "read/write items", "cites": [...]}
  ],
  "interfaces": {
    "exposes": [{"id": "get-item", "kind": "http", "method": "GET", "path": "/api/items/{id}", "handler": "api.routes", "summary": "...", "cites": [...]}],
    "calls": [{"id": "c1", "kind": "http", "target_project": "<registered name>", "port": 20100, "method": "POST", "path": "/api/x", "from": "api.routes", "cites": [...]}]
  },
  "entities": [
    {"id": "items", "name": "items", "store": "db", "fields": [
      {"name": "id", "type": "INTEGER", "pk": true},
      {"name": "owner_id", "type": "INTEGER", "fk": "owners.id", "nullable": true}], "cites": [...]}
  ],
  "flows": [
    {"id": "get-item-flow", "title": "Read an item", "trigger": "GET /api/items/{id}",
     "participants": ["web", "api.routes", "db"],
     "steps": [
       {"from": "web", "to": "api.routes", "label": "GET /api/items/{id}"},
       {"from": "api.routes", "to": "db", "label": "SELECT ... WHERE id = ?"},
       {"block": "alt", "label": "found", "steps": [{"from": "api.routes", "to": "web", "label": "200 item", "reply": true}],
        "others": [{"label": "missing", "steps": [{"from": "api.routes", "to": "web", "label": "404", "reply": true}]}]},
       {"note": "cached for 60 s", "over": ["api.routes"]}
     ], "cites": [...]}
  ],
  "activities": [
    {"id": "sync-job", "title": "Nightly sync", "nodes": [
      {"id": "start", "kind": "start"}, {"id": "fetch", "label": "fetch page"},
      {"id": "more", "label": "more pages?", "kind": "decision"}, {"id": "end", "kind": "end"}],
     "edges": [{"from": "start", "to": "fetch"}, {"from": "fetch", "to": "more"},
               {"from": "more", "to": "fetch", "label": "yes"}, {"from": "more", "to": "end", "label": "no"}], "cites": [...]}
  ],
  "states": [
    {"id": "order-status", "title": "Order", "entity": "orders", "states": [{"id": "new"}, {"id": "paid"}, {"id": "shipped"}],
     "initial": "new", "final": ["shipped"],
     "transitions": [{"from": "new", "to": "paid", "label": "payment ok"}], "cites": [...]}
  ],
  "findings": [{"id": "f1", "severity": "warn", "title": "...", "detail": "...", "rule": "ports", "cites": [...]}],
  "questions": ["What the code didn't answer."]
}
```

- **Component kinds:** service, package, module, class, function, library, database, external, ui, cli, job, store. Nest them with `parent`, which the component map draws as boxes inside boxes.
- **Relation kinds:** imports, calls, http, sql, event, reads, writes.
- **Interface kinds:** exposes is http, cli, event, file or library. Calls is http, event, file or library. An http call needs `target_project`, `target_url` or `port`. Name a registered project in `target_project` when you know it, so the system map can link the two.
- **Flow steps:** messages (`from`, `to`, `label`, `reply`, `async`), notes (`note`, `over`: one or two participants), and blocks (`block`: alt, opt, loop or par, with `steps` and, for alt and par, `others` branches). Participants must be components.
- **Finding severity:** info, warn or risk.

## Notes
- One project per run. A module can be studied on its own. Studying a project covers its modules unless they have their own studies.
- A dirty working tree is fine. Record `"dirty": true` so the snapshot says it saw uncommitted code.
- If the scan finds very little (another language, generated code), say so in `coverage.note` and read the code directly.
