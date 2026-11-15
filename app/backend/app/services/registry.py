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
    parent: example-service                       # the project (or module) it sits in
    type: module                                  # optional: project | module (ADR 0016)
    group: example-system                         # a groups/<group>.md page
    status: active                                # active | paused | archived | planned
    inbox_edits: true                             # optional: /inbox may edit its files (ADR 0017)
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
TYPES = ("project", "module")  # ADR 0016: a project has its own repository, a module lives in one
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
    # ADR 0016. `type` is what counts: the page's `type:` if set, else `detected_type`.
    type: str = "project"
    type_source: str = "detected"  # "page" | "detected"
    detected_type: str = "project"
    owner: str | None = None  # a module's project (nearest ancestor that's a project)
    # ADR 0017: whether Archeion's /inbox may edit this project's files for its inbox items.
    # From the page's `inbox_edits:`, else a module follows its project, else allowed.
    inbox_edits: bool = True
    inbox_edits_source: str = "default"  # "page" | "owner" | "default"
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
    return roots if isinstance(roots, Roots) else Roots(workspace=roots.resolve())  # tests, old callers


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
        if bound is None:
            return None, (
                "no workspace folder is granted, so a page without root: can't be found; "
                "add the folder as a root on the Settings page and set root: <name>"
            )
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
        edits = meta.get("inbox_edits")
        if edits is not None and not isinstance(edits, bool):
            reg.warn(rel, f"inbox_edits '{edits}' must be true or false; ignored")
            edits = None
        page_type = meta.get("type")
        if page_type is not None and page_type not in TYPES:
            reg.warn(rel, f"unknown type '{page_type}' (use project or module); detected instead")
            page_type = None
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
        if page_type:
            project.type, project.type_source = str(page_type), "page"
        if edits is not None:
            project.inbox_edits, project.inbox_edits_source = edits, "page"
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

    _types(reg)
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


def is_repo(folder: Path | None) -> bool:
    """The folder is the root of its own git repository (`.git` is a folder, or a file
    for a submodule or a worktree)."""
    return folder is not None and (folder / ".git").exists()


def _types(reg: Registry) -> None:
    """Project or module (ADR 0016). Detected: a page inside another (`parent:`) whose folder
    isn't a repository of its own is a module; anything else is a project. A folder this
    machine can't see counts as no repository. The page's `type:` overrides detection."""
    for p in reg.projects.values():
        p.detected_type = "module" if p.parent and not is_repo(p.dir) else "project"
        if p.type_source != "page":
            p.type = p.detected_type
    for p in reg.projects.values():
        if p.type == "project":
            continue
        if not p.parent:
            reg.warn(p.page, "a module needs `parent:`, the project it's part of")
            continue
        p.owner = owning_project(reg, p).id
    # A module lives in its project's repository, so it follows the project unless its page says.
    for p in reg.projects.values():
        if p.inbox_edits_source != "page" and p.owner and p.owner != p.id:
            p.inbox_edits, p.inbox_edits_source = reg.projects[p.owner].inbox_edits, "owner"


def owning_project(reg: Registry, p: Project) -> Project:
    """The project a module is part of: its nearest ancestor that's a project. A project
    owns itself. A chain of modules with no project above ends at the topmost page."""
    cur = p
    while cur.type != "project" and cur.parent and cur.parent in reg.projects:
        cur = reg.projects[cur.parent]
    return cur


def modules_of(reg: Registry, p: Project) -> list[str]:
    """The modules a project owns, at any depth (not nested projects or their modules)."""
    return sorted(m.id for m in reg.projects.values() if m.type == "module" and m.owner == p.id)


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
    found = _discover_all(repo_root, _as_roots(roots), only_root)
    for item in found:
        item.pop("dir")
    return found


def _discover_all(repo_root: Path, roots: Roots, only_root: str | None = None) -> list[dict]:
    """discover(), with each item's resolved folder kept in `dir`."""
    found: list[dict] = []
    seen: set[Path] = set()
    for name, folder in roots.all():
        if only_root and name != only_root:
            continue
        for item in _discover_in(repo_root.resolve(), folder, None if name == WORKSPACE else name):
            if item["dir"] not in seen:
                seen.add(item["dir"])
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
        inside = reg.project_for_dir(target.parent) if item["parent"] else None
        detected = "module" if inside and not is_repo(target) else "project"
        out.append({**item, "name": name, "detected_type": detected})
    return out


def stub_page(item: dict) -> str:
    """A new page for a discovered folder. `verified` is left out: nobody has checked the
    page against the project yet (ADR 0010)."""
    lines = ["---", f"name: {item['name']}"]
    if item.get("root"):
        lines.append(f"root: {item['root']}")
    lines.append(f"path: {item['path']}")
    if item.get("parent"):
        lines.append(f"parent: {item['parent']}")
    if item.get("type"):
        lines.append(f"type: {item['type']}")
    lines.append("status: active")
    if item.get("inbox_edits") is not None:
        lines.append(f"inbox_edits: {'true' if item['inbox_edits'] else 'false'}")
    lines += [
        "# verified: YYYY-MM-DD   (add it once this page is checked against the project)",
        "---",
        "",
        f"# {item['name']}",
        "",
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


# --- managing from the viewer (ADR 0010) ------------------------------------------------


class RegisterError(ValueError):
    """A registration the viewer asked for that can't be done; the message says why."""


def _shown(base: Path, target: Path) -> str:
    try:
        return target.relative_to(base).as_posix()
    except ValueError:
        return target.as_posix()


def _entry(p: Project, root: str | None, folder: str) -> dict:
    return {
        "name": p.id,
        "path": p.path,
        "root": root,
        "folder": folder,
        "parent_folder": None,
        "parent": p.parent,
        "registered": p.id,
        "detected_type": p.type,
    }


def survey(reg: Registry, repo_root: Path, roots: Roots | Path) -> list[dict]:
    """For each root, the projects in it: every folder discovery finds, and every registered
    project that lives there, with the project it's registered as (or None). Roots that
    registry pages name but this machine doesn't grant come last, with `granted` False."""
    roots = _as_roots(roots)
    by_dir = {p.dir: p for p in reg.projects.values() if p.dir is not None}
    found = _discover_all(repo_root, roots)
    out: list[dict] = []
    for name, folder in roots.all():
        key = None if name == WORKSPACE else name
        items: list[dict] = []
        listed: set[Path] = set()
        for item in found:
            if item["root"] != key:
                continue
            target = item["dir"]
            listed.add(target)
            project = by_dir.get(target)
            if project is not None:
                items.append(_entry(project, key, _shown(folder, target)))
                continue
            parent = reg.project_for_dir(target.parent) if item["parent"] else None
            suggested = item["name"]
            if suggested in reg.projects and item["parent"]:
                suggested = f"{item['parent']}-{suggested}"
            items.append(
                {
                    "name": suggested,
                    "path": item["path"],
                    "root": key,
                    "folder": _shown(folder, target),
                    "parent_folder": item["parent"],
                    "parent": parent.id if parent else None,
                    "registered": None,
                    # What it would be detected as once registered (ADR 0016).
                    "detected_type": "module" if parent and not is_repo(target) else "project",
                }
            )
        # Registered projects that discovery doesn't find (no CLAUDE.md, or nested deeper).
        for p in reg.projects.values():
            if p.dir is None or p.dir in listed or (p.root or WORKSPACE) != name:
                continue
            items.append(_entry(p, key, _shown(folder, p.dir)))
        items.sort(key=lambda i: i["folder"])
        out.append({"name": name, "folder": str(folder), "granted": True, "items": items})
    missing = sorted({p.root for p in reg.projects.values() if p.root and roots.get(p.root) is None})
    for name in missing:
        items = [_entry(p, name, p.path or "") for p in reg.projects.values() if p.root == name]
        out.append({"name": name, "folder": None, "granted": False, "items": items})
    return out


def register(
    registry_root: Path,
    reg: Registry,
    repo_root: Path,
    roots: Roots | Path,
    *,
    root: str | None,
    path: str,
    name: str,
    type: str | None = None,
) -> str:
    """Create the registry page for a folder that discovery found and nothing registers yet.
    Only such folders can be registered, so a page can't point anywhere else. Never
    overwrites a page. Returns the page's path inside the registry."""
    roots = _as_roots(roots)
    key = None if root in (None, "", WORKSPACE) else root
    if key is not None and roots.get(key) is None:
        raise RegisterError(f"no root named '{key}' is configured")
    if not ID_RE.match(name):
        raise RegisterError(f"'{name}' isn't a valid project name (lowercase letters, digits, . _ -)")
    if name in RESERVED_IDS:
        raise RegisterError(f"'{name}' is reserved for Archeion's own sources")
    if name in reg.projects:
        raise RegisterError(f"a project named '{name}' is already registered")
    if type is not None and type not in TYPES:
        raise RegisterError(f"type must be project or module, not '{type}'")
    candidates = _discover_all(repo_root, roots, key or WORKSPACE)
    item = next((i for i in candidates if i["root"] == key and i["path"] == path), None)
    if item is None:
        raise RegisterError("that folder isn't a project Archeion found in its roots")
    known = {p.dir: p.id for p in reg.projects.values() if p.dir is not None}
    if item["dir"] in known:
        raise RegisterError(f"that folder is already registered as '{known[item['dir']]}'")
    parent = reg.project_for_dir(item["dir"].parent) if item["parent"] else None
    page = registry_root / PROJECTS_DIR / f"{name}.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    if type == "module" and parent is None:
        raise RegisterError("only a folder inside a registered project can be a module")
    final = type or ("module" if parent and not is_repo(item["dir"]) else "project")
    text = stub_page(
        {
            "name": name,
            "root": key,
            "path": path,
            "parent": parent.id if parent else None,
            "type": type,
            # ADR 0017: written out, so the page shows it. A module follows its project.
            "inbox_edits": True if final == "project" else None,
        }
    )
    try:
        with page.open("x", encoding="utf-8", newline="\n") as f:
            f.write(text)
    except FileExistsError:
        raise RegisterError(f"{PROJECTS_DIR}/{name}.md already exists in the registry") from None
    return page.relative_to(registry_root).as_posix()


# --- single frontmatter lines of an existing page (ADR 0016, ADR 0017) ---------------------


def set_type(registry_root: Path, reg: Registry, project_id: str, value: str | None) -> str:
    """Set (`project` / `module`) or remove (None: back to detection) the `type:` line of a
    project's registry page (ADR 0016). Returns the page's path."""
    if value is not None and value not in TYPES:
        raise RegisterError(f"type must be project or module, not '{value}'")
    project = reg.projects.get(project_id)
    if project is None:
        raise KeyError(project_id)
    if value == "module" and not project.parent:
        raise RegisterError(f"'{project_id}' has no `parent:`, so it can't be a module of a project")
    return _set_line(registry_root, project, "type", value, ("parent", "path"))


def set_inbox_edits(registry_root: Path, reg: Registry, project_id: str, value: bool | None) -> str:
    """Set (True / False) or remove (None: the default, or its project's setting for a module)
    the `inbox_edits:` line of a project's registry page (ADR 0017). Returns the page's path."""
    project = reg.projects.get(project_id)
    if project is None:
        raise KeyError(project_id)
    shown = None if value is None else ("true" if value else "false")
    return _set_line(registry_root, project, "inbox_edits", shown, ("path", "parent", "type", "status"))


def _set_line(
    registry_root: Path, project: Project, key: str, value: str | None, after: tuple[str, ...]
) -> str:
    """Set (or, with None, remove) one `key:` line in the frontmatter of a project's registry
    page. Every other byte of the page stays as it was. A new line goes after the last line
    whose key is in `after`, so the page still reads in the documented order."""
    base = (registry_root / PROJECTS_DIR).resolve()
    page = (registry_root / project.page).resolve()
    if page.parent != base or not page.is_file():
        raise RegisterError(f"'{project.id}' has no page in {PROJECTS_DIR}/")
    raw = page.read_bytes().decode("utf-8")
    bom = "﻿" if raw.startswith("﻿") else ""
    text = raw[len(bom) :]
    m = FRONTMATTER_RE.match(text)
    if not m:
        raise RegisterError(f"{project.page} has no frontmatter to change")
    nl = "\r\n" if "\r\n" in m.group(0) else "\n"
    line_re = re.compile(rf"^{re.escape(key)}\s*:")
    after_re = re.compile(rf"^({'|'.join(map(re.escape, after))})\s*:")
    kept = [line for line in m.group(1).split(nl) if not line_re.match(line)]
    if value is not None:
        at = len(kept)
        for i, line in enumerate(kept):
            if after_re.match(line):
                at = i + 1
        kept.insert(at, f"{key}: {value}")
    head = f"---{nl}{nl.join(kept)}{nl}---{nl}"
    rest = text[m.end() :]
    if not m.group(0).endswith("\n"):  # frontmatter closed at the very end of the file
        head = head[: -len(nl)]
    new = bom + head + rest
    if new != raw:
        tmp = page.with_name(f".{page.name}.tmp")
        tmp.write_bytes(new.encode("utf-8"))
        tmp.replace(page)
    return project.page
