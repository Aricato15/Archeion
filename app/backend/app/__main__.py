"""Command line: python -m app <serve | password | inbox | projects | study ...> (run from app/backend/).

The inbox commands are how an interactive Claude Code session (/inbox) reads and answers
feedback. They work on the backend's own database on this machine, so no API token exists.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import shutil
import sys
from pathlib import Path

from .config import Settings, read_version
from .db import Database
from .paths import DocNotFound, DocPathError
from .security import MIN_PW_LEN, clear_sessions, pw_is_set, set_pw
from .services import designs as dz
from .services import docs_fs, git, study_scan
from .services import feedback as fb
from .services import glossary as gl
from .services import report_render as rr
from .services import reports as rp
from .services import studies as st
from .services.registry import (
    REGISTRY_ID,
    SELF_ID,
    Project,
    RegisterError,
    Registry,
    apply_structure,
    effective_group,
    list_removed,
    modules_of,
    owning_project,
    plan_structure,
    purge,
    restore,
    set_inbox_edits,
    set_type,
    split_frontmatter,
    stub_page,
    unregister,
)
from .services.sources import SourceManager, SourceNotFound

EXIT_NO_PASSWORD = 3

NO_ROOTS = "No roots are granted yet, so Archeion reads no projects. Add one on the viewer's Settings page."


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
    print("No admin password is set. Create it in the viewer, or with: password set")
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


def _with_modules(reg: Registry, p: Project) -> list[str]:
    """A project and the modules it owns: one repository, one session, one inbox (ADR 0016).
    A module on its own (--project <module>) is just itself."""
    return [p.id, *modules_of(reg, p)] if p.type == "project" else [p.id]


def _target(settings: Settings, args: argparse.Namespace) -> list[str] | None:
    """The sources to filter on: --project X, --here (the caller's folder), or None for all.
    A project includes its modules; --here inside a module means the project it's part of."""
    if getattr(args, "project", None):
        project = args.project
        if project in OWN_SOURCES:
            return OWN_SOURCES
        reg = _sources(settings).registry
        if project not in reg.projects:
            raise ValueError(f"'{project}' isn't a registered project (see: projects list)")
        return _with_modules(reg, reg.projects[project])
    if getattr(args, "here", False):
        here = _caller_dir()
        if here.is_relative_to(settings.repo_root.resolve()):
            return OWN_SOURCES
        manager = _sources(settings)
        project = manager.registry.project_for_dir(here)
        if project is None:
            raise ValueError(_not_registered(here, manager))
        return _with_modules(manager.registry, owning_project(manager.registry, project))
    return None


def _caller_dir() -> Path:
    # The wrapper scripts cd into app/backend; they pass the caller's folder along.
    return Path(os.environ.get("ARCHEION_CALLER_DIR") or os.getcwd()).resolve()


def _not_registered(here: Path, manager: SourceManager) -> str:
    msg = f"{here.name} isn't inside a registered project; register it first (projects scan)"
    # A registered project whose root isn't granted here can't be matched by folder.
    missing = sorted(
        f"{p.id} (root '{p.root}')"
        for p in manager.registry.projects.values()
        if p.root and manager.roots.get(p.root) is None
    )
    if missing:
        msg += (
            ". Or it's registered, but its root isn't configured on this machine (ARCHEION_ROOTS"
            f" in Archeion's .env): {', '.join(missing)}"
        )
    return msg


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
        raise ValueError(_not_registered(here, manager))
    return project


def _summary_line(item: dict) -> str:
    where = item["doc_path"] or "(general)"
    if item.get("source", "archeion") != "archeion":
        where = f"[{item['source']}] {where}"
    anchor = item["anchor"] or {}
    if anchor.get("task"):
        where = f"[{anchor['task']['type']} {anchor['task']['project']}]"
    if anchor.get("study"):
        s = anchor["study"]
        where = f"[study {s['project']} {s['snapshot']}] {s['kind']} {s['element']}"
    if anchor.get("heading"):
        where += f" > {anchor['heading']}"
    if anchor.get("lines"):
        where += f" (lines {anchor['lines'][0]}-{anchor['lines'][1]})"
    first = item["body"].strip().splitlines()[0] if item["body"].strip() else ""
    if len(first) > 80:
        first = first[:77] + "..."
    thread = item.get("thread_id")
    parent = f" follow-up in thread #{thread}" if thread and thread != item["id"] else ""
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


STUDY_SECTIONS = {
    "component": ("components",),
    "flow": ("flows",),
    "activity": ("activities",),
    "state machine": ("states",),
    "entity": ("entities",),
    "finding": ("findings",),
    "interface": ("interfaces.exposes", "interfaces.calls"),
}


def _study_excerpt(settings: Settings, item: dict) -> str:
    """For feedback about a study element (ADR 0019): that element from its snapshot, as JSON."""
    study = (item["anchor"] or {}).get("study")
    if not study:
        return ""
    try:
        snap = st.get_snapshot(settings.registry_root, study["project"], study["snapshot"])
    except st.StudyNotFound:
        return f"(snapshot {study['snapshot']} of {study['project']} no longer exists; see: study list)"
    model, _ = st.load(snap)
    for section in STUDY_SECTIONS.get(study["kind"], ()):
        value: object = model
        for key in section.split("."):
            value = value.get(key, []) if isinstance(value, dict) else []
        for element in value if isinstance(value, list) else []:
            if isinstance(element, dict) and element.get("id") == study["element"]:
                text = json.dumps(element, ensure_ascii=False, indent=2)
                return text if len(text) <= 6000 else text[:6000] + "\n..."
    return f"(no {study['kind']} '{study['element']}' in snapshot {snap.id})"


def _item_target(settings: Settings, item: dict) -> dict | None:
    """For an item about a registered project: where its files are and whether Archeion's
    /inbox may edit them (ADR 0017). None for Archeion's own items."""
    source = item.get("source") or SELF_ID
    if source in OWN_SOURCES:
        return None
    reg = _sources(settings).registry
    p = reg.projects.get(source)
    if p is None:
        return {"project": source, "registered": False, "folder": None, "inbox_edits": False}
    home = owning_project(reg, p) if p.type == "module" else p
    return {
        "project": p.id,
        "registered": True,
        "folder": str(p.dir) if p.dir else None,
        # The repository the changes land in: the module's project, for a module.
        "repository": str(home.dir) if home.dir else None,
        "inbox_edits": p.inbox_edits and p.dir is not None,
        "inbox_edits_source": p.inbox_edits_source,
    }


def _target_line(target: dict) -> str:
    if not target["registered"]:
        return f"       target: {target['project']} (no longer registered; no edits)"
    if target["folder"] is None:
        return f"       target: {target['project']} (not available on this machine; no edits)"
    edits = "allowed" if target["inbox_edits"] else "not allowed (answer or ask, don't edit)"
    return f"       target: {target['project']} in {target['folder']}; inbox edits {edits}"


def cmd_inbox_show(settings: Settings, args: argparse.Namespace) -> int:
    """An item with everything needed to answer it. For a follow-up that's the whole thread
    (ADR 0018), in full: the backend builds the conversation, so a reply in the viewer reaches
    Claude with its context. The doc and anchor are the thread's root's."""
    with _db(settings).conn() as conn:
        item = fb.get(conn, args.id)
        thread = fb.thread(conn, args.id)
    root = thread[0] if thread else item
    about = item if item["doc_path"] and item["anchor"] else root
    excerpt = _doc_excerpt(settings, about)
    study_excerpt = _study_excerpt(settings, about)
    target = _item_target(settings, item)
    conversation = fb.conversation(thread, item["id"]) if len(thread) > 1 else ""
    if args.json:
        _print_json(
            {
                "id": item["id"],
                "thread_id": root["id"],
                "latest_id": (thread[-1] if thread else item)["id"],
                "item": item,
                "thread": thread,
                "conversation": conversation,
                "excerpt": excerpt,
                "study_excerpt": study_excerpt,
                "target": target,
            }
        )
        return 0
    print(_summary_line(item))
    print(f"ids: item #{item['id']}, thread #{root['id']}")
    print(f"       created {item['created_at']}, doc at commit {(item['doc_rev'] or '-')[:10]}")
    latest = thread[-1] if thread else item
    print(
        f"       thread #{root['id']}: {len(thread) or 1} message(s),"
        f" newest #{latest['id']} ({latest['status']})"
    )
    if target:
        print(_target_line(target))
    task = (root["anchor"] or {}).get("task")
    if task:
        if task["type"] == "study":
            draft = st.get_draft(settings.registry_root, task["project"])
            state = f"draft in registry/studies/{task['project']}/draft/" if draft else "no draft yet"
            print(f"       task: a {task['type']} of {task['project']} (ADR 0020); {state}")
            print("       follow the study skill's conversation mode for this round")
        elif task["type"] == "report":
            found = rp.get_plan(settings.registry_root, task["project"])
            plan = found["plan"] if found else None
            state = f"plan with {len(plan['sections'])} sections" if plan else "no plan yet"
            print(f"       task: a report of {task['project']} (ADR 0025); {state}")
            print("       follow the report-guided skill's conversation mode for this round")
        else:
            slug = task.get("slug") or dz.DEFAULT_SLUG
            try:
                stage = dz.get(settings.registry_root, task["project"], slug).stage
                state = f"stage {stage}, in registry/designs/{task['project']}/{slug}/"
            except dz.DesignNotFound:
                state = "no design yet"
            print(f"       task: a {task['type']} of {task['project']} '{slug}' (ADR 0022); {state}")
            if task["type"] == "design":
                print("       follow the design skill's conversation mode for this round")
            else:
                rev = task.get("revision", "latest")
                print(
                    f"       deliver revision {rev}: design package {task['project']} --slug {slug}"
                    f" --revision {rev} (after design preflight {task['project']} --for handoff)"
                )
    anchor = about["anchor"] or {}
    if anchor.get("quote") and not conversation:
        print()
        print("Quoted text:")
        for line in anchor["quote"].splitlines():
            print(f"  > {line}")
    if excerpt:
        if about.get("source", "archeion") == "archeion":
            where = f"docs/{about['doc_path']}"
        else:
            where = f"{about['doc_path']} in {about['source']}"
        print()
        print(f"Doc excerpt ({where}):")
        print(excerpt)
    if study_excerpt:
        s = about["anchor"]["study"]
        print()
        print(
            f"Study element ({s['kind']} '{s['element']}', registry/studies/{s['project']}/{s['snapshot']}/):"
        )
        print(study_excerpt)
    if conversation:
        print()
        print(f"Conversation so far ({len(thread)} messages; answer the one marked 'Your request now'):")
        print()
        print(conversation)
        return 0
    print()
    print("Request:")
    print(item["body"])
    if item["reply"]:
        print()
        print("Current reply:")
        print(item["reply"])
    return 0


def _done(args: argparse.Namespace, item: dict, text: str) -> int:
    """What a write command prints: the sentence, then the ids a session needs to carry on, on a
    fixed line (`ids: item #N, thread #T`). With --json, just the ids and the state."""
    if getattr(args, "json", False):
        keys = ("id", "thread_id", "parent_id", "status", "kind", "source", "origin")
        _print_json({k: item.get(k) for k in keys})
    else:
        print(text)
        print(f"ids: item #{item['id']}, thread #{item['thread_id']}")
    return 0


def cmd_inbox_claim(settings: Settings, args: argparse.Namespace) -> int:
    with _db(settings).conn() as conn:
        item = fb.claim(conn, args.id)
    return _done(args, item, f"Claimed #{item['id']} (thread #{item['thread_id']}).")


def cmd_inbox_release(settings: Settings, args: argparse.Namespace) -> int:
    with _db(settings).conn() as conn:
        item = fb.release(conn, args.id)
    return _done(args, item, f"Released #{item['id']}; it's open again.")


def _read_text_arg(value: str) -> str:
    if value == "-":
        return sys.stdin.buffer.read().decode("utf-8")
    return Path(value).read_text(encoding="utf-8")


def _caller_origin(settings: Settings, manager: SourceManager) -> str | None:
    """The registered project the caller's folder is in, or None (Archeion itself, or elsewhere)."""
    here = _caller_dir()
    if here.is_relative_to(settings.repo_root.resolve()):
        return None
    found = manager.registry.project_for_dir(here)
    return found.id if found else None


def cmd_inbox_create(settings: Settings, args: argparse.Namespace) -> int:
    """A new item, written from a session rather than the viewer (/archeion:notify). It
    records which registered project the caller is in as its origin (ADR 0009).

    With --in, it's the next message in that thread instead (ADR 0018), as a reply typed in
    the viewer would be: it keeps the thread's project and doc, and its kind unless --kind
    names one. So a session can carry on a conversation instead of starting a new one each time.
    """
    manager = _sources(settings)
    origin = _caller_origin(settings, manager)
    body = _read_text_arg(args.file).strip()
    if not body:
        raise ValueError("the item is empty")
    if args.thread is not None:
        if args.to is not None:
            raise ValueError("--to and --in don't go together: a reply stays with its thread's project")
    elif args.claim:
        raise ValueError("--claim only goes with --in")
    if args.thread is not None:
        with _db(settings).conn() as conn:
            first = fb.root(conn, args.thread)
            item = fb.create(
                conn,
                kind=args.kind or first["kind"],
                body=body,
                doc_path=first["doc_path"],
                parent_id=args.thread,
                source=first["source"],
                origin=origin,
                claimed=args.claim,
            )
        state = f"claimed, answer it with: inbox reply {item['id']}" if args.claim else "open"
        return _done(
            args,
            item,
            f"Added #{item['id']} to thread #{item['thread_id']} (for {item['source']}),"
            f" after #{item['parent_id']}; {state}. It shows up in the viewer under the thread.",
        )
    to = args.to or SELF_ID
    if to == REGISTRY_ID:
        to = SELF_ID
    if to != SELF_ID and to not in manager.registry.projects:
        raise ValueError(f"'{to}' isn't a registered project (see: projects list)")
    with _db(settings).conn() as conn:
        item = fb.create(conn, kind=args.kind or "prompt", body=body, source=to, origin=origin)
    sender = f" from {origin}" if origin else ""
    return _done(
        args, item, f"Created #{item['id']} ({item['kind']}) for {to}{sender}. It shows up in the viewer."
    )


def cmd_inbox_resolve(settings: Settings, args: argparse.Namespace) -> int:
    """Close a whole thread, from any of its messages, as Resolve thread in the viewer does."""
    with _db(settings).conn() as conn:
        item = fb.resolve_thread(conn, args.id)
    return _done(args, item, f"Resolved thread #{item['thread_id']}.")


ACTIVE = ("open", "in_progress", "answered")


def cmd_inbox_threads(settings: Settings, args: argparse.Namespace) -> int:
    """Conversations, one row per thread, most recently changed first (as the viewer lists them).
    --from-here narrows to the threads this project started (/archeion:notify), so a session
    can find the conversation it's carrying on."""
    source = _target(settings, args)
    origin = None
    if args.from_here:
        manager = _sources(settings)
        here = _caller_dir()
        project = None
        if not here.is_relative_to(settings.repo_root.resolve()):
            project = manager.registry.project_for_dir(here)
        if project is None:
            raise ValueError(_not_registered(here, manager))
        origin = _with_modules(manager.registry, owning_project(manager.registry, project))
    status = None if args.status in ("all", "active") else args.status
    with _db(settings).conn() as conn:
        threads = fb.list_threads(conn, status=status, source=source, origin=origin, limit=500)
    if args.status == "active":
        threads = [t for t in threads if t["status"] in ACTIVE]
    threads = threads[: args.limit]
    if args.json:
        _print_json(threads)
        return 0
    if not threads:
        print(f"No {args.status} threads.")
        return 0
    for t in threads:
        print(_summary_line(t))
        print(f"       {t['messages']} message(s), latest #{t['latest_id']}, changed {t['updated_at']}")
        if t["reply"]:
            last = t["reply"].strip().splitlines()[0] if t["reply"].strip() else ""
            print(f"       last reply: {last[:77] + '...' if len(last) > 80 else last}")
    return 0


def cmd_inbox_reply(settings: Settings, args: argparse.Namespace) -> int:
    if args.file == "-":
        text = sys.stdin.buffer.read().decode("utf-8")
    else:
        text = Path(args.file).read_text(encoding="utf-8")
    with _db(settings).conn() as conn:
        item = fb.reply(conn, args.id, text.strip())
    return _done(
        args,
        item,
        f"Replied to #{item['id']}; it's now answered. To carry on: inbox create --in {item['thread_id']}",
    )


# --- projects ---------------------------------------------------------------------------


def cmd_projects_list(settings: Settings, args: argparse.Namespace) -> int:
    manager = _sources(settings)
    reg = manager.registry
    if args.json:
        _print_json({**reg.public(), "unregistered": manager.unregistered()})
        return 0
    if not reg.projects:
        print("No projects registered yet. Run: projects scan" if manager.roots.all() else NO_ROOTS)

    def show(pid: str, depth: int) -> None:
        p = reg.projects[pid]
        flags = (
            [p.status] + (["module"] if p.type == "module" else []) + ([f"root {p.root}"] if p.root else [])
        )
        flags += [] if p.available or not p.path else ["not available"]
        flags += [] if p.inbox_edits else ["no inbox edits"]
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
        known = ", ".join(name for name, _ in manager.roots.all()) or "none"
        raise ValueError(f"no root named '{args.root}' (configured: {known}; see ARCHEION_ROOTS)")
    if not manager.roots.all():
        print(NO_ROOTS)
        return 0
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
            # ADR 0017: a project's page says inbox_edits outright; a module follows its project.
            edits = True if item.get("detected_type", "project") == "project" else None
            page.write_text(stub_page({**item, "inbox_edits": edits}), encoding="utf-8")
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
    how = "set on its page" if facts["type_source"] == "page" else "detected"
    of = f" of {facts['owner']}" if facts["owner"] else ""
    print(f"  type: {facts['type']}{of} ({how})")
    print(f"  inbox edits: {_edits_text(facts)}")
    if facts["group"]:
        inherited = " (from its parent)" if facts["group_inherited"] else ""
        print(f"  group: {facts['group']} ({facts['group_title']}){inherited}")
        others = [m for m in facts["group_members"] if m != facts["id"]]
        print(f"    with: {names(others)}")
    else:
        print("  group: none (standalone)")
    if facts["parent"]:
        print(f"  part of: {facts['parent']}")
    reg = manager.registry
    modules = sorted(c for c in facts["children"] if reg.projects[c].type == "module")
    nested = sorted(c for c in facts["children"] if reg.projects[c].type == "project")
    if modules:
        print(f"  modules: {names(modules)}")
    if nested:
        print(f"  sub-projects: {names(nested)}")
    print(f"  depends on: {names(facts['depends_on'])}")
    print(f"  used by: {names(sorted(facts['used_by']))}")
    print(f"  ports: {', '.join(str(n) for n in facts['ports']) or 'none'}")
    print(f"  verified: {facts['verified'] or 'never'}")
    print(f"  registry page: registry/{facts['page']}")
    if facts["notes"]:
        print("\nNotes from the registry page:")
        print(facts["notes"])
    return 0


def cmd_projects_type(settings: Settings, args: argparse.Namespace) -> int:
    manager = _sources(settings)
    reg = manager.registry
    if args.name not in reg.projects:
        raise ValueError(f"'{args.name}' isn't a registered project (see: projects list)")
    value = None if args.type == "auto" else args.type
    page = set_type(manager.registry_root, reg, args.name, value)
    manager.reload()
    p = manager.registry.projects[args.name]
    how = "set on its page" if p.type_source == "page" else "detected"
    of = f" of {p.owner}" if p.owner else ""
    print(f"{p.id}: {p.type}{of} ({how}); registry/{page}")
    return 0


def _edits_text(facts: dict) -> str:
    """Whether Archeion's /inbox may edit the project's files, and where that comes from."""
    how = {
        "page": "set on its page",
        "owner": f"from {facts.get('owner')}",
        "default": "default",
    }.get(facts["inbox_edits_source"], facts["inbox_edits_source"])
    return f"{'allowed' if facts['inbox_edits'] else 'not allowed'} ({how})"


def cmd_projects_inbox_edits(settings: Settings, args: argparse.Namespace) -> int:
    manager = _sources(settings)
    reg = manager.registry
    if args.name not in reg.projects:
        raise ValueError(f"'{args.name}' isn't a registered project (see: projects list)")
    value = {"on": True, "off": False, "auto": None}[args.value]
    page = set_inbox_edits(manager.registry_root, reg, args.name, value)
    manager.reload()
    p = manager.registry.projects[args.name]
    print(f"{p.id}: inbox edits {_edits_text(p.public())}; registry/{page}")
    return 0


def cmd_projects_remove(settings: Settings, args: argparse.Namespace) -> int:
    """Take a project out of the registry (ADR 0026): its page moves to registry/removed/."""
    manager = _sources(settings)
    if args.name not in manager.registry.projects:
        raise ValueError(f"'{args.name}' isn't a registered project (see: projects list)")
    result = unregister(manager.registry_root, manager.registry, args.name)
    print(f"{args.name}: removed; its page is now registry/{result['moved_to']}")
    if result["used_by"]:
        print(f"  still listed in depends_on by: {', '.join(result['used_by'])}")
    return 0


def cmd_projects_removed(settings: Settings, args: argparse.Namespace) -> int:
    """Projects that were removed and not registered since (ADR 0026)."""
    manager = _sources(settings)
    rows = [e for e in list_removed(manager.registry_root) if e["name"] not in manager.registry.projects]
    if not rows:
        print("No removed projects.")
        return 0
    for e in rows:
        kept = ", ".join(e["kept"]) or "only its page"
        print(f"{e['name']}  removed {e['removed_on']}  kept: {kept}")
    return 0


def cmd_projects_restore(settings: Settings, args: argparse.Namespace) -> int:
    manager = _sources(settings)
    try:
        page = restore(manager.registry_root, manager.registry, args.name)
    except KeyError:
        raise ValueError(f"'{args.name}' wasn't removed (see: projects removed)") from None
    print(f"{args.name}: restored; registry/{page}")
    return 0


def cmd_projects_purge(settings: Settings, args: argparse.Namespace) -> int:
    """Delete a removed project for good. Needs --yes, since it can't be undone."""
    manager = _sources(settings)
    if not args.yes:
        raise ValueError(
            f"this deletes '{args.name}' and what the registry kept for it for good: add --yes to go ahead"
        )
    try:
        gone = purge(manager.registry_root, manager.registry, args.name)
    except KeyError:
        raise ValueError(f"'{args.name}' wasn't removed (see: projects removed)") from None
    print(f"{args.name}: deleted {', '.join('registry/' + g for g in gone)}")
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


# --- study (ADR 0019) -------------------------------------------------------------------


def _study_project(manager: SourceManager, name: str) -> Project:
    reg = manager.registry
    if name not in reg.projects:
        raise ValueError(f"'{name}' isn't a registered project (see: projects list)")
    p = reg.projects[name]
    if p.dir is None:
        raise ValueError(
            f"{name}'s folder isn't available on this machine (see: projects show --project {name})"
        )
    return p


def _git_state(folder: Path) -> tuple[str | None, bool | None]:
    try:
        return git.head(folder), git.is_worktree_dirty(folder)
    except git.GitError:
        return None, None


def cmd_study_scan(settings: Settings, args: argparse.Namespace) -> int:
    """A read-only inventory of the project's code, to ground a study in."""
    p = _study_project(_sources(settings), args.project)
    commit, dirty = _git_state(p.dir)
    inv = study_scan.scan(p.dir, p.id, commit, dirty)
    data = inv.public()
    if args.out:
        Path(args.out).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json:
        _print_json(data)
    else:
        print(study_scan.text_report(inv))
        if args.out:
            print(f"\nThe full inventory is in {args.out}.")
    return 0


def _print_study(study: st.Study) -> None:
    print(_study_counts(study))
    for w in st.structure_warnings(study):
        print(f"Warning: {w}.")


def _study_counts(study: st.Study) -> str:
    m = study.meta
    return (
        f"{m.project} at {m.commit[:10]} ({m.date.isoformat()}): {len(study.components)} components,"
        f" {len(study.relations)} relations, {len(study.interfaces.exposes)} exposed,"
        f" {len(study.interfaces.calls)} outgoing calls, {len(study.entities)} entities,"
        f" {len(study.flows)} flows, {len(study.activities)} activities, {len(study.states)} state"
        f" machines, {len(study.findings)} findings"
    )


def cmd_study_validate(settings: Settings, args: argparse.Namespace) -> int:
    study = st.parse_text(_read_text_arg(args.file))
    _print_study(study)
    print("Valid.")
    return 0


def cmd_study_save(settings: Settings, args: argparse.Namespace) -> int:
    """Validate a study and store it as a new snapshot; the only way one is written."""
    manager = _sources(settings)
    p = _study_project(manager, args.project)
    if args.from_draft:
        if args.file or args.notes:
            raise ValueError("--from-draft takes the draft's model and notes; leave out --file and --notes")
        snap, pruned = st.promote_draft(settings.registry_root, p.id, keep=settings.study_keep)
        print(f"Saved the draft of {p.id} as a snapshot; the draft is gone.")
    else:
        if not args.file:
            raise ValueError("give --file <study.json>, or --from-draft")
        study = _study_for(p, args.file)
        notes = Path(args.notes).read_text(encoding="utf-8") if args.notes else None
        snap, pruned = st.save(settings.registry_root, study, notes=notes, keep=settings.study_keep)
        _print_study(study)
    print(f"Saved snapshot {snap.id}: registry/{st.STUDIES_DIR}/{p.id}/{snap.id}/")
    if pruned:
        print(f"Pruned {len(pruned)} older snapshot(s) (keeping {settings.study_keep}): {', '.join(pruned)}")
    return 0


def _study_for(p: Project, file: str) -> st.Study:
    study = st.parse_text(_read_text_arg(file))
    if study.meta.project != p.id:
        raise ValueError(f"the study is for '{study.meta.project}', not '{p.id}'")
    return study


def cmd_study_draft_save(settings: Settings, args: argparse.Namespace) -> int:
    """Keep the study in progress between the rounds of its conversation (ADR 0020)."""
    p = _study_project(_sources(settings), args.project)
    study = _study_for(p, args.file)
    notes = Path(args.notes).read_text(encoding="utf-8") if args.notes else None
    draft = st.save_draft(settings.registry_root, study, notes=notes, thread=args.thread)
    thread = draft.info().get("thread")
    _print_study(study)
    print(
        f"Saved the draft: registry/{st.STUDIES_DIR}/{p.id}/{st.DRAFT}/"
        + (f" (thread #{thread})" if thread else "")
        + ". The Study tab shows it as Draft."
    )
    return 0


def cmd_study_draft_show(settings: Settings, args: argparse.Namespace) -> int:
    manager = _sources(settings)
    if args.project not in manager.registry.projects:
        raise ValueError(f"'{args.project}' isn't a registered project (see: projects list)")
    draft = st.get_draft(settings.registry_root, args.project)
    if draft is None:
        print(f"No draft for {args.project}.")
        return 0
    model, problems = st.load(draft)
    if args.json:
        _print_json({"thread": draft.info().get("thread"), "model": model, "notes": st.load_notes(draft)})
        return 0
    row = st.summary(draft)
    print(f"Draft of {args.project}" + (f" (thread #{row['thread']})" if row["thread"] else ""))
    print("  " + ", ".join(f"{k} {v}" for k, v in row["counts"].items()))
    for prob in problems:
        print(f"  problem: {prob}")
    return 0


def cmd_study_draft_discard(settings: Settings, args: argparse.Namespace) -> int:
    gone = st.discard_draft(settings.registry_root, args.project)
    print(f"Discarded the draft of {args.project}." if gone else f"No draft for {args.project}.")
    return 0


def _commits_since(p: Project, commit: str | None) -> int | None:
    if not commit or p.dir is None:
        return None
    try:
        return git.commits_since(p.dir, commit)
    except git.GitError:
        return None


def cmd_study_list(settings: Settings, args: argparse.Namespace) -> int:
    manager = _sources(settings)
    reg = manager.registry
    if args.project and args.project not in reg.projects:
        raise ValueError(f"'{args.project}' isn't a registered project (see: projects list)")
    if args.project:
        rows = [st.summary(s) for s in st.snapshots(settings.registry_root, args.project)]
    else:
        rows = [st.summary(s) for s in st.latest_by_project(settings.registry_root).values()]
    for row in rows:
        p = reg.projects.get(row["project"])
        row["commits_since"] = _commits_since(p, row["commit"]) if p else None
    if args.json:
        _print_json(rows)
        return 0
    if not rows:
        print("No studies yet." + ("" if args.project else " Run /study <project> in Archeion's session."))
        return 0
    for row in rows:
        since = row["commits_since"]
        age = "" if since is None else (" (current)" if since == 0 else f" ({since} commits since)")
        bad = "" if row["valid"] else "  INVALID: " + "; ".join(row["problems"])[:200]
        print(f"{row['project']:<24} {row['id']}{age}{bad}")
    return 0


def cmd_study_show(settings: Settings, args: argparse.Namespace) -> int:
    manager = _sources(settings)
    if args.project not in manager.registry.projects:
        raise ValueError(f"'{args.project}' isn't a registered project (see: projects list)")
    snap = st.get_snapshot(settings.registry_root, args.project, args.snapshot)
    model, problems = st.load(snap)
    if args.json:
        _print_json({"id": snap.id, "model": model, "notes": st.load_notes(snap), "problems": problems})
        return 0
    row = st.summary(snap)
    since = _commits_since(manager.registry.projects[args.project], row["commit"])
    head = f"{snap.project} {snap.id}: commit {(row['commit'] or '?')[:10]}"
    print(head + ("" if since is None else f", {since} commits since"))
    if row["summary"]:
        print(f"  {row['summary']}")
    print("  " + ", ".join(f"{k} {v}" for k, v in row["counts"].items()))
    for prob in problems:
        print(f"  problem: {prob}")
    print(f"  files: registry/{st.STUDIES_DIR}/{snap.project}/{snap.id}/")
    return 0


def cmd_study_changes(settings: Settings, args: argparse.Namespace) -> int:
    """What changed in the project since its latest snapshot: the files a refresh rereads."""
    manager = _sources(settings)
    p = _study_project(manager, args.project)
    snap = st.get_snapshot(settings.registry_root, p.id, "latest")
    commit = st.summary(snap)["commit"]
    try:
        files = git.changed_files(p.dir, commit) if commit else None
    except git.GitError:
        files = None
    if files is None:
        raise ValueError(f"can't compare with {snap.id}'s commit; study the whole project instead")
    if args.json:
        _print_json({"snapshot": snap.id, "commit": commit, "files": files})
        return 0
    print(f"{len(files)} file(s) changed since {snap.id} (commit {commit[:10]}):")
    for f in files:
        print(f"  {f}")
    return 0


# --- design (ADR 0022) ------------------------------------------------------------------

EXIT_PREFLIGHT = 4


def _design_project(manager: SourceManager, name: str) -> Project:
    reg = manager.registry
    if name not in reg.projects:
        raise ValueError(f"'{name}' isn't a registered project (see: projects list)")
    return reg.projects[name]


def _ports_taken(reg: Registry) -> dict[int, list[str]]:
    taken: dict[int, list[str]] = {}
    for p in reg.projects.values():
        for port in p.ports:
            taken.setdefault(port, []).append(p.id)
    return taken


def _design_ref(settings: Settings, project: str, slug: str) -> dz.DesignRef:
    try:
        return dz.get(settings.registry_root, project, slug)
    except dz.DesignNotFound as exc:
        raise ValueError(
            f"{project} has no design '{slug}' (see: design list {project};"
            f" start one with: design init {project})"
        ) from exc


def _design_row(row: dict) -> str:
    rev = f", revision {row['revision']}" if row["revision"] else ""
    bad = "" if row["valid"] else "  INVALID: " + "; ".join(row["problems"])[:200]
    return f"{row['project']:<24} {row['slug']:<14} {row['stage']}{rev}{bad}"


def cmd_design_preflight(settings: Settings, args: argparse.Namespace) -> int:
    """What must be true before a design step, each problem with its fix. Exit 0 when nothing
    blocks, 4 when something does. Skills run this first (ADR 0022 point 11)."""
    manager = _sources(settings)
    reg = manager.registry
    unregistered = [u["name"] for u in manager.unregistered()] if manager.roots.all() else []
    has_study = bool(args.project in reg.projects and st.snapshots(settings.registry_root, args.project))
    problems = dz.preflight(
        reg,
        project=args.project,
        unregistered=unregistered,
        purpose=args.purpose,
        slug=args.slug,
        registry_root=settings.registry_root,
        has_study=has_study,
    )
    blocked = any(p["severity"] == "block" for p in problems)
    if args.json:
        _print_json({"ok": not blocked, "problems": problems})
    elif not problems:
        print(f"Ready: nothing in the way of a {args.purpose} for {args.project}.")
    else:
        for pr in problems:
            print(f"{pr['severity']:<5} {pr['message']}")
            if pr["fix"]:
                print(f"      fix: {pr['fix']}")
    return EXIT_PREFLIGHT if blocked else 0


def _workspace_rules() -> str:
    ranges = "; ".join(f"{name} {lo}-{hi}" for lo, hi, name in dz.PORT_RANGES)
    return (
        f"Ports: every server listens on a port in its category's range: {ranges}. Check the ports in use"
        " before choosing one.\n"
        "Databases: each service that needs a relational database gets its own SQLite file, owned by that"
        " service alone; no other service opens it, and there are no foreign keys or joins across services"
        " (a reference to another service's data is a plain id).\n"
        "Environments stay inside the project (uv for Python with .venv/, npm for Node);"
        " never global installs.\n"
        "Shell is Windows: prefer Node, Python or PowerShell scripts over bash-only tooling."
    )


def _neighbour(manager: SourceManager, settings: Settings, pid: str) -> dict:
    p = manager.registry.projects[pid]
    snaps = st.snapshots(settings.registry_root, pid)
    exposes: list[dict] = []
    studied = None
    if snaps:
        model, problems = st.load(snaps[0])
        studied = snaps[0].id
        if not problems:
            exposes = [
                {k: x.get(k) for k in ("kind", "method", "path", "name", "summary") if x.get(k)}
                for x in (model.get("interfaces") or {}).get("exposes", [])
            ][:60]
    return {
        "id": p.id,
        "title": p.title,
        "status": p.status,
        "kind": p.kind,
        "ports": p.ports,
        "depends_on": p.depends_on,
        "used_by": p.used_by,
        "summary": p.summary,
        "studied": studied,
        "exposes": exposes,
    }


def _claude_md(p: Project) -> str | None:
    if p.dir is None:
        return None
    f = p.dir / "CLAUDE.md"
    if not f.is_file():
        return None
    text = f.read_text(encoding="utf-8", errors="replace")
    return text if len(text) <= 12000 else text[:12000] + "\n... (cut)"


def cmd_design_context(settings: Settings, args: argparse.Namespace) -> int:
    """Everything a design round needs to know about the system, in one read-only bundle."""
    manager = _sources(settings)
    reg = manager.registry
    p = _design_project(manager, args.project)
    facts = _project_facts(manager, p)
    near = sorted({*p.depends_on, *p.used_by, *facts["group_members"]} - {p.id})
    near = [n for n in near if n in reg.projects]
    overview = settings.registry_root / "overview.md"
    data = {
        "project": facts,
        "has_code": dz.has_code(p.dir),
        "claude_md": _claude_md(p),
        "studied": bool(st.snapshots(settings.registry_root, p.id)),
        "neighbours": [_neighbour(manager, settings, n) for n in near],
        "ports_in_use": [{"port": port, "projects": ids} for port, ids in sorted(_ports_taken(reg).items())],
        "groups": [g.id for g in reg.groups.values()],
        "registered_projects": sorted(reg.projects),
        "designs": [
            dz.summary(dz.get(settings.registry_root, p.id, s))
            for s in dz.slugs(settings.registry_root, p.id)
        ],
        "overview": overview.read_text(encoding="utf-8", errors="replace")[:4000]
        if overview.is_file()
        else "",
        "rules": _workspace_rules(),
    }
    if args.json:
        _print_json(data)
        return 0
    print(f"# Design context for {p.id}")
    print(
        f"\nStatus: {p.status}; kind: {p.kind or '-'}; ports: {p.ports or 'none'};"
        f" depends on: {p.depends_on or 'none'}"
    )
    print(
        f"Folder: {'available' if p.dir else 'not available'}; has code: {data['has_code']};"
        f" studied: {data['studied']}"
    )
    if data["designs"]:
        print("\nExisting designs: " + ", ".join(f"{d['slug']} ({d['stage']})" for d in data["designs"]))
    print("\n## The project's own CLAUDE.md")
    print(data["claude_md"] or "(none: ask for the tech stack)")
    if facts["notes"]:
        print("\n## Its registry page notes")
        print(facts["notes"])
    print("\n## Neighbours (group, depends_on, used_by)")
    for n in data["neighbours"]:
        studied = f", studied {n['studied']}" if n["studied"] else ", not studied"
        print(f"- {n['id']} ({n['status']}, {n['kind'] or '-'}), ports {n['ports'] or 'none'}{studied}")
        if n["summary"]:
            print(f"  {n['summary']}")
        for ex in n["exposes"][:20]:
            print("  exposes: " + " ".join(str(ex[k]) for k in ("method", "path", "name") if ex.get(k)))
    print("\n## Ports in use")
    print(", ".join(f"{r['port']} ({'/'.join(r['projects'])})" for r in data["ports_in_use"]) or "none")
    print(f"\n## Groups you may use: {', '.join(data['groups']) or 'none'}")
    print(f"\n## Registered projects (for depends_on): {', '.join(data['registered_projects'])}")
    if data["overview"]:
        print("\n## Registry overview")
        print(data["overview"])
    print("\n## Workspace rules")
    print(data["rules"])
    return 0


def cmd_design_list(settings: Settings, args: argparse.Namespace) -> int:
    manager = _sources(settings)
    if args.project:
        _design_project(manager, args.project)
    names = [args.project] if args.project else dz.projects_with_designs(settings.registry_root)
    rows = [
        dz.summary(dz.get(settings.registry_root, n, s))
        for n in names
        for s in dz.slugs(settings.registry_root, n)
    ]
    if args.json:
        _print_json(rows)
        return 0
    if not rows:
        print("No designs yet." + (f" Start one: design init {args.project}" if args.project else ""))
        return 0
    for row in rows:
        print(_design_row(row))
    return 0


def cmd_design_init(settings: Settings, args: argparse.Namespace) -> int:
    manager = _sources(settings)
    p = _design_project(manager, args.project)
    ref = dz.init(settings.registry_root, p.id, args.slug, thread=args.thread, summary=args.summary or "")
    print(
        f"Started design '{ref.slug}' for {p.id}: registry/{dz.DESIGNS_DIR}/{p.id}/{ref.slug}/"
        " (stage: brief)."
    )
    print(
        "Write brief.md, architecture.md, plan.md, questions.md, decisions/ and model.json"
        " into a work folder,"
    )
    print(f"then: design save {p.id} --slug {ref.slug} --dir <folder>")
    return 0


def cmd_design_show(settings: Settings, args: argparse.Namespace) -> int:
    manager = _sources(settings)
    p = _design_project(manager, args.project)
    ref = _design_ref(settings, p.id, args.slug)
    if args.revision:
        rev, folder = dz.revision_folder(ref, args.revision)
        label = f"revision {rev['number']} ({rev['id']})"
    else:
        folder, label = ref.folder, "working copy"
    model, problems = dz.load(folder, p.id)
    files = dz.read_files(folder)
    if args.json:
        _print_json({**dz.summary(ref), "label": label, "files": files, "model": model, "problems": problems})
        return 0
    row = dz.summary(ref)
    print(_design_row(row) + f"   [{label}]")
    if row["summary"]:
        print(f"  {row['summary']}")
    print("  " + ", ".join(f"{k} {v}" for k, v in row["counts"].items()))
    for prob in problems:
        print(f"  problem: {prob}")
    for name, text in files.items():
        print(f"  {name}: {'written' if text.strip() else 'empty'}")
    if row["revisions"]:
        print("  revisions: " + ", ".join(r["id"] for r in row["revisions"]))
    print(f"  files: registry/{dz.DESIGNS_DIR}/{p.id}/{ref.slug}/")
    return 0


def cmd_design_validate(settings: Settings, args: argparse.Namespace) -> int:
    manager = _sources(settings)
    p = _design_project(manager, args.project)
    files, model = dz.read_workdir(Path(args.dir))
    problems = [x for n, t in files.items() for x in dz.prose_problems(n, t)]
    if model is not None:
        try:
            dz.parse(
                model, project=p.id, registry=manager.registry, ports_taken=_ports_taken(manager.registry)
            )
        except dz.DesignError as exc:
            problems.append(str(exc))
    if problems:
        raise dz.DesignError("; ".join(problems))
    print(f"Valid: {len(files)} file(s)" + (", and a model." if model is not None else ", no model."))
    return 0


def cmd_design_save(settings: Settings, args: argparse.Namespace) -> int:
    """Replace a design's working copy with the files in a work folder (the only way one is
    written). Files the folder lacks stay as they are."""
    manager = _sources(settings)
    p = _design_project(manager, args.project)
    ref = _design_ref(settings, p.id, args.slug)
    files, model = dz.read_workdir(Path(args.dir))
    was = ref.stage
    dz.save(
        settings.registry_root,
        ref,
        files=files,
        model=model,
        registry=manager.registry,
        ports_taken=_ports_taken(manager.registry),
        thread=args.thread,
    )
    row = dz.summary(ref)
    what = f"{len(files)} file(s)" + (" and the model" if model is not None else "")
    print(f"Saved design '{ref.slug}' of {p.id}: {what}.")
    print("  " + ", ".join(f"{k} {v}" for k, v in row["counts"].items()))
    if was in ("approved", "handed off"):
        print(f"  It was {was}; it's back at stage plan, since it differs from its latest revision.")
    print(f"  Stage: {row['stage']}. The Design tab shows it as a draft until it's approved.")
    return 0


def cmd_design_stage(settings: Settings, args: argparse.Namespace) -> int:
    manager = _sources(settings)
    ref = _design_ref(settings, _design_project(manager, args.project).id, args.slug)
    dz.set_stage(ref, args.stage)
    print(f"{ref.project} '{ref.slug}': stage is now {args.stage}.")
    return 0


def cmd_design_approve(settings: Settings, args: argparse.Namespace) -> int:
    """Freeze the working copy as a revision and write the structural facts into the project's
    registry page. Without --yes, shows what it would do and changes nothing."""
    manager = _sources(settings)
    reg = manager.registry
    p = _design_project(manager, args.project)
    ref = _design_ref(settings, p.id, args.slug)
    taken = _ports_taken(reg)
    problems = dz.approval_problems(ref, reg, taken)
    if problems:
        raise dz.DesignError("; ".join(problems))
    model, _ = dz.load(ref.folder, p.id)
    structure = model.get("structure", {})
    try:
        changes = [] if args.no_registry else plan_structure(manager.registry_root, reg, p.id, structure)
    except RegisterError as exc:
        raise ValueError(str(exc)) from exc
    revs = dz.revisions(ref)
    print(f"Approving '{ref.slug}' of {p.id} would freeze revision {(revs[0]['number'] if revs else 0) + 1}.")
    if changes:
        print(f"It would change these lines in registry/{p.page}:")
        for c in changes:
            old = c["old"] if c["old"] not in (None, []) else "(not set)"
            print(f"  {c['key']}: {old} -> {c['value']}")
    else:
        print(
            "The registry page is left alone." if args.no_registry else "The registry page needs no changes."
        )
    if not args.yes:
        print("Nothing was changed. Run again with --yes once the user has agreed.")
        return 0
    rev = dz.approve(ref, reg, taken)
    if changes:
        try:
            apply_structure(manager.registry_root, reg, p.id, structure)
        except RegisterError as exc:
            raise ValueError(
                f"revision {rev['number']} was frozen, but the registry page wasn't updated: {exc}"
            ) from exc
        manager.reload()
    print(
        f"Approved: revision {rev['number']} ({rev['id']})."
        f" Hand it off with: design handoff {p.id} --slug {ref.slug}"
    )
    return 0


def cmd_design_handoff(settings: Settings, args: argparse.Namespace) -> int:
    """Ask Archeion's /inbox to deliver a revision to the project: a thread for Archeion
    (anchor.task = handoff-design), like a study conversation."""
    manager = _sources(settings)
    reg = manager.registry
    p = _design_project(manager, args.project)
    unregistered = [u["name"] for u in manager.unregistered()] if manager.roots.all() else []
    blocking = [
        x
        for x in dz.preflight(
            reg,
            project=p.id,
            unregistered=unregistered,
            purpose="handoff",
            slug=args.slug,
            registry_root=settings.registry_root,
            has_study=True,
        )
        if x["severity"] == "block"
    ]
    if blocking:
        raise ValueError(
            "; ".join(f"{x['message']} Fix: {x['fix']}" if x["fix"] else x["message"] for x in blocking)
        )
    ref = _design_ref(settings, p.id, args.slug)
    rev, _ = dz.revision_folder(ref, args.revision)
    body = (
        f"Deliver revision {rev['number']} of the design '{ref.slug}' to {p.id}: copy its package into the"
        f" project's {dz.PACKAGE_DIR}/{ref.slug}/ with `design package {p.id} --slug {ref.slug}"
        f" --revision {rev['number']}`, then reply with the files. The project's session then runs"
        " /archeion:consume-design."
    )
    anchor = {
        "task": {"type": "handoff-design", "project": p.id, "slug": ref.slug, "revision": rev["number"]}
    }
    with _db(settings).conn() as conn:
        item = fb.create(conn, kind="prompt", body=body, anchor=anchor, source=SELF_ID)
    dz.record_handoff(ref, rev["number"], item["thread_id"])
    return _done(args, item, f"Handoff of revision {rev['number']} to {p.id} requested in Archeion's inbox.")


def cmd_design_package(settings: Settings, args: argparse.Namespace) -> int:
    """Copy a revision's package into the project's .archeion/designs/<slug>/. A plain copy, the
    only place a design is written outside the registry, and only where /inbox may edit (ADR 0017)."""
    manager = _sources(settings)
    p = _design_project(manager, args.project)
    if p.dir is None:
        raise ValueError(
            f"{p.id}'s folder isn't available on this machine (see: design preflight {p.id} --for handoff)"
        )
    if not p.inbox_edits:
        raise ValueError(f"Archeion's /inbox may not edit {p.id} (fix: projects inbox-edits {p.id} on)")
    ref = _design_ref(settings, p.id, args.slug)
    rev, files = dz.package_files(ref, args.revision)
    target = (p.dir / dz.PACKAGE_DIR / ref.slug).resolve()
    if not target.is_relative_to(p.dir.resolve()):
        raise ValueError("the package folder must stay inside the project")
    if target.exists():
        for old in list(target.iterdir()):
            if old.name == "receipt.md":
                continue
            if old.is_dir():
                shutil.rmtree(old)
            else:
                old.unlink()
    for name, text in files.items():
        dest = target / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
    print(f"Delivered revision {rev['number']} of '{ref.slug}' to {p.id}: {dz.PACKAGE_DIR}/{ref.slug}/")
    for name in sorted(files):
        print(f"  {name}")
    print(
        f"These files are inside {p.id}; commit them from there if wanted."
        " Next: /archeion:consume-design in its session."
    )
    return 0


def cmd_design_consumed(settings: Settings, args: argparse.Namespace) -> int:
    """The project consumed a revision (called by /archeion:consume-design): the design is handed off."""
    manager = _sources(settings)
    p = _design_project(manager, args.project)
    ref = _design_ref(settings, p.id, args.slug)
    dz.mark_consumed(ref, args.revision)
    print(f"{p.id} '{ref.slug}': revision {args.revision} consumed; stage is {ref.stage}.")
    return 0


def cmd_design_discard(settings: Settings, args: argparse.Namespace) -> int:
    manager = _sources(settings)
    ref = _design_ref(settings, _design_project(manager, args.project).id, args.slug)
    dz.delete(ref)
    print(f"Deleted the design '{ref.slug}' of {ref.project}, revisions included.")
    return 0


def _glossary_project(settings: Settings, name: str) -> None:
    if name not in _sources(settings).registry.projects:
        raise ValueError(f"'{name}' isn't a registered project (see: projects list)")


def cmd_glossary_list(settings: Settings, args: argparse.Namespace) -> int:
    _glossary_project(settings, args.project)
    terms = gl.load(settings.registry_root, args.project)
    if args.json:
        _print_json(terms)
        return 0
    for t in terms:
        aka = f" (aka {', '.join(t['aliases'])})" if t["aliases"] else ""
        print(f"{t['term']}{aka}: {t['definition']}")
    if not terms:
        print(f"No terms yet for {args.project}.")
    return 0


def cmd_glossary_set(settings: Settings, args: argparse.Namespace) -> int:
    """Add a term, or replace the one with the same name."""
    _glossary_project(settings, args.project)
    existing = {t["id"] for t in gl.load(settings.registry_root, args.project)}
    raw = {"term": args.term, "definition": args.definition, "aliases": args.alias or []}
    replace = gl.slug(args.term) if gl.slug(args.term) in existing else None
    entry = gl.upsert(settings.registry_root, args.project, raw, replace=replace)
    print(f"{'Updated' if replace else 'Added'} '{entry['term']}' in {args.project}.")
    return 0


def cmd_glossary_remove(settings: Settings, args: argparse.Namespace) -> int:
    _glossary_project(settings, args.project)
    gl.remove(settings.registry_root, args.project, gl.slug(args.term))
    print(f"Removed '{args.term}' from {args.project}.")
    return 0


def _report_project(settings: Settings, name: str) -> SourceManager:
    manager = _sources(settings)
    if name not in manager.registry.projects:
        raise ValueError(f"'{name}' isn't a registered project (see: projects list)")
    return manager


def _report_catalog(settings: Settings, name: str) -> tuple[SourceManager, list[dict]]:
    manager = _report_project(settings, name)
    return manager, rp.catalog(manager, settings.registry_root, name)


def cmd_report_preflight(settings: Settings, args: argparse.Namespace) -> int:
    manager = _report_project(settings, args.project)
    result = rp.preflight(
        manager, settings.registry_root, args.project, settings.report_browser, rr.frontend_up(settings)
    )
    if args.json:
        _print_json(result)
        return 0 if result["ok"] else 1
    print(f"{args.project}: {result['available']} of {result['sections']} sections have a source.")
    print(f"  renderer (headless Edge): {'found' if result['browser'] else 'NOT found'}")
    print(f"  viewer frontend: {'running' if result['frontend'] else 'NOT running'}")
    print(f"  latest study: {result['study'] or 'none'}")
    for u in result["unavailable"]:
        print(f"  unavailable: {u['id']} ({u['reason']})")
    for problem in result["problems"]:
        print(f"  problem: {problem}")
    return 0 if result["ok"] else 1


def cmd_report_catalog(settings: Settings, args: argparse.Namespace) -> int:
    _, entries = _report_catalog(settings, args.project)
    if args.json:
        _print_json(entries)
        return 0
    group = None
    for e in entries:
        if e["group"] != group:
            group = e["group"]
            print(rp.GROUP_TITLES[group])
        mark = " " if e["available"] else "x"
        why = "" if e["available"] else f"  ({e['reason']})"
        print(f"  [{mark}] {e['id']}: {e['title']}{why}")
    return 0


def _read_preset_file(path: str) -> object:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} isn't valid JSON: {exc}") from exc


def cmd_report_validate(settings: Settings, args: argparse.Namespace) -> int:
    _, entries = _report_catalog(settings, args.project)
    preset = rp.validate_preset(_read_preset_file(args.file), entries)
    print(f"OK: '{preset['name']}' ({preset['mode']}) holds {len(preset['sections'])} sections.")
    return 0


def cmd_report_preset_save(settings: Settings, args: argparse.Namespace) -> int:
    _, entries = _report_catalog(settings, args.project)
    preset = rp.save_preset(settings.registry_root, args.project, _read_preset_file(args.file), entries)
    print(f"Saved the preset '{preset['name']}' of {args.project}: {len(preset['sections'])} sections.")
    return 0


def cmd_report_preset_list(settings: Settings, args: argparse.Namespace) -> int:
    _report_project(settings, args.project)
    presets = rp.list_presets(settings.registry_root, args.project)
    if args.json:
        _print_json(presets)
        return 0
    for p in presets:
        print(f"{p['name']} ({p['mode']}): {len(p['sections'])} sections")
    if not presets:
        print(f"No presets yet for {args.project}.")
    return 0


def cmd_report_preset_show(settings: Settings, args: argparse.Namespace) -> int:
    _report_project(settings, args.project)
    _print_json(rp.get_preset(settings.registry_root, args.project, args.name))
    return 0


def cmd_report_preset_delete(settings: Settings, args: argparse.Namespace) -> int:
    _report_project(settings, args.project)
    rp.delete_preset(settings.registry_root, args.project, args.name)
    print(f"Deleted the preset '{args.name}' of {args.project}.")
    return 0


def cmd_report_build(settings: Settings, args: argparse.Namespace) -> int:
    manager = _report_project(settings, args.project)
    info = rr.build(settings, manager, args.project, args.preset)
    print(
        f"Built {info['file']}: {info['pages']} pages, {info['sections']} sections, "
        f"{info['failed']} failed diagrams."
    )
    check = rr.verify(settings.registry_root, args.project, info["file"])
    for problem in check["problems"]:
        print(f"  problem: {problem}")
    return 0 if check["ok"] else 1


def cmd_report_list(settings: Settings, args: argparse.Namespace) -> int:
    _report_project(settings, args.project)
    rows = rr.list_reports(settings.registry_root, args.project)
    if args.json:
        _print_json(rows)
        return 0
    for r in rows:
        print(f"{r['file']}: {r.get('pages', '?')} pages, {r.get('mode', '?')}, built {r.get('built', '?')}")
    if not rows:
        print(f"No reports built yet for {args.project}.")
    return 0


def cmd_report_verify(settings: Settings, args: argparse.Namespace) -> int:
    _report_project(settings, args.project)
    result = rr.verify(settings.registry_root, args.project, args.file)
    if args.json:
        _print_json(result)
    else:
        print(f"{result['file']}: {result['pages']} pages, {result['bytes']} bytes")
        for problem in result["problems"]:
            print(f"  problem: {problem}")
        if result["ok"]:
            print("  OK")
    return 0 if result["ok"] else 1


def cmd_report_read(settings: Settings, args: argparse.Namespace) -> int:
    """The content of catalog sections, for planning and writing a guided report."""
    manager = _report_project(settings, args.project)
    sections = rp.read_sections(manager, settings.registry_root, args.project, args.ids)
    for s in sections:
        text = s.get("markdown")
        if isinstance(text, str) and len(text) > args.limit:
            cut = len(text) - args.limit
            s["markdown"] = text[: args.limit] + "\n\n[truncated: " + str(cut) + " more characters]"
    _print_json(sections)
    return 0


def cmd_report_plan_save(settings: Settings, args: argparse.Namespace) -> int:
    _, entries = _report_catalog(settings, args.project)
    data = rp.save_plan(
        settings.registry_root, args.project, _read_preset_file(args.file), entries, thread=args.thread
    )
    plan = data["plan"]
    authored = sum(1 for s in plan["sections"] if s["id"].startswith(rp.AUTHORED_PREFIX))
    print(
        f"Saved the plan of {args.project}: {len(plan['sections'])} sections ({authored} written by Claude)"
        + (f", thread #{data['thread']}." if data["thread"] else ".")
    )
    return 0


def cmd_report_plan_show(settings: Settings, args: argparse.Namespace) -> int:
    _report_project(settings, args.project)
    data = rp.get_plan(settings.registry_root, args.project)
    if data is None:
        print(f"No plan in progress for {args.project}.")
        return 1
    if args.json:
        _print_json(data)
        return 0
    plan = data["plan"]
    print(
        f"Plan '{plan['name']}' for {args.project} "
        f"(updated {data['updated']}, thread {data['thread'] or 'none'})"
    )
    print(f"  prompt: {plan.get('prompt') or '-'}")
    print(f"  outline: {plan.get('outline') or '-'}")
    for i, s in enumerate(plan["sections"], 1):
        label = f"authored: {s['title']}" if s["id"].startswith(rp.AUTHORED_PREFIX) else s["id"]
        print(f"  {i}. {label}")
    return 0


def cmd_report_plan_discard(settings: Settings, args: argparse.Namespace) -> int:
    _report_project(settings, args.project)
    print(
        "Discarded the plan."
        if rp.discard_plan(settings.registry_root, args.project)
        else "No plan to discard."
    )
    return 0


def cmd_report_plan_approve(settings: Settings, args: argparse.Namespace) -> int:
    """Turns the plan into a saved preset (the user approves it in the viewer; this is for a terminal)."""
    _, entries = _report_catalog(settings, args.project)
    preset = rp.approve_plan(settings.registry_root, args.project, entries)
    print(
        f"Approved: saved the preset '{preset['name']}'. "
        f"Build it with: report build {args.project} --preset {preset['name']}"
    )
    return 0


def cmd_report_default(settings: Settings, args: argparse.Namespace) -> int:
    """A starting standard preset: every available section, in catalog order."""
    _, entries = _report_catalog(settings, args.project)
    _print_json(
        {
            "name": args.name,
            "mode": "standard",
            "title": "",
            "options": rp.DEFAULT_OPTIONS,
            "sections": [{"id": i} for i in rp.default_sections(entries)],
        }
    )
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
    show = inbox.add_parser("show", help="an item with its whole conversation and doc excerpt")
    show.add_argument("id", type=int)
    show.add_argument("--json", action="store_true")
    show.set_defaults(func=cmd_inbox_show)
    for name, func, text in (
        ("claim", cmd_inbox_claim, "open -> in_progress"),
        ("release", cmd_inbox_release, "in_progress -> open"),
    ):
        p = inbox.add_parser(name, help=text)
        p.add_argument("id", type=int)
        p.add_argument("--json", action="store_true", help="print the ids and the state as JSON")
        p.set_defaults(func=func)
    rep = inbox.add_parser("reply", help="answer an in-progress item (in_progress -> answered)")
    rep.add_argument("id", type=int)
    rep.add_argument("--file", required=True, help="UTF-8 file with the reply (Markdown), or - for stdin")
    rep.add_argument("--json", action="store_true", help="print the ids and the state as JSON")
    rep.set_defaults(func=cmd_inbox_reply)
    new = inbox.add_parser(
        "create", help="a new item from this session, or with --in the next message in a thread (open)"
    )
    new.add_argument("--to", help="the project a new thread is for (default: archeion)")
    new.add_argument(
        "--in", dest="thread", type=int, metavar="ID", help="add to the thread this item is in (ADR 0018)"
    )
    new.add_argument("--kind", choices=fb.KINDS, help="default: prompt, or the thread's kind with --in")
    new.add_argument(
        "--claim", action="store_true", help="with --in: add it already claimed, to answer it in this session"
    )
    new.add_argument("--file", required=True, help="UTF-8 file with the text (Markdown), or - for stdin")
    new.add_argument("--json", action="store_true", help="print the new item's ids and state as JSON")
    new.set_defaults(func=cmd_inbox_create)
    res = inbox.add_parser("resolve", help="resolve the whole thread an item is in")
    res.add_argument("id", type=int)
    res.add_argument("--json", action="store_true", help="print the ids and the state as JSON")
    res.set_defaults(func=cmd_inbox_resolve)
    th = inbox.add_parser("threads", help="conversations, one row per thread, latest change first")
    th.add_argument("--status", default="active", choices=["active", *fb.STATUSES, "all"])
    th.add_argument("--from-here", action="store_true", help="only threads the project this runs in started")
    th.add_argument("--limit", type=int, default=20)
    th.add_argument("--json", action="store_true")
    _target_args(th)
    th.set_defaults(func=cmd_inbox_threads)

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
    pt = projects.add_parser("type", help="mark a page as a project or a module, or back to auto (ADR 0016)")
    pt.add_argument("name", help="the registered name")
    pt.add_argument("type", choices=["project", "module", "auto"], help="auto: detected from the folder")
    pt.set_defaults(func=cmd_projects_type)
    pe = projects.add_parser(
        "inbox-edits", help="allow Archeion's /inbox to edit a project's files for its items (ADR 0017)"
    )
    pe.add_argument("name", help="the registered name")
    pe.add_argument("value", choices=["on", "off", "auto"], help="auto: on, or a module's project's setting")
    pe.set_defaults(func=cmd_projects_inbox_edits)
    pr = projects.add_parser(
        "remove", help="take a project out of the registry; its page moves to registry/removed/ (ADR 0026)"
    )
    pr.add_argument("name", help="the registered name")
    pr.set_defaults(func=cmd_projects_remove)
    projects.add_parser("removed", help="projects removed and not registered since (ADR 0026)").set_defaults(
        func=cmd_projects_removed
    )
    prs = projects.add_parser("restore", help="put a removed project back in the registry (ADR 0026)")
    prs.add_argument("name", help="the removed project's name")
    prs.set_defaults(func=cmd_projects_restore)
    ppg = projects.add_parser(
        "purge", help="delete a removed project and what the registry kept for it, for good (ADR 0026)"
    )
    ppg.add_argument("name", help="the removed project's name")
    ppg.add_argument("--yes", action="store_true", help="confirm: this can't be undone")
    ppg.set_defaults(func=cmd_projects_purge)
    ports = projects.add_parser("ports", help="the ports recorded in the registry, by project")
    ports.add_argument("--json", action="store_true")
    ports.set_defaults(func=cmd_projects_ports)

    study = sub.add_parser("study", help="code studies of registered projects (ADR 0019)").add_subparsers(
        dest="action", required=True
    )
    ss = study.add_parser("scan", help="a read-only inventory of a project's code")
    ss.add_argument("project")
    ss.add_argument("--json", action="store_true")
    ss.add_argument("--out", help="also write the full inventory (JSON) to this file")
    ss.set_defaults(func=cmd_study_scan)
    sv = study.add_parser("validate", help="check a study model (study.json) without saving it")
    sv.add_argument("--file", required=True, help="the model, or - for stdin")
    sv.set_defaults(func=cmd_study_validate)
    sa = study.add_parser("save", help="validate a study and store it as a new snapshot")
    sa.add_argument("project")
    sa.add_argument("--file", help="the model (study.json), or - for stdin")
    sa.add_argument("--notes", help="the narrative (Markdown) to keep with it")
    sa.add_argument("--from-draft", action="store_true", help="save the project's draft instead (ADR 0020)")
    sa.set_defaults(func=cmd_study_save)
    draft = study.add_parser(
        "draft", help="the study in progress, between conversation rounds"
    ).add_subparsers(dest="draft_action", required=True)
    ds = draft.add_parser("save", help="validate a model and keep it as the project's draft")
    ds.add_argument("project")
    ds.add_argument("--file", required=True, help="the model (study.json), or - for stdin")
    ds.add_argument("--notes", help="the narrative so far (kept from the last draft when left out)")
    ds.add_argument("--thread", type=int, help="the feedback thread the study is discussed in")
    ds.set_defaults(func=cmd_study_draft_save)
    dsh = draft.add_parser("show", help="the project's draft")
    dsh.add_argument("project")
    dsh.add_argument("--json", action="store_true")
    dsh.set_defaults(func=cmd_study_draft_show)
    dd = draft.add_parser("discard", help="drop the project's draft")
    dd.add_argument("project")
    dd.set_defaults(func=cmd_study_draft_discard)
    sl = study.add_parser("list", help="a project's snapshots, or every project's latest")
    sl.add_argument("project", nargs="?")
    sl.add_argument("--json", action="store_true")
    sl.set_defaults(func=cmd_study_list)
    sh = study.add_parser("show", help="one snapshot: counts, problems and where it is")
    sh.add_argument("project")
    sh.add_argument("snapshot", nargs="?", default="latest")
    sh.add_argument("--json", action="store_true")
    sh.set_defaults(func=cmd_study_show)
    sc = study.add_parser("changes", help="files changed since the latest snapshot (for --refresh)")
    sc.add_argument("project")
    sc.add_argument("--json", action="store_true")
    sc.set_defaults(func=cmd_study_changes)

    design = sub.add_parser("design", help="design and plan a project (ADR 0022)").add_subparsers(
        dest="action", required=True
    )

    def design_cmd(name: str, help_: str, func, *, slug: bool = True):
        d = design.add_parser(name, help=help_)
        d.add_argument("project")
        if slug:
            d.add_argument("--slug", default=dz.DEFAULT_SLUG, help="which design of the project")
        d.set_defaults(func=func)
        return d

    dp = design_cmd(
        "preflight", "what stands in the way of a design step, with the fix", cmd_design_preflight
    )
    dp.add_argument("--for", dest="purpose", choices=["design", "handoff"], default="design")
    dp.add_argument("--json", action="store_true")
    dc = design_cmd(
        "context", "the project, its neighbours, ports in use and the rules", cmd_design_context, slug=False
    )
    dc.add_argument("--json", action="store_true")
    dl = design.add_parser("list", help="designs, of one project or all")
    dl.add_argument("project", nargs="?")
    dl.add_argument("--json", action="store_true")
    dl.set_defaults(func=cmd_design_list)
    di = design_cmd("init", "start a design", cmd_design_init)
    di.add_argument("--thread", type=int, help="the feedback thread it's discussed in")
    di.add_argument("--summary", help="one line on what it is")
    dsw = design_cmd("show", "a design's state, files and problems", cmd_design_show)
    dsw.add_argument("--revision", help="a frozen revision (a number, or latest) instead of the working copy")
    dsw.add_argument("--json", action="store_true")
    dv = design_cmd("validate", "check a work folder without saving it", cmd_design_validate, slug=False)
    dv.add_argument("--dir", required=True, help="the folder with the design's files and model.json")
    dsa = design_cmd("save", "replace the working copy with a work folder's files", cmd_design_save)
    dsa.add_argument("--dir", required=True)
    dsa.add_argument("--thread", type=int)
    dst = design_cmd("stage", "move a design to brief, architecture or plan", cmd_design_stage)
    dst.add_argument("stage", choices=list(dz.MOVABLE))
    da = design_cmd(
        "approve", "freeze a revision and update the registry page (needs --yes)", cmd_design_approve
    )
    da.add_argument("--yes", action="store_true", help="do it; without it, only show what would change")
    da.add_argument("--no-registry", action="store_true", help="leave the registry page alone")
    dh = design_cmd("handoff", "ask /inbox to deliver a revision to the project", cmd_design_handoff)
    dh.add_argument("--revision", default="latest")
    dh.add_argument("--json", action="store_true")
    dpk = design_cmd(
        "package", "copy a revision into the project's .archeion/designs/ (for /inbox)", cmd_design_package
    )
    dpk.add_argument("--revision", default="latest")
    dco = design_cmd(
        "consumed",
        "record that the project consumed a revision (for /archeion:consume-design)",
        cmd_design_consumed,
    )
    dco.add_argument("--revision", type=int, required=True)
    design_cmd("discard", "delete a design and its revisions", cmd_design_discard)

    glossary = sub.add_parser("glossary", help="a project's terms and jargon (ADR 0023)").add_subparsers(
        dest="action", required=True
    )
    gls = glossary.add_parser("list", help="a project's terms")
    gls.add_argument("project")
    gls.add_argument("--json", action="store_true")
    gls.set_defaults(func=cmd_glossary_list)
    gst = glossary.add_parser("set", help="add a term, or replace the one with the same name")
    gst.add_argument("project")
    gst.add_argument("term")
    gst.add_argument("definition")
    gst.add_argument("--alias", action="append", help="another name for it (repeatable)")
    gst.set_defaults(func=cmd_glossary_set)
    grm = glossary.add_parser("remove", help="remove a term")
    grm.add_argument("project")
    grm.add_argument("term")
    grm.set_defaults(func=cmd_glossary_remove)

    report = sub.add_parser("report", help="PDF reports of a project (ADR 0025)").add_subparsers(
        dest="action", required=True
    )
    rpf = report.add_parser("preflight", help="what a report of the project can use, and what is missing")
    rpf.add_argument("project")
    rpf.add_argument("--json", action="store_true")
    rpf.set_defaults(func=cmd_report_preflight)
    rct = report.add_parser("catalog", help="every section a report of the project can hold")
    rct.add_argument("project")
    rct.add_argument("--json", action="store_true")
    rct.set_defaults(func=cmd_report_catalog)
    rdf = report.add_parser("default", help="print a starting standard preset (every available section)")
    rdf.add_argument("project")
    rdf.add_argument("--name", default="full")
    rdf.set_defaults(func=cmd_report_default)
    rbd = report.add_parser("build", help="build a saved preset into a PDF (needs the viewer running)")
    rbd.add_argument("project")
    rbd.add_argument("--preset", required=True)
    rbd.set_defaults(func=cmd_report_build)
    rls = report.add_parser("list", help="the PDFs built for a project")
    rls.add_argument("project")
    rls.add_argument("--json", action="store_true")
    rls.set_defaults(func=cmd_report_list)
    rvf = report.add_parser("verify", help="check a built PDF against its build record")
    rvf.add_argument("project")
    rvf.add_argument("file")
    rvf.add_argument("--json", action="store_true")
    rvf.set_defaults(func=cmd_report_verify)
    rrd = report.add_parser("read", help="read catalog sections (JSON), to plan and write a guided report")
    rrd.add_argument("project")
    rrd.add_argument("ids", nargs="+")
    rrd.add_argument("--limit", type=int, default=12000, help="characters of Markdown to show per section")
    rrd.set_defaults(func=cmd_report_read)
    plan = report.add_parser("plan", help="the guided report in progress").add_subparsers(
        dest="plan_action", required=True
    )
    pls = plan.add_parser("save", help="validate a plan file and keep it as the project's draft")
    pls.add_argument("project")
    pls.add_argument("--file", required=True)
    pls.add_argument("--thread", type=int, help="the inbox thread this plan belongs to")
    pls.set_defaults(func=cmd_report_plan_save)
    plw = plan.add_parser("show", help="the draft plan")
    plw.add_argument("project")
    plw.add_argument("--json", action="store_true")
    plw.set_defaults(func=cmd_report_plan_show)
    pld = plan.add_parser("discard", help="drop the draft plan")
    pld.add_argument("project")
    pld.set_defaults(func=cmd_report_plan_discard)
    pla = plan.add_parser(
        "approve", help="turn the draft into a saved preset (the user approves, not Claude)"
    )
    pla.add_argument("project")
    pla.set_defaults(func=cmd_report_plan_approve)
    rva = report.add_parser("validate", help="check a preset file against the catalog without saving it")
    rva.add_argument("project")
    rva.add_argument("--file", required=True)
    rva.set_defaults(func=cmd_report_validate)
    preset = report.add_parser("preset", help="saved presets of a project").add_subparsers(
        dest="preset_action", required=True
    )
    rpl = preset.add_parser("list", help="a project's presets")
    rpl.add_argument("project")
    rpl.add_argument("--json", action="store_true")
    rpl.set_defaults(func=cmd_report_preset_list)
    rps = preset.add_parser("show", help="one preset, as JSON")
    rps.add_argument("project")
    rps.add_argument("name")
    rps.set_defaults(func=cmd_report_preset_show)
    rpv = preset.add_parser("save", help="validate a preset file and store it")
    rpv.add_argument("project")
    rpv.add_argument("--file", required=True)
    rpv.set_defaults(func=cmd_report_preset_save)
    rpd = preset.add_parser("delete", help="delete a preset")
    rpd.add_argument("project")
    rpd.add_argument("name")
    rpd.set_defaults(func=cmd_report_preset_delete)

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
    except rp.PresetNotFound as exc:
        print(f"No preset '{exc.args[0]}'. See: report preset list", file=sys.stderr)
        return 1
    except gl.TermNotFound as exc:
        print(f"No term '{exc.args[0]}'. See: glossary list", file=sys.stderr)
        return 1
    except st.StudyNotFound as exc:
        print(f"No study snapshot '{exc.args[0]}'. See: study list", file=sys.stderr)
        return 1
    except dz.DesignNotFound as exc:
        print(f"No design {exc.args[0]}. See: design list", file=sys.stderr)
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
