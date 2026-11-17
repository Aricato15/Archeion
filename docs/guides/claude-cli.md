# Working with Claude from the command line

The terminal is where you work with Claude. The viewer is for reading the docs, the registry and the maps, and for leaving feedback that Claude picks up. This page is also the viewer's **Claude CLI** panel. For whole jobs from start to finish, see the [use cases](use-cases.md).

## The loop
1. **Read** in the viewer. Comment on a passage (select text or use the margin button), or write a prompt or review on a doc or project page.
2. **Work** in a terminal: start `claude` in the right folder and run the inbox skill. Claude claims each item, does the work, and replies.
3. **Check** in the viewer. The reply shows up under Feedback (the header badge counts them), and docs update live. Resolve the item or reply to it to go another round.

## Where to start Claude
| You want to… | Start `claude` in | Then |
|---|---|---|
| Work on the system view: registry, maps, roadmap, ADRs, this viewer | Archeion's root folder | `/inbox` |
| Clear every project's feedback from one place | Archeion's root folder | `/inbox` (edits a project only when its inbox edits are allowed) |
| Work on one project | That project's folder | `/archeion:inbox` |

Start it at Archeion's root, not a subfolder: the session-start hook that announces open feedback only fires there.

## In Archeion's session
| Command | What it does |
|---|---|
| `/inbox` | Works through the feedback left for Archeion and for every registered project. For a project's item it reads that project's `CLAUDE.md`, edits its files when its inbox edits are allowed, runs its tests, and leaves the changes uncommitted there |
| `/study <project>` | Reads one registered project's code, read-only, and saves what it learns as a dated snapshot, with the component tree shaped top-down into named sub-groups (`study validate` warns about a level wider than 12): components, libraries, calls, web calls, tables, flows, logic and states, each with the code it came from. Shows its plan first (skip with `--yes`). `--refresh` rereads only what changed since the last snapshot. The project page's **Study** tab draws it ([ADR 0019](../decisions/0019-code-studies.md)) |
| `/design <project>` | Designs and plans a registered project with the rest of the system in view (its own `CLAUDE.md`, the neighbours and what their studies say they expose, ports in use, the workspace rules), and keeps the brief, architecture, plan, decisions and model as a living design. It checks its own setup first and fixes what it can after asking. You move the stages and approve; it never does. From the viewer, **Ask Claude to design** on the project page's **Design** tab starts the same thing as a conversation ([ADR 0022](../decisions/0022-design-and-plan-a-project.md)) |
| `/report <project>` | Builds a standard PDF report of a registered project: the sections you pick, in your order, from its registry page, docs, study, design and glossary, with every diagram. Deterministic: nothing in it is written by Claude, and the same choices give the same PDF. Checks the renderer and the study's age first (and offers `/study --refresh`), shows the plan (skip with `--yes`), builds and verifies. The project page's **Report** button does the same without Claude ([ADR 0025](../decisions/0025-project-pdf-reports.md)) |
| `/report-guided <project>` | Plans a PDF report from your prompt and outline: reads the sources, writes an executive summary and any other sections you ask for (each labeled and citing the sections it came from), and keeps the plan as a draft you review in the viewer's **Report** dialog, **Guided**. From the viewer it's a conversation in a thread. You press **Approve and build**; it builds only if you tell it to ([ADR 0025](../decisions/0025-project-pdf-reports.md)) |
| On-demand Claude | Not a command: **Settings → On-demand Claude** has the backend start Claude whenever a new message waits ([ADR 0020](../decisions/0020-study-conversations-and-on-demand-claude.md)). By default it's a window running `cmd /c claude "/inbox"` you can watch, closed when its turn ends; with **Headless** (Settings → Claude jobs) it opens nothing and logs every step. **Max Claude instances** (1 or 2) counts it and the inbox terminal below ([ADR 0021](../decisions/0021-claude-jobs-windows-headless-and-limits.md)) |
| `/loop 10m /inbox` | Checks the inbox every 10 minutes while the terminal is open, so items you send from the viewer get picked up without you asking. The viewer can run this for you: **Settings → Inbox terminal** starts, stops and restarts it in its own window, and the header badge shows whether it's running |
| `/workspace-core:commit` | Reviews the staged changes, proposes a Conventional Commits message, and asks before committing |
| `/workspace-core:handoff` | Writes a handoff note to `docs/notes/` for the next session |

Or just ask in plain words: "register the new project in my workspace", "check the registry against the projects", "plan the next step on the roadmap".

## In a project's session (Archeion plugin)
| Command | What it does |
|---|---|
| `/archeion:inbox` | Works through the feedback left for this project. A follow-up you type in the chat goes into that item's thread, as if you'd replied in the viewer |
| `/archeion:context` | Where this project sits: its group, what it depends on, what uses it, its ports |
| `/archeion:ports` | The ports every project uses, before you pick a new one |
| `/archeion:consume-design` | Turns a design package that Archeion delivered into `.archeion/designs/` into this project's docs: the design, its decisions as ADRs, the plan in the roadmap and additions to `CLAUDE.md`. It shows what it will write and asks first, never commits, and does nothing at all when there's no package ([ADR 0022](../decisions/0022-design-and-plan-a-project.md)) |
| `/archeion:report` | Tells Archeion about a change the registry needs (a port, a dependency, a rename). A report on something already reported, or an answer to Archeion's reply, carries on that thread |

A project session never edits Archeion's registry. It reports, and Archeion's session makes the change.

## Archeion's own CLI
Run these from Archeion's root folder: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/archeion.ps1 <command>`.

| Command | What it does |
|---|---|
| `inbox list` | Open feedback, with the projects that have items waiting |
| `inbox threads` | Conversations, one row per thread (`--project <name>`, or `--here`/`--from-here` in a project's folder) |
| `inbox create --in <id> --file <f>` | Add a message to a thread from a session, as a reply in the viewer would (`--claim` to answer it yourself) |
| `inbox resolve <id>` | Close a whole thread |
| `projects list` | The registered projects, by group, with any problems |
| `projects scan` | Folders in your roots with no registry page yet (`--write` creates stub pages) |
| `projects show --project <name>` | One project's place in the system |
| `projects type <name> project\|module\|auto` | Mark a page as a project or a module, or go back to detection |
| `projects inbox-edits <name> on\|off\|auto` | Allow or forbid Archeion's `/inbox` editing a project's files (auto: allowed, or as its project for a module) |
| `projects ports` | Every recorded port, with clashes marked |
| `design preflight <name> [--for design\|handoff]` | What stands in the way of a design step, each problem with its fix |
| `design context <name>` | The project, its neighbours, ports in use, groups and the workspace rules, in one read-only bundle |
| `design init\|show\|list\|validate\|save\|stage\|discard` | Start a design, read it, check and save a work folder as its working copy, move its stage (`brief`, `architecture`, `plan`). `--slug` picks one of a project's designs |
| `design approve <name> [--yes]` | Shows the revision it would freeze and the registry lines it would change; with `--yes`, does it |
| `design handoff <name>` / `design package <name>` | Ask the inbox to deliver a revision / copy it into the project's `.archeion/designs/<slug>/` (needs inbox edits allowed) |
| `design consumed <name> --revision <n>` | Record that the project consumed a revision (what `/archeion:consume-design` calls) |
| `glossary list <name>` / `glossary set <name> <term> <meaning> [--alias x]` / `glossary remove <name> <term>` | A project's terms and jargon, shown on its **Glossary** tab ([ADR 0023](../decisions/0023-project-glossaries.md)). `set` adds a term or replaces the one with the same name |
| `report preflight <name>` / `report catalog <name>` | Whether a report can be built (Edge found, the frontend running) and what has no source / every section a report can hold |
| `report default <name>` / `report validate <name> --file <f>` | A starting preset with every available section / check a preset against the catalog |
| `report preset list\|show\|save\|delete <name>` | A project's saved report presets |
| `report build <name> --preset <n>` | Build a preset into a PDF in `registry/reports/<name>/` (needs the viewer's frontend running), and check it |
| `report list <name>` / `report verify <name> <file>` | The PDFs built, and a check of one against its build record |
| `report read <name> <id>...` | The content of catalog sections as JSON (what `/report-guided` reads to plan and cite) |
| `report plan save\|show\|discard\|approve <name>` | The guided report in progress: Claude saves it between rounds, the **Guided** panel shows it, `approve` turns it into a preset |
| `study scan <name>` | A read-only inventory of a project's code (Python and TS/JS): manifests, entry points, import graph, routes, outgoing HTTP calls, SQL tables, env var names, ports |
| `study list [<name>]` | Study snapshots, and how many commits behind the project each is |
| `study show <name> [<snapshot>]` | One snapshot's counts, problems and folder |
| `study changes <name>` | Files changed since the latest snapshot (what `/study --refresh` rereads) |
| `study draft save\|show\|discard <name>` | The study in progress, kept between the rounds of its conversation; the Study tab shows it as **Draft** |
| `study save <name> --from-draft` | Turn the draft into a dated snapshot |
| `study validate --file <f>` / `study save <name> --file <f>` | Check a study model, or store it as a new snapshot (`/study` does this) |
| `password set` | Changes the admin password and logs out every session |

## Tips
- **One item, one request.** Small items are claimed, answered and resolved cleanly.
- **Anchor your comments.** A comment on a passage gives Claude the quote and the lines it's about.
- **Big questions go in the terminal.** The viewer is pull-based, so a back-and-forth brainstorm goes faster in a live session.
