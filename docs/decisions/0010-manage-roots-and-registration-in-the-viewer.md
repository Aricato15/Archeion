# 0010: Manage roots and register projects from the viewer

- Status: Accepted (2026-11-15)
- Date: 2026-11-15
- Amends: [ADR 0008](0008-named-project-roots.md) (roots edited only with `configure.bat`), [ADR 0006](0006-multi-project-registry.md) (registry pages written only by hand or by `projects scan --write`)

## Context
Granting a root means running `configure.bat` and restarting Archeion. Registering a project means running `projects scan --write` from a terminal. Both are things you decide while looking at the viewer, so the viewer should do them:
1. a settings page where you add and remove roots;
2. for each root, the projects in it, and which are already registered;
3. a way to register the ones that aren't.

Until now the backend wrote only to its own database. This is the first time it writes files, so the limits need to be exact.

## Decision
1. **The backend writes two things, and nothing else.**
   - The `ARCHEION_ROOTS` line of the repo-root `.env`. Every other line stays as it was, and the previous file is kept as `.env.bak`, as `configure.bat` does.
   - New pages in `registry/projects/`. It only creates them: a page that exists is never overwritten, edited or deleted from the viewer. Filling a page in stays a job for you or a Claude session.
   - It still never writes to a project ([ADR 0006](0006-multi-project-registry.md)), nor to this repo's tracked files.
2. **The same rules as `configure.bat`.** A root is checked by `parse_roots` in `roots.py`, the code the backend already uses to read `.env`. A save that has any problem is refused as a whole, with every problem listed, and `.env` isn't touched.
3. **Changes apply without a restart.** After a save the backend reloads the registry with the new roots, restarts its file watchers and tells the viewer (`registry.changed`). Removing a root makes its projects unavailable at once. The page says which registered projects use a root before you remove it.
4. **Set in the environment wins.** If `ARCHEION_ROOTS` is set in the process environment, it overrides `.env`, so a save would have no effect after a restart. The page then shows the roots read-only and says why.
5. **Registration from the list only.** The viewer registers a folder that discovery found in a root (a folder with a `CLAUDE.md`, or a sub-project with a manifest), using the same stub as `projects scan --write`. You can change the name. You can't type an arbitrary path, so a page can't point outside the roots.
6. **`verified` stays unset on new pages.** A stub hasn't been checked against the project, so it no longer claims it was. The page gets a date when someone checks it.
7. **The usual protections apply.** These are ordinary endpoints behind the admin session and the Origin check. Granting a folder from the viewer gives the same access as granting it in `configure.bat`: Archeion reads only the allowlisted files of registered projects in it.

## Consequences
- Folder paths of roots are shown in the viewer. That's fine: the viewer is local and behind the login. They still never reach committed files, because `.env` and `registry/` are gitignored.
- `configure.bat` and the viewer edit the same line. Whichever saves last wins, and `.env.bak` keeps the version before.
- The backend can now change what it may read. A logged-in session could already ask Claude to do the same through the feedback loop, and the login is the boundary for both.
