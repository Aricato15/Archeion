"""Doc sources: this repo's docs/ ("archeion"), the gitignored registry folder ("registry",
ADR 0007), plus, read-only, each registered project's own README.md, CLAUDE.md,
CHANGELOG.md, ROADMAP.md and docs folder (ADR 0006).

Every file access goes through Source.resolve(), which applies the same path rules as
before (no '..', no dotfiles, allowed types, size limit, no symlinks out) plus the
source's own allowlist. Nothing here ever writes to a project.
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from pathlib import Path

from ..paths import ALLOWED_EXT, MARKDOWN_EXT, MAX_FILE_BYTES, DocNotFound, DocPathError, validate_rel_path
from .registry import REGISTRY_ID, SELF_ID, Project, Registry, load_registry, unregistered

# Sources that are folders of this repo: every allowed file in them is served.
FULL_KINDS = {SELF_ID, REGISTRY_ID}

TOP_FILES = ("README.md", "CLAUDE.md", "CHANGELOG.md", "ROADMAP.md")
ROADMAP_CANDIDATES = ("docs/roadmap/roadmap.md", "docs/roadmap.md", "ROADMAP.md")


class SourceNotFound(LookupError):
    pass


@dataclass
class Source:
    id: str
    title: str
    root: Path  # paths are relative to this folder
    kind: str  # "archeion" | "registry" | "project"
    docs_dir: str | None = None  # project sources: the only folder besides TOP_FILES
    project: Project | None = field(default=None, repr=False)

    def allows(self, rel: str) -> bool:
        if self.kind in FULL_KINDS:
            return True
        if rel in TOP_FILES:
            return True
        return bool(self.docs_dir) and rel.startswith(f"{self.docs_dir}/")

    def resolve(self, rel: str, *, allowed: set[str] | None = None, must_exist: bool = True) -> Path:
        rel = validate_rel_path(rel)
        suffix = Path(rel).suffix.lower()
        if suffix not in (allowed or ALLOWED_EXT):
            raise DocPathError("file type not allowed")
        if not self.allows(rel):
            raise DocPathError("not part of this project's docs")
        root = self.root.resolve()
        target = (root / rel).resolve()
        if not target.is_relative_to(root):
            raise DocPathError("outside the source")
        if must_exist:
            if not target.is_file():
                raise DocNotFound(rel)
            if target.stat().st_size > MAX_FILE_BYTES:
                raise DocPathError("file too large")
        return target

    def files(self, exts: set[str] | None = None) -> list[tuple[str, Path]]:
        """(rel, path) of every visible, allowed file in this source, sorted."""
        exts = exts or ALLOWED_EXT
        root = self.root.resolve()
        out: list[tuple[str, Path]] = []
        candidates: list[Path] = []
        if self.kind in FULL_KINDS:
            candidates = sorted(root.rglob("*"))
        else:
            candidates = [root / f for f in TOP_FILES]
            if self.docs_dir and (root / self.docs_dir).is_dir():
                candidates += sorted((root / self.docs_dir).rglob("*"))
        for p in candidates:
            if not p.is_file() or p.suffix.lower() not in exts:
                continue
            try:
                rel = p.relative_to(root).as_posix()
            except ValueError:
                continue
            if any(part.startswith(".") for part in rel.split("/")) or not self.allows(rel):
                continue
            if not p.resolve().is_relative_to(root):
                continue
            out.append((rel, p))
        return out

    def tree(self) -> dict:
        root = self.root.resolve()
        top: dict = {"name": self.id, "path": "", "type": "dir", "children": []}
        index: dict[str, dict] = {"": top}
        for rel, _ in self.files():
            parts = rel.split("/")
            for i in range(1, len(parts)):
                key = "/".join(parts[:i])
                if key not in index:
                    node = {"name": parts[i - 1], "path": key, "type": "dir", "children": []}
                    index["/".join(parts[: i - 1])]["children"].append(node)
                    index[key] = node
            index["/".join(parts[:-1])]["children"].append({"name": parts[-1], "path": rel, "type": "file"})
        # Empty folders still show for this repo's own sources (e.g. docs/notes/).
        if self.kind in FULL_KINDS and root.is_dir():
            for d in sorted(root.rglob("*")):
                rel = d.relative_to(root).as_posix()
                if not d.is_dir() or d.is_symlink() or any(x.startswith(".") for x in rel.split("/")):
                    continue
                parts = rel.split("/")
                for i in range(1, len(parts) + 1):
                    key = "/".join(parts[:i])
                    if key not in index:
                        node = {"name": parts[i - 1], "path": key, "type": "dir", "children": []}
                        index["/".join(parts[: i - 1])]["children"].append(node)
                        index[key] = node

        def sort(node: dict) -> None:
            node["children"].sort(key=lambda n: (n["type"] == "file", n["name"].lower()))
            for c in node["children"]:
                if c["type"] == "dir":
                    sort(c)

        sort(top)
        return top

    def watch_paths(self) -> tuple[list[Path], list[Path]]:
        """(flat, deep): folders to watch without and with recursion.

        A project's root is watched flat, so new top-level files (README.md appearing later)
        are seen without walking its venv/ or node_modules/. Its docs folder is watched deep.
        """
        root = self.root.resolve()
        if not root.is_dir():
            return [], []
        if self.kind in FULL_KINDS:
            return [], [root]
        deep = [root / self.docs_dir] if self.docs_dir and (root / self.docs_dir).is_dir() else []
        return [root], deep

    def roadmap_path(self) -> str | None:
        if self.kind == REGISTRY_ID:
            return None
        if self.kind == SELF_ID:
            return "roadmap/roadmap.md" if (self.root / "roadmap/roadmap.md").is_file() else None
        for rel in ROADMAP_CANDIDATES:
            if self.allows(rel) and (self.root / rel).is_file():
                return rel
        return None

    def public(self) -> dict:
        return {"id": self.id, "title": self.title, "kind": self.kind}


class SourceManager:
    """The registry plus the sources built from it; reloaded when registry pages change."""

    def __init__(self, docs_root: Path, registry_root: Path, repo_root: Path, workspace_root: Path) -> None:
        self.docs_root = docs_root
        self.registry_root = registry_root
        self.repo_root = repo_root
        self.workspace_root = workspace_root
        self._lock = threading.Lock()
        self.version = 0
        self.changed = asyncio.Event()
        self.registry = Registry()
        self.sources: dict[str, Source] = {}
        self.reload()

    def reload(self) -> None:
        reg = load_registry(self.registry_root, self.repo_root, self.workspace_root)
        sources = {
            SELF_ID: Source(SELF_ID, "Archeion", self.docs_root, SELF_ID),
            REGISTRY_ID: Source(REGISTRY_ID, "Registry (private)", self.registry_root, REGISTRY_ID),
        }
        for p in reg.projects.values():
            if p.dir is not None:
                sources[p.id] = Source(p.id, p.title, p.dir, "project", p.docs_dir, p)
        with self._lock:
            self.registry = reg
            self.sources = sources
            self.version += 1
        # Not set here: reload() may run in a worker thread, and asyncio.Event isn't
        # thread-safe. The watcher sets `changed` on the event loop after reloading.

    def get(self, source_id: str) -> Source:
        source = self.sources.get(source_id)
        if source is None:
            raise SourceNotFound(source_id)
        return source

    def all(self) -> list[Source]:
        return list(self.sources.values())

    def locate(self, path: Path) -> tuple[Source, str] | None:
        """The source a filesystem path belongs to, and its rel path. Deepest root wins,
        so a sub-project's files aren't attributed to its parent."""
        path = path.absolute()
        best: tuple[Source, str] | None = None
        for s in self.sources.values():
            root = s.root.resolve()
            try:
                rel = path.relative_to(root).as_posix()
            except ValueError:
                try:
                    rel = path.resolve().relative_to(root).as_posix()
                except ValueError:
                    continue
            if best is None or len(root.parts) > len(best[0].root.resolve().parts):
                best = (s, rel)
        return best

    def unregistered(self) -> list[dict]:
        return unregistered(self.registry, self.repo_root, self.workspace_root)

    def is_registry_page(self, source_id: str, rel: str) -> bool:
        return (
            source_id == REGISTRY_ID
            and rel.startswith(("projects/", "groups/"))
            and rel.endswith(MARKDOWN_EXT)
        )


def read_text(path: Path) -> str:
    return path.read_bytes()[:MAX_FILE_BYTES].decode("utf-8", errors="replace")
