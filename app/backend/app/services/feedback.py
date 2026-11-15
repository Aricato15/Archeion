"""Feedback threads: prompts, reviews and comments that reach Claude through /inbox.

A thread (ADR 0018) is a root item plus the follow-ups written after Claude answered.
Every item records its thread's root id in `thread_id`. Claude works item by item, while
the user sees threads:

- An item's status flow: open -> in_progress (claim) -> answered (reply) -> resolved,
  with release (in_progress -> open). Every transition is one conditional UPDATE, so two
  claims of the same item can't both succeed. An answered item is never sent back to
  open, so a reply is never overwritten.
- A thread's status is its latest item's status. At most one item per thread waits for
  Claude (open or in progress), and it's always the latest: a follow-up is refused while
  one waits, and a follow-up to a resolved thread reopens it.
- Reopening a thread adds a follow-up (REOPENED, unless you write your own).
- Resolving resolves the whole thread, so does dismissing an open one.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from ..db import iso, utcnow, write_tx

KINDS = ("prompt", "review", "comment")
STATUSES = ("open", "in_progress", "answered", "resolved")
WAITING = ("open", "in_progress")

# (from, to) pairs a PATCH may request on a thread's latest item. Claim and reply have
# their own calls, "resolved" applies to the whole thread (resolve_thread) and reopening
# adds a message (reopen).
PATCH_TRANSITIONS = {
    ("in_progress", "open"),  # release
}

# The message a plain "Reopen thread" adds.
REOPENED = "Reopened: please take another look at your last answer."


class FeedbackNotFound(LookupError):
    pass


class FeedbackConflict(RuntimeError):
    """The item exists but isn't in a state that allows this action."""


def _row(r: sqlite3.Row) -> dict[str, Any]:
    d = dict(r)
    d["anchor"] = json.loads(d["anchor"]) if d["anchor"] else None
    return d


def get(conn: sqlite3.Connection, item_id: int) -> dict[str, Any]:
    r = conn.execute("SELECT * FROM feedback WHERE id = ?", (item_id,)).fetchone()
    if r is None:
        raise FeedbackNotFound(item_id)
    return _row(r)


def _status_of(conn: sqlite3.Connection, item_id: int) -> str:
    r = conn.execute("SELECT status FROM feedback WHERE id = ?", (item_id,)).fetchone()
    if r is None:
        raise FeedbackNotFound(item_id)
    return r["status"]


def _thread_id(conn: sqlite3.Connection, item_id: int) -> int:
    r = conn.execute("SELECT thread_id FROM feedback WHERE id = ?", (item_id,)).fetchone()
    if r is None:
        raise FeedbackNotFound(item_id)
    return r["thread_id"]


def _latest(conn: sqlite3.Connection, thread_id: int) -> sqlite3.Row:
    return conn.execute(
        "SELECT id, status FROM feedback WHERE thread_id = ? ORDER BY id DESC LIMIT 1", (thread_id,)
    ).fetchone()


def root(conn: sqlite3.Connection, item_id: int) -> dict[str, Any]:
    """The first item of the thread an item belongs to."""
    return get(conn, _thread_id(conn, item_id))


def create(
    conn: sqlite3.Connection,
    *,
    kind: str,
    body: str,
    doc_path: str | None = None,
    anchor: dict | None = None,
    parent_id: int | None = None,
    doc_rev: str | None = None,
    source: str = "archeion",
    origin: str | None = None,
) -> dict:
    """A new thread, or with parent_id a follow-up in that item's thread.

    A follow-up always goes after the thread's latest item, whichever item it names, and is
    refused while an earlier one still waits for Claude: edit that one instead.
    """
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    now = iso(utcnow())
    with write_tx(conn):
        thread_id = None
        if parent_id is not None:
            thread_id = _thread_id(conn, parent_id)
            latest = _latest(conn, thread_id)
            if latest["status"] in WAITING:
                raise FeedbackConflict(
                    f"#{latest['id']} in this thread still waits for Claude ({latest['status']});"
                    " edit it instead, or wait for the answer"
                )
            parent_id = latest["id"]
        cur = conn.execute(
            "INSERT INTO feedback"
            " (kind, source, origin, doc_path, anchor, body, parent_id, thread_id, doc_rev,"
            " created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                kind,
                source,
                origin,
                doc_path,
                json.dumps(anchor) if anchor else None,
                body,
                parent_id,
                thread_id,
                doc_rev,
                now,
                now,
            ),
        )
        item_id = cur.lastrowid
        assert item_id is not None
        if thread_id is None:
            conn.execute("UPDATE feedback SET thread_id = id WHERE id = ?", (item_id,))
    return get(conn, item_id)


def _sources_sql(source: str | list[str] | None, column: str, args: list[Any]) -> str:
    if not source:
        return ""
    wanted = [source] if isinstance(source, str) else source
    args.extend(wanted)
    return f" AND {column} IN ({','.join('?' * len(wanted))})"


def list_items(
    conn: sqlite3.Connection,
    *,
    status: str | None = None,
    doc_path: str | None = None,
    kind: str | None = None,
    source: str | list[str] | None = None,
    limit: int = 500,
) -> list[dict]:
    """Single items, newest first: Claude's work queue (the inbox CLI)."""
    sql = "SELECT * FROM feedback WHERE 1=1"
    args: list[Any] = []
    if status:
        sql += " AND status = ?"
        args.append(status)
    if doc_path:
        sql += " AND doc_path = ?"
        args.append(doc_path)
    sql += _sources_sql(source, "source", args)
    if kind:
        sql += " AND kind = ?"
        args.append(kind)
    sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
    args.append(limit)
    return [_row(r) for r in conn.execute(sql, args).fetchall()]


# One row per thread: its root, its latest item, its size and its last change.
_THREADS = """
    WITH t AS (
      SELECT thread_id, max(id) AS latest_id, count(*) AS messages, max(updated_at) AS touched
      FROM feedback GROUP BY thread_id
    )
    SELECT r.*, l.status AS thread_status, t.latest_id, t.messages, t.touched,
      (SELECT x.reply FROM feedback x
        WHERE x.thread_id = t.thread_id AND x.reply IS NOT NULL ORDER BY x.id DESC LIMIT 1) AS last_reply,
      (SELECT x.answered_at FROM feedback x
        WHERE x.thread_id = t.thread_id AND x.reply IS NOT NULL ORDER BY x.id DESC LIMIT 1) AS last_answered
    FROM t JOIN feedback r ON r.id = t.thread_id JOIN feedback l ON l.id = t.latest_id
    WHERE 1=1
"""


def list_threads(
    conn: sqlite3.Connection,
    *,
    status: str | None = None,
    doc_path: str | None = None,
    kind: str | None = None,
    source: str | list[str] | None = None,
    limit: int = 500,
) -> list[dict]:
    """Threads, most recently changed first: what the viewer lists.

    Each row is the thread's root (its request, doc and anchor) with the thread's status,
    latest reply, message count and last change in place of the root's own.
    """
    sql = _THREADS
    args: list[Any] = []
    if status:
        sql += " AND l.status = ?"
        args.append(status)
    if doc_path:
        sql += " AND r.doc_path = ?"
        args.append(doc_path)
    sql += _sources_sql(source, "r.source", args)
    if kind:
        sql += " AND r.kind = ?"
        args.append(kind)
    sql += " ORDER BY t.touched DESC, t.latest_id DESC LIMIT ?"
    args.append(limit)
    out = []
    for r in conn.execute(sql, args).fetchall():
        d = _row(r)
        d["status"] = d.pop("thread_status")
        d["updated_at"] = d.pop("touched")
        d["reply"] = d.pop("last_reply")
        d["answered_at"] = d.pop("last_answered")
        out.append(d)
    return out


def summary(conn: sqlite3.Connection, source: str | list[str] | None = None) -> dict[str, int]:
    """Threads per status (a thread's status is its latest item's)."""
    counts = dict.fromkeys(STATUSES, 0)
    args: list[Any] = []
    sql = (
        "SELECT l.status, count(*) AS n FROM feedback l"
        " WHERE l.id = (SELECT max(id) FROM feedback x WHERE x.thread_id = l.thread_id)"
        + _sources_sql(source, "l.source", args)
        + " GROUP BY l.status"
    )
    for r in conn.execute(sql, args):
        counts[r["status"]] = r["n"]
    return counts


def open_by_source(conn: sqlite3.Connection) -> dict[str, int]:
    """Threads waiting for Claude (open or in progress), per source."""
    rows = conn.execute(
        "SELECT source, count(DISTINCT thread_id) AS n FROM feedback"
        " WHERE status IN ('open','in_progress') GROUP BY source"
    )
    return {r["source"]: r["n"] for r in rows}


def thread(conn: sqlite3.Connection, item_id: int) -> list[dict]:
    """The whole conversation an item belongs to: its root and every follow-up, oldest first."""
    rows = conn.execute(
        "SELECT * FROM feedback WHERE thread_id = ? ORDER BY id", (_thread_id(conn, item_id),)
    ).fetchall()
    return [_row(r) for r in rows]


def _transition(conn: sqlite3.Connection, item_id: int, frm: str, to: str, extra: dict | None = None) -> dict:
    now = iso(utcnow())
    sets = {"status": to, "updated_at": now, **(extra or {})}
    assignments = ", ".join(f"{k} = ?" for k in sets)
    with write_tx(conn):
        cur = conn.execute(
            f"UPDATE feedback SET {assignments} WHERE id = ? AND status = ?",
            (*sets.values(), item_id, frm),
        )
        if cur.rowcount == 0:
            status = _status_of(conn, item_id)
            raise FeedbackConflict(f"item {item_id} is {status}, expected {frm}")
    return get(conn, item_id)


def claim(conn: sqlite3.Connection, item_id: int) -> dict:
    return _transition(conn, item_id, "open", "in_progress", {"claimed_at": iso(utcnow())})


def reply(conn: sqlite3.Connection, item_id: int, text: str) -> dict:
    if not text.strip():
        raise ValueError("the reply is empty")
    return _transition(
        conn, item_id, "in_progress", "answered", {"reply": text, "answered_at": iso(utcnow())}
    )


def release(conn: sqlite3.Connection, item_id: int) -> dict:
    return _transition(conn, item_id, "in_progress", "open", {"claimed_at": None})


def resolve_thread(conn: sqlite3.Connection, item_id: int) -> dict:
    """Resolve the whole thread an item belongs to (an open item in it is dismissed).

    Refused while Claude is working on it: release the claim first.
    """
    with write_tx(conn):
        thread_id = _thread_id(conn, item_id)
        busy = conn.execute(
            "SELECT id FROM feedback WHERE thread_id = ? AND status = 'in_progress'", (thread_id,)
        ).fetchone()
        if busy is not None:
            raise FeedbackConflict(f"Claude is working on #{busy['id']}; release the claim first")
        conn.execute(
            "UPDATE feedback SET status = 'resolved', claimed_at = NULL, updated_at = ?"
            " WHERE thread_id = ? AND status IN ('open', 'answered')",
            (iso(utcnow()), thread_id),
        )
    return get(conn, item_id)


def reopen(
    conn: sqlite3.Connection, item_id: int, body: str | None = None, doc_rev: str | None = None
) -> dict:
    """Send a thread back to Claude: a new message after its latest one, with the thread's kind,
    project and doc. The earlier answers stay as they are, so the conversation keeps them."""
    first = root(conn, item_id)
    return create(
        conn,
        kind=first["kind"],
        body=(body or "").strip() or REOPENED,
        doc_path=first["doc_path"],
        parent_id=item_id,
        doc_rev=doc_rev,
        source=first["source"],
    )


def set_status(conn: sqlite3.Connection, item_id: int, to: str) -> dict:
    if to == "resolved":
        return resolve_thread(conn, item_id)
    current = _status_of(conn, item_id)
    if (current, to) not in PATCH_TRANSITIONS:
        raise FeedbackConflict(f"can't change {current} to {to}")
    latest = _latest(conn, _thread_id(conn, item_id))
    if latest["id"] != item_id:
        raise FeedbackConflict(f"only the thread's latest item (#{latest['id']}) can change status")
    extra = {"claimed_at": None} if to == "open" else None
    return _transition(conn, item_id, current, to, extra)


def edit_body(conn: sqlite3.Connection, item_id: int, body: str) -> dict:
    with write_tx(conn):
        cur = conn.execute(
            "UPDATE feedback SET body = ?, updated_at = ? WHERE id = ? AND status = 'open'",
            (body, iso(utcnow()), item_id),
        )
        if cur.rowcount == 0:
            raise FeedbackConflict(
                f"item {item_id} is {_status_of(conn, item_id)}; only open items can be edited"
            )
    return get(conn, item_id)


def delete(conn: sqlite3.Connection, item_id: int) -> None:
    """Delete an open item: a whole new thread, or the follow-up that's still waiting."""
    with write_tx(conn):
        cur = conn.execute(
            "DELETE FROM feedback WHERE id = ? AND status = 'open'"
            " AND NOT EXISTS (SELECT 1 FROM feedback c WHERE c.thread_id = ? AND c.id > ?)",
            (item_id, item_id, item_id),
        )
        if cur.rowcount == 0:
            status = _status_of(conn, item_id)
            reason = "only open items" if status != "open" else "only the thread's latest item"
            raise FeedbackConflict(f"item {item_id} is {status}; {reason} can be deleted")


# --- the conversation, as Claude reads it ---------------------------------------------


def _where(item: dict) -> str:
    where = item["doc_path"] or "no specific doc"
    if item.get("source", "archeion") != "archeion":
        where = f"{where} in {item['source']}"
    anchor = item["anchor"] or {}
    if anchor.get("heading"):
        where += f", section '{anchor['heading']}'"
    if anchor.get("lines"):
        where += f", lines {anchor['lines'][0]}-{anchor['lines'][1]}"
    return where


def conversation(items: list[dict], item_id: int) -> str:
    """The thread as one Markdown text, for the inbox: what was asked and answered so far, in
    full and in order, then the message to work on now. Built when it's read, never stored, so
    an edit to any message shows up in it."""
    if not items:
        return ""
    first = items[0]
    lines = [f"# Thread #{first['id']}: {first['kind']} about {_where(first)}"]
    quote = (first["anchor"] or {}).get("quote")
    if quote:
        lines += ["", "Quoted text:", "", *(f"> {q}" for q in quote.splitlines())]
    for n, it in enumerate(items, 1):
        current = it["id"] == item_id
        label = "Your request now" if current else f"Message {n}"
        lines += ["", f"## {label} (#{it['id']}, {it['created_at']}, {it['status']})", "", it["body"].strip()]
        if it["anchor"] and it is not first:
            lines += ["", f"(about {_where(it)})"]
        if it["reply"]:
            lines += ["", f"### Claude replied ({it['answered_at'] or '-'})", "", it["reply"].strip()]
    return "\n".join(lines) + "\n"
