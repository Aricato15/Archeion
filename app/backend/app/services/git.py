"""Read-only git access for doc history. Argument lists only, never a shell."""

from __future__ import annotations

import difflib
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

REV_RE = re.compile(r"^[0-9a-f]{7,40}$")
WORKTREE = "WORKTREE"
TIMEOUT = 5

_ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"}


class GitError(RuntimeError):
    pass


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), "-c", "core.quotepath=off", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT,
            env=_ENV,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GitError(str(exc)) from exc
    if check and proc.returncode != 0:
        raise GitError(proc.stderr.strip() or f"git exited {proc.returncode}")
    return proc


def valid_rev(rev: str) -> bool:
    return bool(REV_RE.match(rev))


def head(repo: Path) -> str | None:
    proc = _git(repo, "rev-parse", "--verify", "-q", "HEAD", check=False)
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


@dataclass(frozen=True)
class Commit:
    rev: str
    short: str
    author_name: str
    date: str
    subject: str


def history(repo: Path, repo_rel: str, limit: int = 50) -> list[Commit]:
    """Commits that touched a file, newest first. Author emails are never read."""
    fmt = "%H%x1f%h%x1f%an%x1f%aI%x1f%s%x1e"
    proc = _git(repo, "log", "--follow", f"-n{limit}", f"--format={fmt}", "--", repo_rel, check=False)
    if proc.returncode != 0:
        return []
    commits = []
    for rec in proc.stdout.split("\x1e"):
        rec = rec.strip("\r\n")
        if not rec:
            continue
        rev, short, name, date, subject = rec.split("\x1f", 4)
        commits.append(Commit(rev, short, name, date, subject))
    return commits


def show_file(repo: Path, rev: str, repo_rel: str) -> str | None:
    """Content of a file at a revision, or None when it doesn't exist there."""
    proc = _git(repo, "show", f"{rev}:{repo_rel}", check=False)
    return proc.stdout if proc.returncode == 0 else None


def commit_diff(repo: Path, rev: str, repo_rel: str) -> str:
    """Unified diff of what one commit changed in one file (follows renames)."""
    proc = _git(repo, "show", "--no-color", "--format=", "--patch", "-M", rev, "--", repo_rel, check=False)
    if proc.returncode != 0:
        raise GitError(proc.stderr.strip() or "unknown revision")
    return proc.stdout


def _norm(text: str) -> str:
    return text.replace("\r\n", "\n")


def worktree_diff(repo: Path, repo_rel: str, current: str) -> str:
    """Unified diff of the working-tree file against HEAD (covers untracked files too)."""
    old = show_file(repo, "HEAD", repo_rel) if head(repo) else None
    old_lines = _norm(old or "").splitlines(keepends=True)
    new_lines = _norm(current).splitlines(keepends=True)
    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile="/dev/null" if old is None else f"a/{repo_rel}",
        tofile=f"b/{repo_rel}",
    )
    body = "".join(line if line.endswith("\n") else line + "\n" for line in diff)
    if not body:
        return ""
    return f"diff --git a/{repo_rel} b/{repo_rel}\n{body}"


def is_dirty(repo: Path, repo_rel: str, current: str) -> bool:
    """True when the working-tree content differs from HEAD (line endings ignored)."""
    if head(repo) is None:
        return True
    old = show_file(repo, "HEAD", repo_rel)
    return old is None or _norm(old) != _norm(current)
