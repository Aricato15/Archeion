"""Named project roots: the folders Archeion may read projects from (ADR 0008).

The workspace root (ARCHEION_WORKSPACE_ROOT) is always the root named "workspace". More
roots are granted in .env, as ARCHEION_ROOTS=name=folder;name=folder. A registry page
picks its root with `root: <name>`, and its `path` is then relative to that root.
Granting a root is the permission: no project outside the roots is ever read.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

WORKSPACE = "workspace"
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,31}$")


@dataclass
class Roots:
    workspace: Path
    named: dict[str, Path] = field(default_factory=dict)  # granted in .env, without workspace
    errors: list[str] = field(default_factory=list)  # entries of ARCHEION_ROOTS that were refused

    def get(self, name: str) -> Path | None:
        return self.workspace if name == WORKSPACE else self.named.get(name)

    def all(self) -> list[tuple[str, Path]]:
        return [(WORKSPACE, self.workspace), *self.named.items()]


def root_problem(folder: Path, repo_root: Path) -> str | None:
    """Why a folder can't be a root, or None. `folder` must be resolved."""
    if not folder.is_dir():
        return "isn't an existing folder"
    if folder.parent == folder:
        return "is a whole drive; grant the folder that holds the projects"
    if folder == Path.home().resolve():
        return "is your whole home folder; grant the folder that holds the projects"
    if folder.is_relative_to(repo_root.resolve()):
        return "is inside Archeion's own folder"
    return None


def parse_roots(raw: str, repo_root: Path, workspace: Path) -> Roots:
    """Parse ARCHEION_ROOTS. Bad entries are left out and reported in `errors`, so one
    typo doesn't stop the app."""
    roots = Roots(workspace=workspace.resolve())
    for entry in (raw or "").split(";"):
        entry = entry.strip()
        if not entry:
            continue
        name, sep, folder = entry.partition("=")
        name, folder = name.strip(), folder.strip().strip('"')
        if not sep or not folder:
            roots.errors.append(f"ARCHEION_ROOTS entry '{entry}' must look like name=folder")
            continue
        if not NAME_RE.match(name):
            roots.errors.append(
                f"root name '{name}' must be 2-32 characters of lowercase letters, digits and -"
            )
            continue
        if name == WORKSPACE:
            roots.errors.append("root name 'workspace' is reserved for ARCHEION_WORKSPACE_ROOT")
            continue
        if name in roots.named:
            roots.errors.append(f"root '{name}' is listed twice")
            continue
        p = Path(folder).expanduser()
        resolved = (p if p.is_absolute() else repo_root / p).resolve()
        problem = root_problem(resolved, repo_root)
        if problem:
            roots.errors.append(f"root '{name}' {problem}")
            continue
        roots.named[name] = resolved
    return roots
