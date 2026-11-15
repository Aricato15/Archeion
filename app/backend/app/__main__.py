"""Command line: python -m app <serve | password ... | inbox ...> (run from app/backend/).

The inbox commands are how an interactive Claude Code session (/inbox) reads and answers
feedback. They work on the backend's own database on this machine, so no API token exists.
"""

from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path

from .config import Settings
from .db import Database
from .paths import DocNotFound, DocPathError, resolve_doc_path
from .security import MIN_PW_LEN, clear_sessions, pw_is_set, set_pw
from .services import docs_fs
from .services import feedback as fb

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


def _summary_line(item: dict) -> str:
    where = item["doc_path"] or "(general)"
    anchor = item["anchor"] or {}
    if anchor.get("heading"):
        where += f" > {anchor['heading']}"
    if anchor.get("lines"):
        where += f" (lines {anchor['lines'][0]}-{anchor['lines'][1]})"
    first = item["body"].strip().splitlines()[0] if item["body"].strip() else ""
    if len(first) > 80:
        first = first[:77] + "..."
    parent = f" follow-up of #{item['parent_id']}" if item["parent_id"] else ""
    return f"#{item['id']:<4} {item['status']:<11} {item['kind']:<7} {where}{parent}\n       {first}"


def cmd_inbox_list(settings: Settings, args: argparse.Namespace) -> int:
    status = None if args.status == "all" else args.status
    with _db(settings).conn() as conn:
        items = fb.list_items(conn, status=status)
    items.reverse()  # oldest first: the order to work in
    if args.json:
        _print_json(items)
    elif not items:
        print(f"No {args.status} feedback items.")
    else:
        for item in items:
            print(_summary_line(item))
    return 0


def cmd_inbox_count(settings: Settings, _: argparse.Namespace) -> int:
    with _db(settings).conn() as conn:
        print(fb.summary(conn)["open"])
    return 0


def _doc_excerpt(settings: Settings, item: dict) -> str:
    if not item["doc_path"]:
        return ""
    try:
        target = resolve_doc_path(settings.docs_root, item["doc_path"], allowed={".md"})
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
        print(f"\nDoc excerpt (docs/{item['doc_path']}):")
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


def cmd_inbox_reply(settings: Settings, args: argparse.Namespace) -> int:
    if args.file == "-":
        text = sys.stdin.buffer.read().decode("utf-8")
    else:
        text = Path(args.file).read_text(encoding="utf-8")
    with _db(settings).conn() as conn:
        item = fb.reply(conn, args.id, text.strip())
    print(f"Replied to #{item['id']}; it's now answered.")
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
    ls.set_defaults(func=cmd_inbox_list)
    inbox.add_parser("count", help="number of open items").set_defaults(func=cmd_inbox_count)
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
    return parser


def main(argv: list[str] | None = None, settings: Settings | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    try:
        return args.func(settings or Settings(), args)
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
