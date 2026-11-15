# 0008: Named project roots outside the workspace

- Status: Proposed
- Date: 2026-11-15
- Amends: [ADR 0006](0006-multi-project-registry.md) (one workspace root, paths relative to this repo)

## Context
A project can only be registered if it sits inside `ARCHEION_WORKSPACE_ROOT`, which defaults to `..`, the folder that holds Archeion. People keep projects in more than one place, for example a public folder next to Archeion and a private folder elsewhere on the machine. Moving a project just so Archeion can see it is the wrong way round. The project should be able to stay where it is, show up in the viewer, and still get its feedback.

Three constraints stay in place:
- Archeion never writes to a project.
- Drive paths never reach committed files ([ADR 0003](0003-track-on-github-keep-configuration-out.md)).
- The registry stays private ([ADR 0007](0007-keep-project-information-out-of-the-repo.md)).

## Decision
1. **Named roots, granted in `.env`.** A new setting, `ARCHEION_ROOTS`, lists extra folders Archeion may read, each with a short name:
   ```
   ARCHEION_ROOTS=private=<absolute path to the private folder>;lab=<another folder>
   ```
   - The workspace root stays as the root named `workspace`.
   - A name is 2 to 32 characters, lowercase letters, digits and `-`, so it can't be confused with a drive letter.
   - A root must be an existing folder, and can't be a drive root or a home folder as a whole.
   - Granting a root is the permission. Archeion can read only inside the workspace root and the granted roots. Removing a root from `.env` revokes access to every project under it.
   - `configure.bat` edits the list and validates each folder. The setting is defined once in `scripts/settings.schema.json`, as every setting is.
2. **A `root` field in the registry.** A page names its root, and its `path` is relative to that root:
   ```yaml
   root: private
   path: example-app
   ```
   - Without `root`, nothing changes: `path` is relative to this repo and must stay inside the workspace root, as before.
   - With `root`, `path` must be relative and stay inside that root. A page whose root isn't granted on this machine reports a problem ("root `private` isn't configured") instead of failing.
   - Sub-projects state their own `root` and `path`.
   - The registry still holds no drive paths. On another machine you map `private` to wherever that folder lives there.
3. **Discovery.** `projects scan --root <name>` scans a granted root by the same rules as the workspace (folders with a `CLAUDE.md`, plus sub-projects two levels down), and `--write` creates pages with `root` set.
4. **Everything else follows the resolved folder.** Once a page resolves to a folder, the doc sources, the allowlist of files, the read-only rule, git history, the watcher and `inbox --here` work as they do for workspace projects, because they already work from the resolved folder.
5. **The commit hook covers the new roots.** `check-sensitive.ps1` reads the root folders from `.env` and blocks the names of the project folders in them, as it already does for the workspace's folders.
6. **Claude Code access is a separate grant, made in each session.**
   - The project's session needs to run Archeion's CLI. That's covered by the project plugin ([ADR 0009](0009-archeion-plugin-for-project-sessions.md)).
   - Archeion's own session may read a project's docs only if you add the folder to `additionalDirectories` in `.claude/settings.local.json`, which is gitignored. The viewer doesn't need this, because the backend reads the files itself.

## Consequences
- A project can stay in a private folder and still be browsed, mapped and given feedback, without being moved or changed.
- Access has two sides. The root in Archeion's `.env` lets Archeion read the project. Enabling the plugin in the project lets the project take feedback. Either side can withdraw.
- The registry stays portable and free of drive paths. A page whose root isn't configured on a machine is shown with a warning, not dropped.
- `tests/` gains cases for: an unknown root, a path escaping its root, a root that is a drive root, and a page without `root` behaving exactly as before.
- This is a MINOR change: new setting, new optional field, new CLI flag ([ADR 0005](0005-semantic-versioning.md)).
