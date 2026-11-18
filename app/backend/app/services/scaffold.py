"""Create a new project or group in a granted root, from the viewer (ADR 0028).

The one place the backend writes outside the registry, and only ever to make something new:
a folder that doesn't exist yet in a root the user granted, a README.md and a CLAUDE.md in it,
optionally a git repository, and the registry page that registers it. Nothing is overwritten,
nothing existing in a project is edited, and if a step fails the folder this call made is
removed again.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from . import git
from .registry import (
    ID_RE,
    PROJECTS_DIR,
    RESERVED_IDS,
    STATUSES,
    RegisterError,
    Registry,
    _rel_from,
)
from .roots import WORKSPACE, Roots

KINDS = ("project", "group")
MAX_TITLE = 100
MAX_DESCRIPTION = 2000
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _clean(text: str | None, limit: int, what: str) -> str:
    out = _CONTROL.sub("", (text or "").replace("\r\n", "\n")).strip()
    if len(out) > limit:
        raise RegisterError(f"{what} is longer than {limit} characters")
    return out


def _readme(title: str, description: str) -> str:
    return f"# {title}\n\n{description}\n" if description else f"# {title}\n"


def _claude_md(title: str, description: str, kind: str, status: str) -> str:
    lines = [f"# {title}", ""]
    if description:
        lines += [description, ""]
    lines += [
        "## Status",
        f"{status.capitalize()}. Created from Archeion as a new {kind}.",
        "",
        "## Notes for Claude",
        "- Read this file and README.md first.",
        "- Put the project's own rules, commands and gotchas here as they're learned.",
        "",
    ]
    return "\n".join(lines)


def _page(item: dict) -> str:
    lines = ["---", f"name: {item['name']}"]
    if item["title"] != item["name"]:
        lines.append(f"title: {json.dumps(item['title'], ensure_ascii=False)}")
    if item.get("root"):
        lines.append(f"root: {item['root']}")
    lines.append(f"path: {item['path']}")
    if item.get("parent"):
        lines.append(f"parent: {item['parent']}")
    if item.get("group"):
        lines.append(f"group: {item['group']}")
    if item.get("type"):
        lines.append(f"type: {item['type']}")
    lines.append(f"status: {item['status']}")
    if item.get("inbox_edits"):
        lines.append("inbox_edits: true")
    lines += [
        "# verified: YYYY-MM-DD   (add it once this page is checked against the project)",
        "---",
        "",
        f"# {item['title']}",
        "",
    ]
    if item["description"]:
        lines += [item["description"], ""]
    lines += ["## Owns", "- TODO", "", "## Exposes", "- TODO", "", "## Depends on", "- TODO", ""]
    return "\n".join(lines)


def plan_create(
    reg: Registry,
    roots: Roots,
    repo_root: Path,
    *,
    root: str | None,
    name: str,
    kind: str = "project",
    title: str | None = None,
    description: str | None = None,
    status: str = "planned",
    group: str | None = None,
    inside_group: bool = False,
    git_init: bool = True,
) -> dict:
    """Check everything and say what would be created. Writes nothing."""
    if kind not in KINDS:
        raise RegisterError("kind must be project or group")
    if not ID_RE.match(name):
        raise RegisterError(f"'{name}' isn't a valid name (lowercase letters, digits, . _ -)")
    if name in RESERVED_IDS:
        raise RegisterError(f"'{name}' is reserved for Archeion's own sources")
    if name in reg.projects or name in reg.groups:
        raise RegisterError(f"'{name}' is already a project or group")
    if status not in STATUSES:
        raise RegisterError(f"status must be one of {', '.join(sorted(STATUSES))}")
    title = _clean(title, MAX_TITLE, "the title") or name
    if "\n" in title:
        raise RegisterError("the title must be one line")
    description = _clean(description, MAX_DESCRIPTION, "the description")
    if kind == "group" and group:
        raise RegisterError("a group can't be a member of a group (groups don't nest)")

    host = None
    if group:
        if group not in reg.groups:
            raise RegisterError(f"no group named '{group}'")
        host = reg.projects.get(reg.groups[group].home) if reg.groups[group].home else None
    if inside_group:
        if host is None or host.dir is None:
            raise RegisterError("only a group with a folder on this machine can hold it inside")
        base, key = host.dir, host.root
        path_prefix = (host.path or "").rstrip("/")
    else:
        key = None if root in (None, "", WORKSPACE) else root
        folder = roots.get(key or WORKSPACE)
        if folder is None:
            raise RegisterError(f"no root named '{key or WORKSPACE}' is granted")
        base, path_prefix = folder, ""
    if not base.is_dir():
        raise RegisterError("that root's folder doesn't exist")
    target = base / name
    if target.exists():
        raise RegisterError(
            f"'{name}' already exists in that folder; Archeion never writes into an existing one"
        )
    page = Path(PROJECTS_DIR) / f"{name}.md"

    if inside_group:
        path = f"{path_prefix}/{name}" if path_prefix else name
        page_root = key
    elif key is None:
        path, page_root = _rel_from(repo_root, target), None
    else:
        path, page_root = name, key
    module = inside_group and not git_init
    item = {
        "name": name,
        "title": title,
        "description": description,
        "root": page_root,
        "path": path,
        "parent": host.id if inside_group and host else None,
        "group": group if group and not inside_group else None,
        "type": "group" if kind == "group" else None,
        "status": status,
        "inbox_edits": not module,
    }
    files = ["README.md", "CLAUDE.md"]
    return {
        "name": name,
        "kind": "module" if module else kind,
        "title": title,
        "location": f"{page_root}:{path}" if page_root else path,
        "files": files,
        "git": git_init,
        "page": page.as_posix(),
        "group": group,
        "inside_group": inside_group,
        "_target": target,
        "_item": item,
    }


def public(plan: dict) -> dict:
    return {k: v for k, v in plan.items() if not k.startswith("_")}


def create(registry_root: Path, reg: Registry, roots: Roots, repo_root: Path, **fields) -> dict:
    """Create the folder, its files, an optional repository and the registry page. If any step
    fails, what this call made is removed and the error is raised."""
    plan = plan_create(reg, roots, repo_root, **fields)
    target: Path = plan["_target"]
    item = plan["_item"]
    page = registry_root / PROJECTS_DIR / f"{item['name']}.md"
    if page.exists():
        raise RegisterError(f"{PROJECTS_DIR}/{item['name']}.md already exists in the registry")
    page.parent.mkdir(parents=True, exist_ok=True)
    kind = "group" if item["type"] == "group" else "project"
    created = made_page = False
    try:
        target.mkdir()  # never exist_ok: it must be new
        created = True
        for filename, text in (
            ("README.md", _readme(item["title"], item["description"])),
            ("CLAUDE.md", _claude_md(item["title"], item["description"], kind, item["status"])),
        ):
            with (target / filename).open("x", encoding="utf-8", newline="\n") as f:
                f.write(text)
        if plan["git"]:
            git.init(target)
        with page.open("x", encoding="utf-8", newline="\n") as f:
            f.write(_page(item))
        made_page = True
    except Exception as exc:
        if created:  # only a folder this call made
            shutil.rmtree(target, ignore_errors=True)
        if made_page:
            page.unlink(missing_ok=True)
        if isinstance(exc, git.GitError):
            raise RegisterError(f"git init failed: {exc}") from exc
        raise
    return public(plan)
