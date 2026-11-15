"""The project registry: which projects exist, how they nest and group, and how they connect.

It lives in the gitignored registry folder (ARCHEION_REGISTRY_DIR, default registry/;
ADR 0007): one Markdown page per project in projects/ and one per group (a system of
related projects) in groups/. The structural facts live in YAML frontmatter; the page
body holds the cross-project notes (ADR 0006). Files starting with "_" are templates.

    ---
    name: example-collector                       # id; defaults to the file name
    title: Example collector                      # optional display name
    path: ../example-service/collectors/example   # relative to this repo's root, or to `root`
    root: private                                 # optional: a folder granted in ARCHEION_ROOTS
    parent: example-service                       # makes this a sub-project
    group: example-system                         # a groups/<group>.md page
    status: active                                # active | paused | archived | planned
    kind: library                                 # free text: service, frontend, library...
    ports: [20100]
    depends_on: [example-service]                 # projects this one calls or imports
    docs_dir: docs                                # where its docs live inside `path`
    verified: 2026-11-15                          # when the frontmatter was last checked
    ---
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

import yaml

from .roots import WORKSPACE, Roots

FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?", re.S)
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
STATUSES = {"active", "paused", "archived", "planned"}
PROJECTS_DIR = "projects"
GROUPS_DIR = "groups"
SELF_ID = "archeion"  # this repo's docs/ source, never a registered project
REGISTRY_ID = "registry"  # the registry folder's own source, never a registered project
RESERVED_IDS = {SELF_ID, REGISTRY_ID}


def split_frontmatter(text: str) -> tuple[dict, str, str | None]:
    """(frontmatter, body, error). The body keeps its text; the frontmatter is parsed YAML.
    A leading byte-order mark is ignored: Windows tools (PowerShell 5.1, older Notepad)
    write one, and the page would otherwise lose its frontmatter without a warning."""
    text = text.removeprefix("﻿")
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text, None
    try:
        data = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as exc:
        return {}, text[m.end() :], f"invalid frontmatter: {exc}"
    if not isinstance(data, dict):
        return {}, text[m.end() :], "frontmatter must be a mapping"
    return data, text[m.end() :], None


def _title_of(body: str, fallback: str) -> str:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def _summary_of(body: str) -> str:
    """The first paragraph of plain text after the title, for cards."""
    para: list[str] = []
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("#"):
            if para:
                break
            continue
        if not s:
            if para:
                break
            continue
        if s.startswith(("|", "-", "*", "```", ">")) and not para:
            continue
        para.append(s)
    return " ".join(para)[:300]


def _str_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value if v is not None]
    return [str(value)]


@dataclass
class Project:
    id: str
    title: str
    page: str  # docs-relative path of its registry page
    path: str | None = None
    root: str | None = None  # a named root (ADR 0008); None: path is relative to this repo
    parent: str | None = None
    group: str | None = None
    status: str = "active"
    kind: str | None = None
    ports: list[int] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    docs_dir: str = "docs"
    verified: str | None = None
    summary: str = ""
    available: bool = False  # path resolves to a folder inside its root
    children: list[str] = field(default_factory=list)
    used_by: list[str] = field(default_factory=list)
    dir: Path | None = field(default=None, repr=False)

    def public(self) -> dict:
        d = asdict(self)
        d.pop("dir")
        return d


@dataclass
class Group:
    id: str
    title: str
    page: str
    summary: str = ""
    projects: list[str] = field(default_factory=list)


@dataclass
class Registry:
    projects: dict[str, Project] = field(default_factory=dict)
    groups: dict[str, Group] = field(default_factory=dict)
    warnings: list[dict] = field(default_factory=list)

    def warn(self, page: str, message: str) -> None:
        self.warnings.append({"page": page, "message": message})

    def public(self) -> dict:
        return {
            "projects": [p.public() for p in self.projects.values()],
            "groups": [asdict(g) for g in self.groups.values()],
            "warnings": self.warnings,
        }

    def project_for_dir(self, folder: Path) -> Project | None:
        """The registered project whose folder contains `folder` (deepest match wins)."""
        folder = folder.resolve()
        best: Project | None = None
        for p in self.projects.values():
            if p.dir is None or not folder.is_relative_to(p.dir):
                continue
            if best is None or len(p.dir.parts) > len(best.dir.parts):  # type: ignore[union-attr]
                best = p
        return best


def _as_roots(roots: Roots | Path) -> Roots:
    return roots if isinstance(roots, Roots) else Roots(workspace=roots.resolve())


def _resolve_project_dir(
    repo_root: Path, roots: Roots, raw: str, root: str | None = None
) -> tuple[Path | None, str | None]:
    """Without `root`, `raw` is relative to this repo and must stay in the workspace (ADR
    0006). With `root`, it's relative to that granted folder and must stay in it (ADR 0008)."""
    if re.match(r"^[A-Za-z]:", raw) or raw.startswith(("/", "\\")):
        if root:
            return None, f"path must be relative to the root '{root}' (e.g. my-service)"
        return None, "path must be relative to this repo's root (e.g. ../my-service)"
    if root:
        bound = roots.get(root)
        if bound is None:
            return None, f"root '{root}' isn't configured on this machine (ARCHEION_ROOTS in .env)"
        target, outside = (bound / raw).resolve(), f"path points outside the root '{root}'"
    else:
        bound = roots.workspace
        target, outside = (repo_root / raw).resolve(), "path points outside the workspace"
    if not target.is_relative_to(bound):
        return None, outside
    if target.is_relative_to(repo_root.resolve()):
        return None, "path points at this repo itself"
    if not target.is_dir():
        return None, "path doesn't exist on this machine"
    return target, None


def load_registry(registry_root: Path, repo_root: Path, roots: Roots | Path) -> Registry:
    reg = Registry()
    roots = _as_roots(roots)
    for err in roots.errors:
        reg.warn("", f".env: {err}")

    groups_dir = registry_root / GROUPS_DIR
    if groups_dir.is_dir():
        for page in sorted(groups_dir.glob("*.md")):
            if page.name.lower() == "readme.md" or page.name.startswith((".", "_")):
                continue
            rel = page.relative_to(registry_root).as_posix()
            meta, body, err = split_frontmatter(page.read_text(encoding="utf-8", errors="replace"))
            if err:
                reg.warn(rel, err)
            gid = str(meta.get("name") or page.stem)
            reg.groups[gid] = Group(
                gid, str(meta.get("title") or _title_of(body, gid)), rel, _summary_of(body)
            )

    projects_dir = registry_root / PROJECTS_DIR
    pages = sorted(projects_dir.rglob("*.md")) if projects_dir.is_dir() else []
    for page in pages:
        if page.name.lower() == "readme.md" or any(x.startswith((".", "_")) for x in page.parts[-3:]):
            continue
        rel = page.relative_to(registry_root).as_posix()
        meta, body, err = split_frontmatter(page.read_text(encoding="utf-8", errors="replace"))
        if err:
            reg.warn(rel, err)
        pid = str(meta.get("name") or page.stem)
        if not ID_RE.match(pid):
            reg.warn(rel, f"'{pid}' isn't a valid project name (lowercase letters, digits, . _ -)")
            continue
        if pid in RESERVED_IDS:
            reg.warn(rel, f"'{pid}' is reserved for Archeion's own sources; pick another name")
            continue
        if pid in reg.projects:
            reg.warn(rel, f"duplicate project name '{pid}' (also in {reg.projects[pid].page})")
            continue
        status = str(meta.get("status") or "active")
        if status not in STATUSES:
            reg.warn(rel, f"unknown status '{status}' (use {', '.join(sorted(STATUSES))})")
        ports: list[int] = []
        for port in _str_list(meta.get("ports")):
            try:
                ports.append(int(port))
            except ValueError:
                reg.warn(rel, f"port '{port}' isn't a number")
        verified = meta.get("verified")
        if isinstance(verified, date):
            verified = verified.isoformat()
        docs_dir = str(meta.get("docs_dir") or "docs").strip("/")
        project = Project(
            id=pid,
            title=str(meta.get("title") or _title_of(body, pid)),
            page=rel,
            path=str(meta["path"]).replace("\\", "/").rstrip("/") if meta.get("path") else None,
            root=str(meta["root"]) if meta.get("root") else None,
            parent=str(meta["parent"]) if meta.get("parent") else None,
            group=str(meta["group"]) if meta.get("group") else None,
            status=status,
            kind=str(meta["kind"]) if meta.get("kind") else None,
            ports=ports,
            depends_on=_str_list(meta.get("depends_on")),
            docs_dir=docs_dir,
            verified=str(verified) if verified else None,
            summary=_summary_of(body),
        )
        if project.path:
            project.dir, problem = _resolve_project_dir(repo_root, roots, project.path, project.root)
            if problem:
                reg.warn(rel, f"path '{project.path}': {problem}")
            project.available = project.dir is not None
        if not re.match(r"^[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)*$", docs_dir) or ".." in docs_dir.split("/"):
            reg.warn(rel, f"docs_dir '{docs_dir}' must be a plain relative folder")
            project.docs_dir = "docs"
        reg.projects[pid] = project

    _link(reg)
    return reg


def _link(reg: Registry) -> None:
    """Check references and fill in children, used_by and group membership."""
    for p in reg.projects.values():
        if p.parent and p.parent not in reg.projects:
            reg.warn(p.page, f"parent '{p.parent}' isn't a registered project")
            p.parent = None
        if p.parent == p.id:
            reg.warn(p.page, "a project can't be its own parent")
            p.parent = None
        kept = []
        for dep in p.depends_on:
            if dep not in reg.projects:
                reg.warn(p.page, f"depends_on '{dep}' isn't a registered project")
            elif dep == p.id:
                reg.warn(p.page, "a project can't depend on itself")
            else:
                kept.append(dep)
        p.depends_on = kept

    # Parent cycles: walk up from each project; break the link that closes a loop.
    for p in reg.projects.values():
        seen = {p.id}
        cur = p
        while cur.parent:
            if cur.parent in seen:
                reg.warn(cur.page, f"parent '{cur.parent}' makes a cycle; ignored")
                cur.parent = None
                break
            seen.add(cur.parent)
            cur = reg.projects[cur.parent]

    for p in reg.projects.values():
        if p.parent:
            reg.projects[p.parent].children.append(p.id)
        for dep in p.depends_on:
            reg.projects[dep].used_by.append(p.id)
        group = effective_group(reg, p)
        if p.group and p.group not in reg.groups:
            reg.warn(p.page, f"group '{p.group}' has no page in {GROUPS_DIR}/")
            reg.groups[p.group] = Group(p.group, p.group, "", "")
        if group:
            reg.groups[group].projects.append(p.id)


def effective_group(reg: Registry, p: Project) -> str | None:
    """A sub-project without its own group belongs to its parent's group."""
    cur: Project | None = p
    while cur is not None:
        if cur.group:
            return cur.group
        cur = reg.projects.get(cur.parent) if cur.parent else None
    return None


# --- discovery --------------------------------------------------------------------------

MANIFESTS = ("pyproject.toml", "package.json", "Cargo.toml", "go.mod")
SKIP_DIRS = {"node_modules", "venv", ".venv", "dist", "build", "data", "docs", "tests", "src", "scripts"}


def _rel_from(repo_root: Path, target: Path) -> str:
    import os

    return Path(os.path.relpath(target, repo_root)).as_posix()


def discover(repo_root: Path, roots: Roots | Path, only_root: str | None = None) -> list[dict]:
    """Projects in each root (folders with a CLAUDE.md) and their sub-projects (a manifest
    two levels down, like collectors/<name>/pyproject.toml). Items found in the workspace
    have a path relative to this repo and no root; items in a named root have a path
    relative to that root. A folder in two roots is reported once, for the first root."""
    roots = _as_roots(roots)
    found: list[dict] = []
    seen: set[Path] = set()
    for name, folder in roots.all():
        if only_root and name != only_root:
            continue
        for item in _discover_in(repo_root.resolve(), folder, None if name == WORKSPACE else name):
            target = item.pop("dir")
            if target not in seen:
                seen.add(target)
                found.append(item)
    return found


def _discover_in(repo_root: Path, base: Path, root: str | None) -> list[dict]:
    found: list[dict] = []
    if not base.is_dir():
        return found

    def entry(d: Path, parent: str | None) -> dict:
        path = _rel_from(base, d) if root else _rel_from(repo_root, d)
        return {"name": d.name.lower(), "path": path, "root": root, "parent": parent, "dir": d.resolve()}

    for d in sorted(base.iterdir()):
        if not d.is_dir() or d.name.startswith((".", "_")) or d.resolve().is_relative_to(repo_root):
            continue
        if not (d / "CLAUDE.md").is_file():
            continue
        found.append(entry(d, None))
        for container in sorted(d.iterdir()):
            if not container.is_dir() or container.name.startswith((".", "_")) or container.name in SKIP_DIRS:
                continue
            for sub in sorted(container.iterdir()):
                if not sub.is_dir() or sub.name.startswith((".", "_")):
                    continue
                if any((sub / m).is_file() for m in MANIFESTS):
                    found.append(entry(sub, d.name.lower()))
    return found


def unregistered(
    reg: Registry, repo_root: Path, roots: Roots | Path, only_root: str | None = None
) -> list[dict]:
    """Discovered folders that no registry page points at."""
    roots = _as_roots(roots)
    known_dirs = {p.dir for p in reg.projects.values() if p.dir is not None}
    out = []
    for item in discover(repo_root, roots, only_root):
        base = roots.get(item["root"]) if item["root"] else repo_root
        target = (base / item["path"]).resolve()  # type: ignore[operator]
        if target in known_dirs:
            continue
        name = item["name"]
        if name in reg.projects:
            name = f"{item['parent']}-{name}" if item["parent"] else name
        out.append({**item, "name": name})
    return out


def stub_page(item: dict, today: str) -> str:
    lines = ["---", f"name: {item['name']}"]
    if item.get("root"):
        lines.append(f"root: {item['root']}")
    lines.append(f"path: {item['path']}")
    if item.get("parent"):
        lines.append(f"parent: {item['parent']}")
    lines += ["status: active", f"verified: {today}", "---", "", f"# {item['name']}", ""]
    lines += [
        "_Cross-project notes: what this project owns, exposes and depends on, seen from the whole "
        "system. Its own README, CLAUDE.md and docs are shown live in the viewer, so don't copy "
        "them here._",
        "",
        "## Owns",
        "- TODO",
        "",
        "## Exposes",
        "- TODO",
        "",
        "## Depends on",
        "- TODO (also list them in `depends_on` above, so the maps show them)",
        "",
    ]
    return "\n".join(lines)
