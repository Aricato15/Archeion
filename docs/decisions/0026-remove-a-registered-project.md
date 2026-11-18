# 0026: Remove a registered project

- Status: Accepted (2026-11-19)
- Date: 2026-11-19
- Builds on: [ADR 0007](0007-keep-project-information-out-of-the-repo.md), [ADR 0010](0010-manage-roots-and-registration-in-the-viewer.md)
- Amends: [ADR 0010](0010-manage-roots-and-registration-in-the-viewer.md), see Decision 1 (the list of files the backend writes).

## Context
Registering a project creates a page in the private registry, and nothing could undo it. A project registered by mistake, renamed or given up stayed in every list and map until its page was deleted by hand, outside the viewer.

## Decision
1. **Removing a project moves its registry page, it doesn't delete it.** The page goes from `registry/projects/<name>.md` to `registry/removed/<name>-<date>.md` (a number is added if that name exists). The loader only reads `projects/`, so the project leaves every list, map and count at once, and putting the page back restores it. This is one more write in the backend's short list (ADR 0010): a move out of `projects/`, never a change to a project's own files.
2. **Only the page moves.** The project's folder is never touched. Its studies, designs, glossary, reports and feedback stay in the registry, and are found again if a project of the same name is registered again.
3. **A project with modules or sub-projects can't be removed** until those are. The reply names them. Projects that list it in `depends_on` don't block it: the viewer says which they are, and the registry shows the usual "isn't a registered project" warning on their pages until they're updated.
4. **Three ways in, one function.** `DELETE /api/registry/projects/{name}` (behind the session like every route), the project page's and Settings' **Remove** buttons (each asks first and says what it does), and `projects remove <name>` in the CLI. All call `services/registry.py: unregister`.
5. **Removed projects are shown, and can be restored or deleted for good.** Settings lists them under **Previously registered** (name, date, and which of studies, designs, glossary and reports the registry still keeps), and a folder that was registered before shows a *previously registered as* badge next to **Register**. **Restore** moves the latest page back to `projects/` (refused while the name is registered). **Delete permanently** asks first, then deletes every removed page of that name and its `studies/`, `designs/`, `glossary/` and `reports/` entries, only for a name that isn't registered. Feedback in the database and the project's own folder are never touched. API: `GET /api/registry/removed`, `POST /api/registry/removed/{name}/restore`, `DELETE /api/registry/removed/{name}`; CLI: `projects removed|restore|purge --yes`. `registry.py: list_removed`, `restore` and `purge` do it, and `purge` is the only place the backend deletes registry data.

## Consequences
- Removal is recoverable (Restore, or moving the file back), so it needs only the dialog. Deleting permanently is the one step that can't be undone, and the CLI asks for `--yes`. `registry/removed/` is private like the rest of the registry.
- Feedback addressed to a removed project stays in the database and keeps its source name. It can't be answered by a project session until the project is registered again.
