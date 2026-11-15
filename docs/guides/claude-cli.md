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
| Work on one project | That project's folder | `/archeion:inbox` |

Start it at Archeion's root, not a subfolder: the session-start hook that announces open feedback only fires there.

## In Archeion's session
| Command | What it does |
|---|---|
| `/inbox` | Works through the feedback left for Archeion |
| `/loop 10m /inbox` | Checks the inbox every 10 minutes while the terminal is open, so items you send from the viewer get picked up without you asking |
| `/workspace-core:commit` | Reviews the staged changes, proposes a Conventional Commits message, and asks before committing |
| `/workspace-core:handoff` | Writes a handoff note to `docs/notes/` for the next session |

Or just ask in plain words: "register the new project in my workspace", "check the registry against the projects", "plan the next step on the roadmap".

## In a project's session (Archeion plugin)
| Command | What it does |
|---|---|
| `/archeion:inbox` | Works through the feedback left for this project |
| `/archeion:context` | Where this project sits: its group, what it depends on, what uses it, its ports |
| `/archeion:ports` | The ports every project uses, before you pick a new one |
| `/archeion:report` | Tells Archeion about a change the registry needs (a port, a dependency, a rename) |

A project session never edits Archeion's registry. It reports, and Archeion's session makes the change.

## Archeion's own CLI
Run these from Archeion's root folder: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/archeion.ps1 <command>`.

| Command | What it does |
|---|---|
| `inbox list` | Open feedback, with the projects that have items waiting |
| `projects list` | The registered projects, by group, with any problems |
| `projects scan` | Folders in your roots with no registry page yet (`--write` creates stub pages) |
| `projects show --project <name>` | One project's place in the system |
| `projects ports` | Every recorded port, with clashes marked |
| `password set` | Changes the admin password and logs out every session |

## Tips
- **One item, one request.** Small items are claimed, answered and resolved cleanly.
- **Anchor your comments.** A comment on a passage gives Claude the quote and the lines it's about.
- **Big questions go in the terminal.** The viewer is pull-based, so a back-and-forth brainstorm goes faster in a live session.
