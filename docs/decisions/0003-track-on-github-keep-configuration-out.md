# 0003: Track on GitHub, keep configuration out of the repo

- Status: Accepted
- Date: 2026-11-15
- Supersedes: 0001

## Context
I changed my mind about 0001: this repo is worth tracking on GitHub. Once it's hosted, anything committed is effectively published, so secrets, machine details and personal information must never reach a commit.

## Decision
- Pushing to GitHub is allowed. Claude may add or change the remote and push, but only when I ask (amended 2026-11-15; originally I added the remote myself). The pre-push block from 0001 is removed.
- Never committed: API keys, tokens, passwords, private keys, absolute paths, email addresses and other personal information, `.env` files, SQLite databases, `settings.local.json`, `CLAUDE.local.md`.
- Machine-specific values go in a gitignored `.env`, documented by a committed `.env.example` with placeholders. Paths are relative to the repo.
- Enforcement:
  1. `.githooks/pre-commit` runs `.githooks/check-sensitive.ps1` on the staged changes and blocks the commit if it finds a secret pattern, an absolute path, a non-placeholder email or a blocked file. It's activated with `git config core.hooksPath .githooks` (once per clone). `-All` scans every tracked file.
  2. `.claude/settings.json` denies `git commit --no-verify` / `-n` and changing `core.hooksPath`.
  3. Hard rule 1 in `CLAUDE.md`.
- Allowed emails: `example.com/org/net`, GitHub noreply addresses and `anthropic.com` (commit attribution). A deliberate example line can be marked `sensitive-ok`.

## Consequences
- Commits are authored with my GitHub noreply address, so commit metadata doesn't expose my email.
- The check is pattern-based. It catches the common cases, not every possible secret, so review diffs before pushing.
- Before the first push, run the `-All` scan once.
