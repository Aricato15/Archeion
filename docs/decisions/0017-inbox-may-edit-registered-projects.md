# 0017: Archeion's inbox may edit registered projects

- Status: Accepted (2026-11-15)
- Date: 2026-11-15
- Amends: [ADR 0006](0006-multi-project-registry.md) (each project's session handles its own items) and [ADR 0016](0016-projects-and-modules.md) (what the backend may write).

## Context
Feedback written in the viewer targets a project, and until now only that project's own session (`/archeion:inbox`, from the plugin, ADR 0009) could act on it. Archeion's `/inbox` listed such items as "waiting elsewhere" and left them alone, because this repo never edited sibling projects. With the inbox terminal running from the viewer (ADR 0013), that meant an item for another project waited until someone opened that project's session, even when the change was small and clear.

## Decision
1. **Archeion's `/inbox` handles every registered project's items.** For an item that targets a project, it may edit that project's files, but only to carry out that item. Outside the inbox, sessions in Archeion still never edit sibling projects.
2. **The project's rules apply.** Before editing, the session reads the project's `CLAUDE.md` and the relevant part of its `docs/`, works only inside the project's folder (a module's changes land in its project's repository), and runs the project's tests and linters before replying. It never commits in the project. The reply lists the changed files relative to the project's folder, and the user commits from that project.
3. **A switch per project, in the private registry.** `inbox_edits: true|false` in the frontmatter of the project's page in `registry/projects/` says whether `/inbox` may edit it. Without the line a project is allowed, and a module follows its project. Pages created by the Register button or `projects scan --write` write `inbox_edits: true` for a project, so the setting is visible from the start; a module's new page leaves it out. Nothing is added to the projects' own repositories, so they never have to name Archeion.
4. **Set it three ways:** the project page in the viewer (Auto / Allowed / Not allowed), `projects inbox-edits <name> on|off|auto` in the CLI, or editing the page.
5. **When edits aren't allowed** (the switch is off, or the folder isn't available on this machine), `/inbox` still answers questions and reviews from what it can read, and leaves changes to the project's own session, saying so in its reply.
6. **The CLI tells the session.** `inbox show` prints the target project, its folder and whether edits are allowed (`target` in `--json`), so the skill doesn't have to work it out.
7. **One more backend write (amends ADR 0016).** Besides `type:`, the backend may set or remove the `inbox_edits:` line of an existing page in `registry/projects/` (`PUT /api/registry/projects/{id}/inbox-edits`), the same way: found by project id, nothing else in the page changes, written atomically. The backend itself still never writes to a project. The edits in point 1 are made by the Claude session, not by the server.

## Consequences
- One loop in Archeion can clear the whole inbox. The project's own session and `/archeion:inbox` keep working as before, and claiming an item still stops two sessions working on it at once.
- Edits outside Archeion's folder may ask for permission. To avoid that, grant the project roots as extra working directories in `.claude/settings.local.json` (`permissions.additionalDirectories`). That file is gitignored and per machine, so the folders never reach the repository.
- The session working in a project doesn't load that project's `CLAUDE.md` by itself, which is why point 2 makes reading it a step of the skill rather than an assumption.
- Changes to several repositories can be left uncommitted at once. Each reply says which project's files changed, so they can be committed from the right place.
