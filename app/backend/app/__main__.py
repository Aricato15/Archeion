"""Command line: python -m app <serve | password ... | inbox ...> (run from app/backend/).

The inbox commands are how an interactive Claude Code session (/inbox) reads and answers
feedback. They work on the backend's own database on this machine, so no API token exists.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from datetime import date
from pathlib import Path

from .config import Settings, read_version
from .db import Database
from .paths import DocNotFound, DocPathError
from .security import MIN_PW_LEN, clear_sessions, pw_is_set, set_pw
from .services import docs_fs
from .services import feedback as fb
from .services.registry import REGISTRY_ID, SELF_ID, Project, effective_group, split_frontmatter, stub_page
from .services.sources import SourceManager, SourceNotFound

EXIT_NO_PASSWORD = 3


def _db(settings: Settings) -> Database:
    db = Database(settings.db_file)
    db.init()
    return db


# --- serve ------------------------------------------------------------------------------


def cmd_serve(settings: Settings, _: argparse.Namespace) -> int:
    import uvicorn

    from .main import create_app

    app = create_app(settings)
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        timeout_graceful_shutdown=2,
        log_level="info",
        server_header=False,
    )
    return 0


# --- password ---------------------------------------------------------------------------


def cmd_password_set(settings: Settings, _: argparse.Namespace) -> int:
    first = getpass.getpass(f"New admin password (at least {MIN_PW_LEN} characters): ")
    if len(first) < MIN_PW_LEN:
        print(f"Too short: use at least {MIN_PW_LEN} characters.", file=sys.stderr)
        return 1
    second = getpass.getpass("Repeat it: ")
    if first != second:
        print("The two entries don't match. Nothing was changed.", file=sys.stderr)
        return 1
    with _db(settings).conn() as conn:
        set_pw(conn, first)
    print("Admin password saved (only a salted scrypt hash is stored). All sessions were logged out.")
    return 0


def cmd_password_status(settings: Settings, _: argparse.Namespace) -> int:
    with _db(settings).conn() as conn:
        if pw_is_set(conn):
            print("An admin password is set.")
            return 0
    print("No admin password is set. Run set_admin_password.bat.")
    return EXIT_NO_PASSWORD


def cmd_clear_sessions(settings: Settings, _: argparse.Namespace) -> int:
    with _db(settings).conn() as conn:
        n = clear_sessions(conn)
    print(f"Logged out {n} session(s).")
    return 0


# --- inbox ------------------------------------------------------------------------------


def _print_json(data: object) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _sources(settings: Settings) -> SourceManager:
    return SourceManager(
        settings.docs_root,
        settings.registry_root,
        settings.repo_root,
        settings.workspace_dir,
        settings.project_roots,
    )


# Archeion's own session handles both of its sources: docs/ and the private registry.
OWN_SOURCES = [SELF_ID, REGISTRY_ID]


def _target(settings: Settings, args: argparse.Namespace) -> list[str] | None:
    """The sources to filter on: --project X, --here (the caller's folder), or None for all."""
    if getattr(args, "project", None):
        project = args.project
        if project in OWN_SOURCES:
            return OWN_SOURCES
        if project not in _sources(settings).registry.projects:
            raise ValueError(f"'{project}' isn't a registered project (see: projects list)")
        return [project]
    if getattr(args, "here", False):
        here = _caller_dir()
        if here.is_relative_to(settings.repo_root.resolve()):
            return OWN_SOURCES
        project = _sources(settings).registry.project_for_dir(here)
        if project is None:
            raise ValueError(_not_registered(here))
        return [project.id]
    return None


def _caller_dir() -> Path:
    # The wrapper scripts cd into app/backend; they pass the caller's folder along.
    return Path(os.environ.get("ARCHEION_CALLER_DIR") or os.getcwd()).resolve()


def _not_registered(here: Path) -> str:
    return f"{here.name} isn't inside a registered project; register it first (projects scan)"


def _project_arg(settings: Settings, manager: SourceManager, args: argparse.Namespace) -> Project:
    """The project named by --project, or the one the caller's folder is in (--here)."""
    reg = manager.registry
    if getattr(args, "project", None):
        if args.project not in reg.projects:
            raise ValueError(f"'{args.project}' isn't a registered project (see: projects list)")
        return reg.projects[args.project]
    here = _caller_dir()
    if here.is_relative_to(settings.repo_root.resolve()):
        raise ValueError("this is Archeion itself, not a registered project; use --project <name>")
    project = reg.project_for_dir(here)
    if project is None:
        raise ValueError(_not_registered(here))
    return project


def _summary_line(item: dict) -> str:
    where = item["doc_path"] or "(general)"
    if item.get("source", "archeion") != "archeion":
        where = f"[{item['source']}] {where}"
    anchor = item["anchor"] or {}
    if anchor.get("heading"):
        where += f" > {anchor['heading']}"
    if anchor.get("lines"):
        where += f" (lines {anchor['lines'][0]}-{anchor['lines'][1]})"
    first = item["body"].strip().splitlines()[0] if item["body"].strip() else ""
    if len(first) > 80:
        first = first[:77] + "..."
    parent = f" follow-up of #{item['parent_id']}" if item["parent_id"] else ""
    if item.get("origin"):
        parent += f" from {item['origin']}"
    return f"#{item['id']:<4} {item['status']:<11} {item['kind']:<7} {where}{parent}\n       {first}"


def cmd_inbox_list(settings: Settings, args: argparse.Namespace) -> int:
    status = None if args.status == "all" else args.status
    source = _target(settings, args)
    with _db(settings).conn() as conn:
        items = fb.list_items(conn, status=status, source=source)
        elsewhere = fb.open_by_source(conn)
    items.reverse()  # oldest first: the order to work in
    if args.json:
        _print_json(items)
    elif not items:
        label = "archeion" if source == OWN_SOURCES else (source[0] if source else None)
        print(f"No {args.status} feedback items" + (f" for {label}." if label else "."))
        if source:
            others = {k: v for k, v in elsewhere.items() if k not in source}
            if others:
                print("Waiting elsewhere: " + ", ".join(f"{k} ({v})" for k, v in sorted(others.items())))
    else:
        for item in items:
            print(_summary_line(item))
    return 0


def cmd_inbox_count(settings: Settings, args: argparse.Namespace) -> int:
    with _db(settings).conn() as conn:
        print(fb.summary(conn, _target(settings, args))["open"])
    return 0


def _doc_excerpt(settings: Settings, item: dict) -> str:
    if not item["doc_path"]:
        return ""
    try:
        source = _sources(settings).get(item.get("source") or "archeion")
        target = source.resolve(item["doc_path"], allowed={".md"})
    except SourceNotFound:
        return f"(the project '{item.get('source')}' is no longer registered)"
    except (DocPathError, DocNotFound):
        return "(the doc no longer exists)"
    anchor = item["anchor"] or {}
    lines = tuple(anchor["lines"]) if anchor.get("lines") else None
    return docs_fs.excerpt(docs_fs.read_text(target), lines=lines, heading=anchor.get("heading"))


def cmd_inbox_show(settings: Settings, args: argparse.Namespace) -> int:
    with _db(settings).conn() as conn:
        item = fb.get(conn, args.id)
        thread = fb.thread(conn, args.id)
    excerpt = _doc_excerpt(settings, item)
    if args.json:
        _print_json({"item": item, "thread": thread, "excerpt": excerpt})
        return 0
    print(_summary_line(item))
    print(f"       created {item['created_at']}, doc at commit {(item['doc_rev'] or '-')[:10]}")
    if len(thread) > 1:
        print("\nThread:")
        for t in thread:
            mark = "->" if t["id"] == item["id"] else "  "
            print(f" {mark} #{t['id']} [{t['status']}] {t['body'].strip()[:200]}")
            if t["reply"]:
                print(f"      reply: {t['reply'].strip()[:200]}")
    anchor = item["anchor"] or {}
    if anchor.get("quote"):
        print("\nQuoted text:")
        for line in anchor["quote"].splitlines():
            print(f"  > {line}")
    if excerpt:
        if item.get("source", "archeion") == "archeion":
            where = f"docs/{item['doc_path']}"
        else:
            where = f"{item['doc_path']} in {item['source']}"
        print(f"\nDoc excerpt ({where}):")
        print(excerpt)
    print("\nRequest:")
    print(item["body"])
    if item["reply"]:
        print("\nCurrent reply:")
        print(item["reply"])
    return 0


def cmd_inbox_claim(settings: Settings, args: argparse.Namespace) -> int:
    with _db(settings).conn() as conn:
        item = fb.claim(conn, args.id)
    print(f"Claimed #{item['id']}.")
    return 0


def cmd_inbox_release(settings: Settings, args: argparse.Namespace) -> int:
    with _db(settings).conn() as conn:
        item = fb.release(conn, args.id)
    print(f"Released #{item['id']}; it's open again.")
    return 0


def _read_text_arg(value: str) -> str:
    if value == "-":
        return sys.stdin.buffer.read().decode("utf-8")
    return Path(value).read_text(encoding="utf-8")


def cmd_inbox_create(settings: Settings, args: argparse.Namespace) -> int:
    """A new item, written from a session rather than the viewer (/archeion:report). It
    records which registered project the caller is in as its origin (ADR 0009)."""
    manager = _sources(settings)
    to = args.to
    if to == REGISTRY_ID:
        to = SELF_ID
    if to != SELF_ID and to not in manager.registry.projects:
        raise ValueError(f"'{to}' isn't a registered project (see: projects list)")
    here = _caller_dir()
    origin = None
    if not here.is_relative_to(settings.repo_root.resolve()):
        found = manager.registry.project_for_dir(here)
        origin = found.id if found else None
    body = _read_text_arg(args.file).strip()
    if not body:
        raise ValueError("the item is empty")
    with _db(settings).conn() as conn:
        item = fb.create(conn, kind=args.kind, body=body, source=to, origin=origin)
    sender = f" from {origin}" if origin else ""
    print(f"Created #{item['id']} ({item['kind']}) for {to}{sender}. It shows up in the viewer.")
    return 0


def cmd_inbox_reply(settings: Settings, args: argparse.Namespace) -> int:
    if args.file == "-":
        text = sys.stdin.buffer.read().decode("utf-8")
    else:
        text = Path(args.file).read_text(encoding="utf-8")
    with _db(settings).conn() as conn:
        item = fb.reply(conn, args.id, text.strip())
    print(f"Replied to #{item['id']}; it's now answered.")
    return 0


# --- projects ---------------------------------------------------------------------------


def cmd_projects_list(settings: Settings, args: argparse.Namespace) -> int:
    manager = _sources(settings)
    reg = manager.registry
    if args.json:
        _print_json({**reg.public(), "unregistered": manager.unregistered()})
        return 0
    if not reg.projects:
        print("No projects registered yet. Run: projects scan")

    def show(pid: str, depth: int) -> None:
        p = reg.projects[pid]
        flags = [p.status] + ([f"root {p.root}"] if p.root else [])
        flags += [] if p.available or not p.path else ["not available"]
        extra = f" -> {', '.join(p.depends_on)}" if p.depends_on else ""
        print(f"{'  ' * depth}- {p.id} ({', '.join(flags)}){extra}")
        for child in sorted(p.children):
            show(child, depth + 1)

    roots = [p for p in reg.projects.values() if not p.parent]
    for gid, group in sorted(reg.groups.items()):
        print(f"{group.title} [{gid}]")
        for p in sorted(roots, key=lambda x: x.id):
            if p.group == gid:
                show(p.id, 1)
    loose = [p for p in roots if not p.group]
    if loose:
        print("Standalone")
        for p in sorted(loose, key=lambda x: x.id):
            show(p.id, 1)
    for w in reg.warnings:
        where = f"registry/{w['page']}" if w["page"] else "settings"
        print(f"warning: {where}: {w['message']}", file=sys.stderr)
    missing = manager.unregistered()
    if missing:
        print(f"\n{len(missing)} folder(s) in your roots aren't registered. Run: projects scan")
    return 0


def cmd_projects_scan(settings: Settings, args: argparse.Namespace) -> int:
    """Show (or, with --write, create) stub registry pages for unregistered folders.
    Existing pages are never touched."""
    manager = _sources(settings)
    if args.root and manager.roots.get(args.root) is None:
        known = ", ".join(name for name, _ in manager.roots.all())
        raise ValueError(f"no root named '{args.root}' (configured: {known}; see ARCHEION_ROOTS)")
    missing = manager.unregistered(args.root)
    if args.only:
        wanted = {n.lower() for n in args.only}
        unknown = wanted - {item["name"] for item in missing}
        if unknown:
            raise ValueError(
                f"not an unregistered folder: {', '.join(sorted(unknown))} (projects scan lists them)"
            )
        missing = [item for item in missing if item["name"] in wanted]
    if not missing:
        where = f"the root '{args.root}'" if args.root else "your roots"
        print(f"Every project in {where} is registered.")
        return 0
    target_dir = settings.registry_root / "projects"
    today = date.today().isoformat()
    for item in missing:
        page = target_dir / f"{item['name']}.md"
        rel = page.relative_to(settings.repo_root).as_posix()
        parent = f", sub-project of {item['parent']}" if item["parent"] else ""
        where = f"{item['root']}:{item['path']}" if item["root"] else item["path"]
        label = f"{item['name']} ({where}{parent})"
        if page.exists():
            print(f"skip   {label}: {rel} already exists")
            continue
        if args.write:
            target_dir.mkdir(parents=True, exist_ok=True)
            page.write_text(stub_page(item, today), encoding="utf-8")
            print(f"create {label}: {rel}")
        else:
            print(f"would create {label}: {rel}")
    if not args.write:
        print(
            "\nNothing written. Run again with --write to create these pages (add --only <name>"
            " to pick some), then fill in group and depends_on."
        )
    return 0


def _project_facts(manager: SourceManager, p: Project) -> dict:
    """A project's place in the system, for a session working in it (/archeion:context)."""
    reg = manager.registry
    group_id = effective_group(reg, p)
    group = reg.groups.get(group_id) if group_id else None
    notes = ""
    page = manager.registry_root / p.page
    if page.is_file():
        notes = split_frontmatter(page.read_text(encoding="utf-8", errors="replace"))[1].strip()
    return {
        **p.public(),
        "group": group_id,
        "group_title": group.title if group else None,
        "group_inherited": bool(group_id and not p.group),
        "group_members": sorted(group.projects) if group else [],
        "notes": notes,
    }


def cmd_projects_show(settings: Settings, args: argparse.Namespace) -> int:
    manager = _sources(settings)
    facts = _project_facts(manager, _project_arg(settings, manager, args))
    if args.json:
        _print_json(facts)
        return 0

    def names(ids: list[str]) -> str:
        return ", ".join(ids) if ids else "none"

    where = f"{facts['root']}:{facts['path']}" if facts["root"] else (facts["path"] or "none")
    print(f"{facts['id']} ({facts['title']})")
    print(f"  status: {facts['status']}" + (f", kind: {facts['kind']}" if facts["kind"] else ""))
    print(f"  path: {where}" + ("" if facts["available"] else " (not available on this machine)"))
    if facts["group"]:
        inherited = " (from its parent)" if facts["group_inherited"] else ""
        print(f"  group: {facts['group']} ({facts['group_title']}){inherited}")
        others = [m for m in facts["group_members"] if m != facts["id"]]
        print(f"    with: {names(others)}")
    else:
        print("  group: none (standalone)")
    if facts["parent"]:
        print(f"  part of: {facts['parent']}")
    if facts["children"]:
        print(f"  sub-projects: {names(sorted(facts['children']))}")
    print(f"  depends on: {names(facts['depends_on'])}")
    print(f"  used by: {names(sorted(facts['used_by']))}")
    print(f"  ports: {', '.join(str(n) for n in facts['ports']) or 'none'}")
    print(f"  verified: {facts['verified'] or 'never'}")
    print(f"  registry page: registry/{facts['page']}")
    if facts["notes"]:
        print("\nNotes from the registry page:")
        print(facts["notes"])
    return 0


def cmd_projects_ports(settings: Settings, args: argparse.Namespace) -> int:
    """Every port the registry records, so a new one can be picked without a clash."""
    reg = _sources(settings).registry
    by_port: dict[int, list[str]] = {}
    for p in reg.projects.values():
        for port in p.ports:
            by_port.setdefault(port, []).append(p.id)
    rows = [{"port": port, "projects": sorted(ids)} for port, ids in sorted(by_port.items())]
    clashes = [r for r in rows if len(r["projects"]) > 1]
    if args.json:
        _print_json({"ports": rows, "clashes": clashes})
        return 0
    if not rows:
        print("No ports are recorded in the registry.")
        return 0
    for r in rows:
        mark = "  <- used twice" if len(r["projects"]) > 1 else ""
        print(f"{r['port']:>6}  {', '.join(r['projects'])}{mark}")
    if clashes:
        print(f"\n{len(clashes)} port(s) are recorded for more than one project.")
    return 0


def cmd_version(settings: Settings, _: argparse.Namespace) -> int:
    print(read_version(settings.repo_root))
    return 0


# --- parser -----------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app", description="Archeion backend")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("serve", help="run the API server").set_defaults(func=cmd_serve)

    pw = sub.add_parser("password", help="manage the admin password").add_subparsers(
        dest="action", required=True
    )
    pw.add_parser("set", help="set or change it (hidden prompt); logs out every session").set_defaults(
        func=cmd_password_set
    )
    pw.add_parser("status", help=f"exit 0 if set, {EXIT_NO_PASSWORD} if not").set_defaults(
        func=cmd_password_status
    )
    pw.add_parser("clear-sessions", help="log out every session").set_defaults(func=cmd_clear_sessions)

    inbox = sub.add_parser("inbox", help="read and answer feedback (for /inbox)").add_subparsers(
        dest="action", required=True
    )
    ls = inbox.add_parser("list", help="list items, oldest first")
    ls.add_argument("--status", default="open", choices=[*fb.STATUSES, "all"])
    ls.add_argument("--json", action="store_true")
    _target_args(ls)
    ls.set_defaults(func=cmd_inbox_list)
    count = inbox.add_parser("count", help="number of open items")
    _target_args(count)
    count.set_defaults(func=cmd_inbox_count)
    show = inbox.add_parser("show", help="an item with its thread and doc excerpt")
    show.add_argument("id", type=int)
    show.add_argument("--json", action="store_true")
    show.set_defaults(func=cmd_inbox_show)
    for name, func, text in (
        ("claim", cmd_inbox_claim, "open -> in_progress"),
        ("release", cmd_inbox_release, "in_progress -> open"),
    ):
        p = inbox.add_parser(name, help=text)
        p.add_argument("id", type=int)
        p.set_defaults(func=func)
    rep = inbox.add_parser("reply", help="answer an in-progress item (in_progress -> answered)")
    rep.add_argument("id", type=int)
    rep.add_argument("--file", required=True, help="UTF-8 file with the reply (Markdown), or - for stdin")
    rep.set_defaults(func=cmd_inbox_reply)
    new = inbox.add_parser("create", help="a new item from this session, e.g. a change to report (open)")
    new.add_argument("--to", default=SELF_ID, help="the project it is for (default: archeion)")
    new.add_argument("--kind", default="prompt", choices=fb.KINDS)
    new.add_argument("--file", required=True, help="UTF-8 file with the text (Markdown), or - for stdin")
    new.set_defaults(func=cmd_inbox_create)

    projects = sub.add_parser("projects", help="the project registry").add_subparsers(
        dest="action", required=True
    )
    pl = projects.add_parser("list", help="registered projects, by group, with warnings")
    pl.add_argument("--json", action="store_true")
    pl.set_defaults(func=cmd_projects_list)
    ps = projects.add_parser("scan", help="find unregistered project folders and sub-projects")
    ps.add_argument("--write", action="store_true", help="create stub pages for them")
    ps.add_argument("--root", help="only scan this root ('workspace' or a name from ARCHEION_ROOTS)")
    ps.add_argument("--only", nargs="+", metavar="NAME", help="only these folders (names as scan lists them)")
    ps.set_defaults(func=cmd_projects_scan)
    show = projects.add_parser("show", help="one project's place in the system (for /archeion:context)")
    which = show.add_mutually_exclusive_group(required=True)
    which.add_argument("--project", help="the project's name")
    which.add_argument("--here", action="store_true", help="the project the command runs in")
    show.add_argument("--json", action="store_true")
    show.set_defaults(func=cmd_projects_show)
    ports = projects.add_parser("ports", help="the ports recorded in the registry, by project")
    ports.add_argument("--json", action="store_true")
    ports.set_defaults(func=cmd_projects_ports)

    sub.add_parser("version", help="Archeion's version").set_defaults(func=cmd_version)
    return parser


def _target_args(p: argparse.ArgumentParser) -> None:
    g = p.add_mutually_exclusive_group()
    g.add_argument("--project", help="only items for this project (or 'archeion')")
    g.add_argument("--here", action="store_true", help="only items for the project the command runs in")


def main(argv: list[str] | None = None, settings: Settings | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    try:
        return args.func(settings or Settings(), args)
    except SourceNotFound as exc:
        print(f"No project named '{exc.args[0]}'.", file=sys.stderr)
        return 1
    except fb.FeedbackNotFound as exc:
        print(f"No feedback item #{exc.args[0]}.", file=sys.stderr)
        return 1
    except (fb.FeedbackConflict, ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
