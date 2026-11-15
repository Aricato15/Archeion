# 0001: Never push to a remote

- Status: Superseded by 0003 (2026-11-15)
- Date: 2026-11-15

## Context
This repo holds my private, system-wide view of all my projects, my plans and my roadmap. It's for me only and must never leave this machine through git.

## Decision
The repo has no remotes and is never pushed. This is enforced in three layers:
1. **Git hook:** `.githooks/pre-push` exits with an error on every push. It's activated with `git config core.hooksPath .githooks`, and `push.default` is set to `nothing`.
2. **Claude permissions:** `.claude/settings.json` denies `git push`, `git remote add`/`set-url`, changing `core.hooksPath`, and every `gh` command, for both the Bash and PowerShell tools.
3. **Instructions:** hard rule 1 in `CLAUDE.md`.

## Consequences
- There's no off-machine copy. Back up by copying the folder or `git bundle create <file> --all` to a private location, never a hosted git service.
- If the repo is re-initialised, `core.hooksPath` must be set again (it lives in `.git/config`).
- `--no-verify` would skip the hook. The rule forbids it, and the permission denies are the second guard.
