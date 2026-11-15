# 2026-11-15: named roots and the plugin, end-to-end test

Phase 3 of [the plan](../roadmap/2026-11-15-named-roots-and-plugin-plan.md), run on the branch `feat/named-roots-and-plugin` at app 0.4.0 and plugin 0.1.0. Everything ran against one existing workspace project, called "the test project" here. No other project was registered.

## Starting point
- The registry and database from before were backed up to `backups/2026-11-15/` (gitignored), the database with SQLite's online backup. Then both were wiped, and `setup` recreated `registry/` from the template.
- `start` refused to start: "No admin password is set."

## Results
| Check | Result |
|---|---|
| `projects scan` dry run lists every candidate and writes nothing | ✔ |
| `scan --only <name> --write` registers just the test project | ✔ (new in 0.3.0; before, `--write` registered everything) |
| `projects show` / `projects ports` with the project's real ports | ✔ |
| Named root granted (`ARCHEION_ROOTS`, set in the process environment only) and the page moved to `root: lab` | ✔ resolves, `list` shows "root lab", `--here` finds the project |
| Root revoked | ✔ "not available", with a warning that the root isn't configured |
| A bad root entry | ✔ shown as a "settings" warning |
| Plugin launcher `--where` (via `ARCHEION_HOME`, the marketplace record, or `../archeion`) | ✔ all three |
| Archeion older than the plugin's minimum | ✔ exit 3, with a message |
| Archeion not found / folder not registered | ✔ exit 2 / exit 1, with messages |
| A prompt for the project → SessionStart hook announces it → list, claim, reply | ✔ |
| Hook silent with nothing open, in an unregistered folder, and inside Archeion | ✔ |
| `inbox create` from the project → Archeion's inbox shows "from <project>", and Archeion's own hook counts it | ✔ |
| Plugin change without a version bump is refused; after `bump-version -Target plugin` it passes and the version test still passes | ✔ (the test bump was reverted) |
| `claude plugin marketplace add` + `install --scope user` | ✔ cached at `~/.claude/plugins/cache/archeion/archeion/0.1.0`, enabled in the project, off in Archeion |
| Headless session in the project running `/archeion:context` | ✔ the skill ran from the cache, compared the registry with the project's `CLAUDE.md`, and offered `/archeion:report` instead of editing the registry |

## Bugs found and fixed
- **A registry page saved with a UTF-8 byte-order mark lost its frontmatter silently.** PowerShell 5.1 and older Notepad save files that way. The project's `path` and `root` were ignored, with no warning. Fixed in `split_frontmatter`, with tests.
- **`--here` misled when a project's root isn't granted.** It said to register a project that was already registered. It now names the projects whose root isn't configured.
- **Archeion's own SessionStart hook said items come "from the viewer".** They can now come from project sessions too.

## Left for the user
- Run `set_admin_password.bat`, then `start.bat`, and check the viewer: the project page (root, ports), the "Settings" problems, and the "from <project>" badge on an item sent with `/archeion:report`.
- Try `/archeion:inbox` in an interactive session in the test project, with a prompt written in the viewer.
- To use a real folder outside the workspace, add it with `configure.bat` (`ARCHEION_ROOTS`).
- Test items were cleared afterwards: the database was deleted again (no password had been set yet), and only the test project's registry page is left.

## Follow-ups noticed
- Stub pages from `projects scan --write` set `verified:` to today, although nobody has checked them yet. It would be more honest to leave it unset until the page is filled in.
- The `_shared` workspace plugin's cached copy is older than its source (0.1.0 cached, 0.2.0 in `plugin.json`). This is the same cache behaviour the Archeion plugin's versioning guards against.
