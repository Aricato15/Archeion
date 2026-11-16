"""Read-only git access for doc history. Argument lists only, never a shell.

Every call takes `cwd` (the folder a source's paths are relative to, e.g. docs/ or a
project's root) and `rel` (a path relative to it). git is run with -C cwd, and
revision paths use the `rev:./rel` form, so the same code works for this repo's docs
and for any registered project's own repo.
"""

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


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(cwd), "-c", "core.quotepath=off", *args],
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


def head(cwd: Path) -> str | None:
    proc = _git(cwd, "rev-parse", "--verify", "-q", "HEAD", check=False)
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def is_worktree_dirty(cwd: Path) -> bool | None:
    """Whether the folder has uncommitted changes (None when it isn't in a git repository)."""
    proc = _git(cwd, "status", "--porcelain", "--untracked-files=no", "--", ".", check=False)
    if proc.returncode != 0:
        return None
    return bool(proc.stdout.strip())


def commits_since(cwd: Path, rev: str) -> int | None:
    """How many commits HEAD is ahead of `rev`, counting only those touching this folder.
    None when that can't be told (no repository, or `rev` isn't known here)."""
    if not valid_rev(rev):
        return None
    proc = _git(cwd, "rev-list", "--count", f"{rev}..HEAD", "--", ".", check=False)
    if proc.returncode != 0:
        return None
    try:
        return int(proc.stdout.strip())
    except ValueError:
        return None


def changed_files(cwd: Path, rev: str) -> list[str] | None:
    """Files in this folder changed between `rev` and the working tree, relative to it."""
    if not valid_rev(rev):
        return None
    proc = _git(cwd, "diff", "--name-only", "--relative", rev, "--", ".", check=False)
    if proc.returncode != 0:
        return None
    return sorted(line for line in proc.stdout.splitlines() if line.strip())


@dataclass(frozen=True)
class Commit:
    rev: str
    short: str
    author_name: str
    date: str
    subject: str


def history(cwd: Path, rel: str, limit: int = 50) -> list[Commit]:
    """Commits that touched a file, newest first. Author emails are never read."""
    fmt = "%H%x1f%h%x1f%an%x1f%aI%x1f%s%x1e"
    proc = _git(cwd, "log", "--follow", f"-n{limit}", f"--format={fmt}", "--", rel, check=False)
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


def show_file(cwd: Path, rev: str, rel: str) -> str | None:
    """Content of a file at a revision, or None when it doesn't exist there."""
    proc = _git(cwd, "show", f"{rev}:./{rel}", check=False)
    return proc.stdout if proc.returncode == 0 else None


def commit_diff(cwd: Path, rev: str, rel: str) -> str:
    """Unified diff of what one commit changed in one file."""
    proc = _git(cwd, "show", "--no-color", "--format=", "--patch", "-M", rev, "--", rel, check=False)
    if proc.returncode != 0:
        raise GitError(proc.stderr.strip() or "unknown revision")
    return proc.stdout


def _norm(text: str) -> str:
    return text.replace("\r\n", "\n")


def worktree_diff(cwd: Path, rel: str, current: str) -> str:
    """Unified diff of the working-tree file against HEAD (covers untracked files too)."""
    old = show_file(cwd, "HEAD", rel) if head(cwd) else None
    old_lines = _norm(old or "").splitlines(keepends=True)
    new_lines = _norm(current).splitlines(keepends=True)
    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile="/dev/null" if old is None else f"a/{rel}",
        tofile=f"b/{rel}",
    )
    body = "".join(line if line.endswith("\n") else line + "\n" for line in diff)
    if not body:
        return ""
    return f"diff --git a/{rel} b/{rel}\n{body}"


def is_ignored(cwd: Path, rel: str) -> bool:
    """True when git ignores the file (e.g. the private registry): it has no history by design."""
    return _git(cwd, "check-ignore", "-q", "--", rel, check=False).returncode == 0


def is_dirty(cwd: Path, rel: str, current: str) -> bool:
    """True when the working-tree content differs from HEAD (line endings ignored).

    A folder that isn't in a git repo at all is never reported as dirty.
    """
    if head(cwd) is None:
        return _git(cwd, "rev-parse", "--git-dir", check=False).returncode == 0
    old = show_file(cwd, "HEAD", rel)
    return old is None or _norm(old) != _norm(current)
