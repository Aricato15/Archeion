"""Named project roots: the folders Archeion may read projects from (ADR 0008).

Nothing is granted by default (ADR 0012). Roots are granted in .env, as
ARCHEION_ROOTS=name=folder;name=folder, usually from the viewer's Settings page. The older
workspace root (ARCHEION_WORKSPACE_ROOT, empty by default) is the root named "workspace"
when it's set: pages without `root:` resolve inside it. A registry page
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
    workspace: Path | None = None  # ARCHEION_WORKSPACE_ROOT; None: not granted
    named: dict[str, Path] = field(default_factory=dict)  # granted in .env, without workspace
    errors: list[str] = field(default_factory=list)  # entries of ARCHEION_ROOTS that were refused

    def get(self, name: str) -> Path | None:
        return self.workspace if name == WORKSPACE else self.named.get(name)

    def all(self) -> list[tuple[str, Path]]:
        head = [(WORKSPACE, self.workspace)] if self.workspace is not None else []
        return [*head, *self.named.items()]


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


def parse_roots(raw: str, repo_root: Path, workspace: Path | None) -> Roots:
    """Parse ARCHEION_ROOTS. Bad entries are left out and reported in `errors`, so one
    typo doesn't stop the app."""
    roots = Roots(workspace=workspace.resolve() if workspace is not None else None)
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


# --- editing from the viewer (ADR 0010) -------------------------------------------------

ENV_KEY = "ARCHEION_ROOTS"
WORKSPACE_KEY = "ARCHEION_WORKSPACE_ROOT"


def format_roots(entries: list[tuple[str, str]]) -> tuple[str, list[str]]:
    """The ARCHEION_ROOTS value for (name, folder) pairs, and the problems that stop it
    being written. Folders are written with forward slashes, which Windows accepts and
    which .env quoting can't turn into escape sequences."""
    problems: list[str] = []
    parts: list[str] = []
    for name, folder in entries:
        name, folder = name.strip(), folder.strip()
        if not folder:
            problems.append(f"root '{name}' needs a folder")
            continue
        if any(c in folder for c in ';#"\r\n'):
            problems.append(f"root '{name}': the folder can't contain ; # or quotes")
            continue
        parts.append(f"{name}={folder.replace(chr(92), '/')}")
    return ";".join(parts), problems


def env_value(value: str) -> str:
    return f'"{value}"' if re.search(r"[\s#']", value) else value


def write_env_roots(env_path: Path, value: str) -> None:
    write_env(env_path, {ENV_KEY: value})


def write_env(env_path: Path, values: dict[str, str]) -> None:
    """Set these keys in .env, leaving every other line as it was. The previous file is
    kept as .env.bak, as configure.bat does."""
    old = env_path.read_text(encoding="utf-8-sig") if env_path.is_file() else ""
    patterns = {k: re.compile(rf"^\s*(?:export\s+)?{k}\s*=") for k in values}
    lines: list[str] = []
    done: set[str] = set()
    for raw in old.splitlines():
        key = next((k for k, pat in patterns.items() if pat.match(raw)), None)
        if key is None:
            lines.append(raw)
        elif key not in done:
            lines.append(f"{key}={env_value(values[key])}")
            done.add(key)
    if not old:
        lines.append("# Machine-specific and gitignored: never commit this file. configure.bat edits it.")
    lines += [f"{k}={env_value(v)}" for k, v in values.items() if k not in done]
    if env_path.is_file():
        env_path.with_name(env_path.name + ".bak").write_bytes(env_path.read_bytes())
    tmp = env_path.with_name(env_path.name + ".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    tmp.replace(env_path)
