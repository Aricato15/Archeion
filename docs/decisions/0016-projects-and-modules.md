# 0016: Projects and modules

- Status: Accepted (2026-11-15). Point 6 extended by [ADR 0017](0017-inbox-may-edit-registered-projects.md) (the `inbox_edits:` line).
- Date: 2026-11-15
- Extended by [ADR 0027](0027-groups-with-a-home-and-promotion.md): a third type, `group`, and a module of a group's repository belongs to the group.
- Refines: [ADR 0006](0006-multi-project-registry.md) (sub-projects). Amends: [ADR 0010](0010-manage-roots-and-registration-in-the-viewer.md) (what the backend may write).

## Context
The registry had one kind of page, a project, and `parent:` made any page a "sub-project". That hid a real difference. A service whose collectors are folders inside its repository has one codebase, one history and one Claude session. The collectors are parts of it, not projects. The viewer showed them as projects in their own right, and the inbox treated each as a separate target.

## Decision
1. **Two types.** A **project** has its own git repository. A **module** lives inside a project's repository and has no repository of its own. `kind:` stays what it was: free text for what a page does (service, collector...).
2. **Detected by default.** A page with `parent:` whose folder has no `.git` (a folder, or a file for a submodule or a worktree) is a module. Everything else is a project: a top-level page with no parent, and a repository nested in a project (a sub-project). A page whose folder this machine can't see counts as having no repository.
3. **Set by hand when detection is wrong.** `type: project` or `type: module` in the page's frontmatter overrides detection. A module needs `parent:`; a page marked `module` without one gets a warning. An unknown value gets a warning and is ignored. The type can be set three ways:
   - in the viewer, on the project page (Auto / Project / Module) or when registering a folder on the Settings page;
   - with `projects type <name> project|module|auto` in the CLI;
   - by editing the page like any other frontmatter.
4. **One repository, one inbox.** A module's `owner` is its nearest ancestor that's a project. `inbox --project <project>` and `inbox --here` (from anywhere in the project's folder, modules included) cover the project and its modules, so the session at the repository's root handles feedback left on any of them. `--project <module>` still narrows to one module.
5. **The viewer shows the difference.**
   - The sidebar uses a puzzle icon for modules.
   - The project page shows a "module of …" badge and lists its children as **Modules** and **Sub-projects**.
   - Cards count "3 modules".
   - The maps draw modules as rounded boxes.
6. **One more backend write (amends ADR 0010).** Besides `ARCHEION_ROOTS` in `.env` and creating pages, the backend may now set or remove the `type:` line in the frontmatter of an existing page in `registry/projects/` (`PUT /api/registry/projects/{id}/type`). Nothing else in the page changes, the page is found by project id and never by a path from the request, and the write is atomic. It still never writes to a project.

## Consequences
- Existing pages need no change. With no `type:`, the current registry already comes out right: the collectors inside a repository become modules.
- An item left on a module now shows up in its project's inbox too. It still carries the module's name, so the session knows where it applies.
- A project's own docs and a module's docs are still separate sources in the viewer: each page keeps its own README, CLAUDE.md and docs folder.
