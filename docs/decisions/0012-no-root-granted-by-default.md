# 0012: No root granted by default

- Status: Accepted (2026-11-15)
- Date: 2026-11-15
- Amends: [ADR 0006](0006-multi-project-registry.md) (one workspace root, default `..`), [ADR 0008](0008-named-project-roots.md) (the workspace is always the root named `workspace`), [ADR 0010](0010-manage-roots-and-registration-in-the-viewer.md)

## Context
`ARCHEION_WORKSPACE_ROOT` defaulted to `..`, so a fresh Archeion could already read every sibling folder of its own, and the Settings page showed a root you never added. A clean start should grant nothing: you decide which folders Archeion may read, in the same place you manage the other roots.

## Decision
1. **`ARCHEION_WORKSPACE_ROOT` is empty by default.** With no roots granted, Archeion reads no project, discovery finds nothing, and the CLI and the Settings page say to add a root.
2. **New roots are named roots**, added on the Settings page (`ARCHEION_ROOTS`). To get the old behaviour, add the folder that holds Archeion as a named root, for example `projects`, and give pages `root: projects`.
3. **The workspace root still works when it's set**, for older setups. It's the root named `workspace`, pages without `root:` resolve inside it, and the Settings page lists it and can remove it (`ARCHEION_WORKSPACE_ROOT=` in `.env`). It can't be added there. The name `workspace` stays reserved.
4. A page without `root:` while no workspace root is set is unavailable, with a warning saying to add its folder as a root and set `root:`.

## Consequences
- An upgraded `.env` that sets `ARCHEION_WORKSPACE_ROOT=..` (as `configure.bat` used to write) keeps working unchanged.
- The registry's examples and template now use `root:`.
