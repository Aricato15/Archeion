"""Repo locations and the one function that turns a client-supplied doc path into a file."""

from __future__ import annotations

import re
from pathlib import Path

# app/backend/app/paths.py -> parents: app (package), backend, app, <repo root>
REPO_ROOT = Path(__file__).resolve().parents[3]

MARKDOWN_EXT = ".md"
IMAGE_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
}
ALLOWED_EXT = {MARKDOWN_EXT, *IMAGE_TYPES}
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_PATH_LEN = 512

_DRIVE = re.compile(r"^[A-Za-z]:")


class DocPathError(ValueError):
    """The path is not an allowed doc path (malformed, outside docs/ or wrong type)."""


class DocNotFound(LookupError):
    """The path is well-formed but no such doc exists."""


def validate_rel_path(rel: str) -> str:
    """Check the shape of a doc path relative to docs/ and return it normalised.

    Rejects absolute paths, drive letters, backslashes, NUL, empty segments,
    '.'/'..' segments and dotfiles. Pure string checks, no filesystem access.
    """
    if not rel or len(rel) > MAX_PATH_LEN:
        raise DocPathError("invalid path")
    if "\x00" in rel or "\\" in rel or rel.startswith("/") or _DRIVE.match(rel):
        raise DocPathError("invalid path")
    parts = rel.split("/")
    for part in parts:
        if part in ("", ".", "..") or part.startswith("."):
            raise DocPathError("invalid path")
    return "/".join(parts)


def resolve_doc_path(docs_root: Path, rel: str, *, allowed: set[str] | None = None) -> Path:
    """Resolve a client-supplied path to a file under docs_root, or raise.

    Every route that touches a doc goes through here.
    """
    rel = validate_rel_path(rel)
    suffix = Path(rel).suffix.lower()
    if suffix not in (allowed or ALLOWED_EXT):
        raise DocPathError("file type not allowed")
    root = docs_root.resolve()
    target = (root / rel).resolve()
    if not target.is_relative_to(root):
        raise DocPathError("outside docs/")
    if not target.is_file():
        raise DocNotFound(rel)
    if target.stat().st_size > MAX_FILE_BYTES:
        raise DocPathError("file too large")
    return target


def to_rel(docs_root: Path, path: Path) -> str:
    """Path of a file under docs_root, as a docs-relative posix string."""
    return path.resolve().relative_to(docs_root.resolve()).as_posix()
