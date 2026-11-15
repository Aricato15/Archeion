# 0007: Keep project information out of the repo

- Status: Proposed (on branch `multi-regis-test`, for review)
- Date: 2026-11-15
- Amends: [ADR 0006](0006-multi-project-registry.md) (where the registry lives), hard rule 1 in `CLAUDE.md`

## Context
The repo will be published on GitHub ([ADR 0003](0003-track-on-github-keep-configuration-out.md)). In 0.2.0, the registry pages (project names, folder layout, ports, dependencies and descriptions) were committed under `docs/system/`. Project names had also crept into docs, code comments and tests. Publishing the repo would publish all of it. Anything committed also stays retrievable from history, even after it's deleted from the files.

## Decision
1. **A private working folder and a public template.**
   - `registry/` holds the real system view: `overview.md`, `projects/`, `groups/` and `interactions/`. It's gitignored.
   - `registry.example/` is the committed, empty template, with generic `example-*` content only.
   - `setup.bat` copies the template to `registry/` when it's missing, so a new clone gets a working setup.
   - The backend reads the registry from `ARCHEION_REGISTRY_DIR` (default `registry`) and shows it as the private `registry` source. Its files have no git history by design, and the viewer marks them "private".
   - Archeion's `/inbox` handles feedback on registry pages as Archeion's own.
2. **Committed files stay generic.** Docs, code, tests and commit messages describe the mechanism, never a specific project. Tests use made-up names (`alpha`, `gateway`, `datasvc`...).
3. **The commit hook enforces it.** `check-sensitive.ps1` adds two checks:
   - It blocks any file under `registry/`.
   - It blocks the names of registered projects and workspace project folders in added lines. It builds that list at commit time from `registry/` and the workspace, so the names are never written into the repo.
4. **History is cleaned before the first push.** See Remediation.

## Remediation (proposed, needs approval)
The repo has never had a remote, so nothing has left this machine. The leaked text is only in local commits:
- one line added on `main` (an example path in `CLAUDE.md`, from the commit that set up the sensitive-content check),
- five commits on `multi-regis-test`,
- the 0.2.0 registry files under `docs/system/` and `docs/interactions/map.md`.

The steps:
1. **Back up.** Write a git bundle of all branches to a folder outside the repo, deleted once the rewrite is verified.
2. **Commit the cleaned working tree** on the branch, so the newest commit is clean.
3. **Rewrite all history** with `git filter-repo`, run through `uvx` so nothing is installed globally.
   - `--invert-paths` removes `docs/system/` and `docs/interactions/map.md` from every commit.
   - `--replace-text` replaces each project name with a placeholder. Its list of names lives outside the repo.
   - Every commit hash on `main` and on the branch changes.
4. **Purge the old objects locally**, so they can't be recovered from the reflog: `git reflog expire --expire=now --all` and `git gc --prune=now --aggressive`.
5. **Verify.** Grep `git log --all -p` for every name, and check that no tree in history contains the removed paths. Then run `check-sensitive.ps1 -All`.
6. **Push only after that.** The first push then carries clean history.

If something had already been pushed, this wouldn't be enough. You'd need to force-push the rewritten history, ask GitHub Support to purge cached views and pull-request refs, and assume that clones and forks keep the old data. Any secret would have to be rotated, not just removed.

## Consequences
- Registry pages aren't versioned and aren't backed up by git. Back up `registry/` with your other private files, for example by copying the folder somewhere private.
- A new machine starts from the empty template. The registry is per machine unless you copy it over.
- The name check can be noisy if a project's name is a common word. Mark a harmless line with `sensitive-ok`.
