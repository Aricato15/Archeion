# 0028: Create a project or group from the viewer

- Status: Accepted (2026-11-19)
- Date: 2026-11-19
- Builds on: [ADR 0008](0008-named-project-roots.md), [ADR 0010](0010-manage-roots-and-registration-in-the-viewer.md), [ADR 0027](0027-groups-with-a-home-and-promotion.md)
- Amends: [ADR 0006](0006-multi-project-registry.md) and [ADR 0010](0010-manage-roots-and-registration-in-the-viewer.md) ("the backend never writes to a project"), and hard rule 5 in `CLAUDE.md`.

## Context
Archeion registers projects that already exist. Starting one meant making the folder by hand, or in a Claude session, and then registering it. The Projects page can show a planned project with no folder ([use case 3](../guides/use-cases.md)), but nothing makes the folder when the idea is ready to become one.

## Decision
1. **The viewer can create a new project or group.** **New project or group** on the Projects page, `projects new <name>` in the CLI and `POST /api/registry/new` ask for a root, a name, an optional title, a brief description, a status (default `planned`) and, for a project, an optional group.
2. **What it makes.** A new folder `<root>/<name>/` with a `README.md` and a `CLAUDE.md` holding the title and description, optionally a git repository (`git init`, a checkbox, on by default), and the registry page that registers it (`type: group` for a group). A group is created with a folder like any other.
3. **In a group, or beside it.** A project can be linked into a group with `group:` while living in the chosen root, because a project used by a group needn't sit in its folder. The user can instead create it inside the group's folder (only for a group with a folder here): it becomes a module, or a sub-project when it gets its own repository, with `parent:` set to the group (ADR 0027).
4. **Create-only, and nothing else.** This is the one place the backend writes outside the registry, and the rule becomes: the backend never edits an existing project's files, and may create a new folder, with those starter files, in a root the user granted. It refuses when the folder or the name exists, so nothing is overwritten, and a name is validated like a registered one (lowercase letters, digits, `.` `_` `-`), so it can't point elsewhere. If a step fails, the folder this call made is removed again.
5. **A choice about git.** `git init` is the backend's only git write, and only inside the folder it just created.

## Consequences
- A new project appears on the maps at once, as planned, and its Design tab and `/design` take it from there.
- The starter files are small and generic. A project that wants more (tests, a stack) gets it from its own session or a design handoff.
- Archeion's hard rule on writing to projects now has this one exception, recorded here and in `CLAUDE.md`.
