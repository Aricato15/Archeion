# Update notes

One short how-to per release that asks the user to do something: update Archeion, update the plugin, open new sessions, change a setting. They are the quick version of the [full update guide](../guides/update_archeion_and_plugin.md), written so someone can follow them without reading the changelog.

| Release | Archeion | Plugin | Note |
|---|---|---|---|
| [1.5.0](update-v1.5.0.md) | 1.4.0 → 1.5.0 | 0.4.0 → 0.5.1 | Design checklist and roadmap, read-only example project, `/archeion:design-consumed`, no database change |
| [1.4.0](update-v1.4.0.md) | 1.3.2 → 1.4.0 | unchanged (0.4.0) | Full screen for every diagram, remove a registered project, groups with a home you can promote a project into, a table of contents for long threads, on-demand Claude gets the project's folder, delete a thread, database migration 11 (automatic) |
| [1.3.2](update-v1.3.2.md) | 1.3.1 → 1.3.2 | unchanged (0.4.0) | Diagram and Reports-tab fixes, Edits now launches Claude in auto mode, no database change |
| [1.3.1](update-v1.3.1.md) | 1.2.0 or 1.3.0 → 1.3.1 | 0.3.0 → 0.4.0 | PDF reports, `/archeion:report` renamed `/archeion:notify` |

## Conventions

- **One file per release**, named `update-vX.Y.Z.md`, kept in this folder for good. The viewer's **Updates** tab lists the notes by the version in the file name, so keep that name exact. Add a row to the table above, newest first.
- **Write one when a release needs the user to do something.** A release that changes nothing for them needs no note.
- **Keep it to what they do.** What's new goes in two or three lines, with links to `CHANGELOG.md` and the plugin's changelog. The steps come next, then how to check that it worked, then what to do if it didn't.
- **Say who it is for** (which versions it covers) and **what is kept**: whether there's a database migration, and whether a backup is needed.
- **Say when the plugin changes.** The plugin has its own version ([ADR 0009](../decisions/0009-archeion-plugin-for-project-sessions.md)), and an open session keeps the plugin it started with.
- **Generic only.** Like every doc here, no project names, paths on your machine or personal details ([ADR 0007](../decisions/0007-keep-project-information-out-of-the-repo.md)).
- The version numbers, release date and changelog are set by `scripts/bump-version.ps1`. Write the note after the bump, so it names the right versions.

## Template

```markdown
# Update to Archeion X.Y.Z

**For:** Archeion A → **X.Y.Z**, and the plugin B → **C** (or: the plugin is unchanged).

## What's new
- ...

## Update in steps
### 1. Update Archeion
### 2. Update the plugin
### 3. Open a new session in each project

## Check that it worked
## If something looks wrong
```
