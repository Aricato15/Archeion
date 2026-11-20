# Update to Archeion 1.5.0

**For:** Archeion 1.4.0 → **1.5.0**, and the plugin 0.4.0 → **0.5.1**. There is **no database migration** (schema stays at 11), so no backup is needed beyond your usual one. It takes about five minutes.

## What's new

- **A checklist and a roadmap in every design** ([ADR 0029](../decisions/0029-design-checklist.md)). The Design tab has a **Checklist** of features, ideas and decisions that `/design` proposes and you confirm, and a read-only **Roadmap** generated from it (Now / Next / Later / Done). A handed-off package carries both.
- **The Roadmap page pages back through versions.** A `## Released` section gives one block per version, with arrows above the three cards.
- **A read-only example project** ([ADR 0030](../decisions/0030-example-project.md)), listed as **Demo** in the sidebar, so you can try the viewer with nothing registered. Nothing about it is written or sent to Claude.
- **The plugin tells Archeion a design was consumed, reliably.** `/archeion:design-consumed` is a new skill, and `/archeion:consume-design` runs it as its last step and now uses the plugin's launcher, which PowerShell's execution policy allows. Before, a project session could be blocked and the design stayed "not handed off". The checklist support in `consume-design` came with plugin 0.5.0.
- Smaller: the sidebar folds a project when you move on, map lines are easier to see, and study diagrams no longer fail on empty names or notes.

The full list is in [`CHANGELOG.md`](../../CHANGELOG.md) and the [plugin's changelog](../../plugins/archeion/CHANGELOG.md).

## Update in steps

### 1. Update Archeion

```
stop.bat
git fetch
git checkout main
git pull
setup.bat
start.bat
```

Then reload the viewer. If something looks stale, use `restart.bat`.

### 2. Update the plugin

In any Claude Code session run `/plugin marketplace update archeion`, then update the plugin from `/plugin` (or `claude plugin update archeion@archeion` in a terminal).

### 3. Open a new session in each project

A running session keeps the plugin it started with, so it doesn't have `/archeion:design-consumed`.

If a design was already consumed but Archeion still shows it as not handed off, run `/archeion:design-consumed` in that project's session. If its receipt has no `slug`, `revision` and `thread` lines (it was written by an older plugin), the skill asks for them, or run `design consumed <project> --slug <slug> --revision <n>` through the plugin's launcher.

## Check that it worked

- The viewer's header shows **v1.5.0**.
- The sidebar has a **Demo** section.
- A design's tab has **Checklist** and **Roadmap** sections.
- In a project's new session, `/archeion:design-consumed` is listed.

## If something looks wrong

| What you see | What to do |
|---|---|
| A project session says `/archeion:design-consumed` doesn't exist | Update the plugin (step 2) and open a new session. |
| The skill says Archeion is too old | Update Archeion (step 1). The report needs Archeion 1.1.0 or newer. |
| PowerShell says running scripts is disabled | The command wasn't run through the plugin's launcher (`powershell -NoProfile -ExecutionPolicy Bypass -File "<plugin>/scripts/archeion.ps1" ...`). Use that form. |
| Anything else | See "If something looks wrong" in the [full guide](../guides/update_archeion_and_plugin.md#if-something-looks-wrong). |

## Undo

Stop Archeion, `git checkout v1.4.0`, run `setup.bat` and `start.bat`. The database is unchanged by this release, so nothing needs restoring.
