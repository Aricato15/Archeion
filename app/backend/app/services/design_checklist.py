"""The checklist of a design (ADR 0029): the features, ideas and decisions agreed for a project,
kept as `checklist.json` next to the design's model.

Nothing changes an item directly. Claude and the user *stage* changes (`pending`); the user
accepts or rejects each, comments on them, and confirms. `confirm` applies the accepted ones
at once and writes the history. This module is the only writer of the file (atomic replace).
"""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, ValidationError

from . import designs as dz
from . import studies as st

VERSION = 1
KINDS = ("feature", "idea", "decision", "task", "question")
STATUSES = ("idea", "decided", "doing", "done", "dropped")
PRIORITIES = ("high", "medium", "low")
EDITABLE = ("title", "note", "kind", "status", "phase", "priority", "refs", "depends_on")

MAX_ITEMS = 500
MAX_PENDING = 200
MAX_LOG = 300
MAX_BYTES = 400_000

_ITEM_ID = r"^c\d{1,5}$"
ItemId = Annotated[str, Field(pattern=_ITEM_ID)]
Kind = Literal["feature", "idea", "decision", "task", "question"]
Status = Literal["idea", "decided", "doing", "done", "dropped"]
Priority = Literal["high", "medium", "low"]
By = Literal["claude", "user"]


class ChecklistError(dz.DesignError):
    """A change that doesn't validate."""


class HistoryEntry(st._Strict):
    at: str
    by: By
    change: str = Field(max_length=300)
    reason: str = Field("", max_length=1000)


class Item(st._Strict):
    id: ItemId
    title: str = Field(min_length=1, max_length=200)
    note: str = Field("", max_length=2000)
    kind: Kind = "feature"
    status: Status = "idea"
    phase: str | None = Field(None, max_length=80)
    priority: Priority | None = None
    refs: list[Annotated[str, Field(max_length=120)]] = Field([], max_length=10)
    depends_on: list[ItemId] = Field([], max_length=20)
    history: list[HistoryEntry] = Field([], max_length=100)


class Comment(st._Strict):
    at: str
    by: By
    text: str = Field(min_length=1, max_length=2000)


class Change(st._Strict):
    """A staged change. `item` is an existing id for update/remove; an add gets its id on
    confirm."""

    id: str = Field(pattern=r"^p\d{1,5}$")
    op: Literal["add", "update", "remove"]
    item: ItemId | None = None
    fields: dict = {}
    reason: str = Field("", max_length=1000)
    by: By
    state: Literal["pending", "accepted", "rejected"] = "pending"
    staged: str
    comments: list[Comment] = Field([], max_length=50)


class LogEntry(st._Strict):
    at: str
    by: By
    item: str
    change: str = Field(max_length=300)
    reason: str = Field("", max_length=1000)


class Checklist(st._Strict):
    version: int = VERSION
    next_item: int = 1
    next_change: int = 1
    items: list[Item] = Field([], max_length=MAX_ITEMS)
    pending: list[Change] = Field([], max_length=MAX_PENDING)
    log: list[LogEntry] = Field([], max_length=MAX_LOG)


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def empty() -> Checklist:
    return Checklist()


# --- file -------------------------------------------------------------------------------


def path_of(folder: Path) -> Path:
    return folder / dz.CHECKLIST_FILE


def load(folder: Path) -> Checklist:
    """The checklist of a design or revision folder; an empty one when there's no file."""
    path = path_of(folder)
    if not path.is_file():
        return empty()
    if path.stat().st_size > MAX_BYTES:
        raise ChecklistError("checklist.json is too large")
    try:
        return Checklist.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ChecklistError(f"checklist.json doesn't validate: {exc}") from exc


def _text_problems(cl: Checklist) -> list[str]:
    """Secrets and absolute paths in any text field, as for the design's prose."""
    return dz.prose_problems("the checklist", json.dumps(cl.model_dump(), ensure_ascii=False))


def check(cl: Checklist) -> list[str]:
    """Every problem with a whole checklist: references, cycles and text."""
    problems = _text_problems(cl)
    ids = [i.id for i in cl.items]
    if len(set(ids)) != len(ids):
        problems.append("an item id is used twice")
    known = set(ids)
    graph: dict[str, list[str]] = {}
    for item in cl.items:
        for dep in item.depends_on:
            if dep == item.id:
                problems.append(f"{item.id} depends on itself")
            elif dep not in known:
                problems.append(f"{item.id} depends on {dep}, which isn't in the checklist")
        graph[item.id] = [d for d in item.depends_on if d in known and d != item.id]
    state: dict[str, int] = {}

    def visit(node: str, trail: list[str]) -> str | None:
        state[node] = 1
        for nxt in graph.get(node, []):
            if state.get(nxt) == 1:
                return " -> ".join([*trail, node, nxt])
            if nxt not in state and (found := visit(nxt, [*trail, node])):
                return found
        state[node] = 2
        return None

    for node in graph:
        if node not in state and (cycle := visit(node, [])):
            problems.append(f"items depend on each other in a circle: {cycle}")
            break
    return problems


def write(folder: Path, cl: Checklist) -> None:
    problems = check(cl)
    if problems:
        raise ChecklistError("; ".join(problems[:20]))
    raw = json.dumps(cl.model_dump(), ensure_ascii=False, indent=2) + "\n"
    if len(raw.encode("utf-8")) > MAX_BYTES:
        raise ChecklistError("the checklist is too large")
    path = path_of(folder)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(raw, encoding="utf-8")
    os.replace(tmp, path)


# --- staging ----------------------------------------------------------------------------


def _clean_fields(fields: dict, *, adding: bool) -> dict:
    unknown = sorted(set(fields) - set(EDITABLE))
    if unknown:
        raise ChecklistError(f"can't change {', '.join(unknown)}; the fields are {', '.join(EDITABLE)}")
    if adding and not str(fields.get("title", "")).strip():
        raise ChecklistError("a new item needs a title")
    # Validate through the item model, so the values are checked once, here.
    Item.model_validate({"id": "c1", "title": "x", **fields})
    return dict(fields)


def stage(
    cl: Checklist,
    changes: list[dict],
    *,
    by: By,
    comment_state: Literal["pending", "accepted"] | None = None,
) -> Checklist:
    """Stage changes (`{op, item?, fields?, reason?}`). A user's own changes start accepted
    (they made them); Claude's start pending. Staging again for the same item by the same
    side replaces the earlier staged change, which is how Claude revises after a comment (the
    comments stay)."""
    start = comment_state or ("accepted" if by == "user" else "pending")
    known = {i.id for i in cl.items}
    for raw in changes:
        op = raw.get("op")
        if op not in ("add", "update", "remove"):
            raise ChecklistError(f"unknown change '{op}': use add, update or remove")
        item = raw.get("item")
        if op == "add":
            if item:
                raise ChecklistError("an add has no item id; it gets one when confirmed")
            fields = _clean_fields(raw.get("fields") or {}, adding=True)
        else:
            if item not in known:
                raise ChecklistError(f"there's no item '{item}' to {op}")
            fields = _clean_fields(raw.get("fields") or {}, adding=False) if op == "update" else {}
            if op == "update" and not fields:
                raise ChecklistError("an update changes at least one field")
        previous: list[Comment] = []
        if op != "add":
            for old in [c for c in cl.pending if c.item == item and c.by == by and c.op == op]:
                previous = old.comments
                cl.pending.remove(old)
        cid = f"p{cl.next_change}"
        cl.next_change += 1
        cl.pending.append(
            Change(
                id=cid,
                op=op,
                item=item,
                fields=fields,
                reason=str(raw.get("reason", ""))[:1000],
                by=by,
                state=start,
                staged=_now(),
                comments=previous,
            )
        )
    _guard(cl)
    return cl


def _find(cl: Checklist, change_id: str) -> Change:
    for c in cl.pending:
        if c.id == change_id:
            return c
    raise ChecklistError(f"there's no staged change '{change_id}'")


def decide(
    cl: Checklist,
    change_id: str,
    *,
    state: Literal["pending", "accepted", "rejected"] | None = None,
    comment: str | None = None,
    by: By = "user",
) -> Checklist:
    """Accept, reject or reopen a staged change, and/or add a comment to it."""
    change = _find(cl, change_id)
    if state is not None:
        change.state = state
    if comment and comment.strip():
        change.comments.append(Comment(at=_now(), by=by, text=comment.strip()))
    _guard(cl)
    return cl


def discard(cl: Checklist, change_id: str) -> Checklist:
    """Take back a staged change without it counting as a rejection."""
    cl.pending.remove(_find(cl, change_id))
    return cl


def _guard(cl: Checklist) -> None:
    problems = _text_problems(cl)
    if problems:
        raise ChecklistError("; ".join(problems))


# --- confirming -------------------------------------------------------------------------


def confirm(cl: Checklist) -> tuple[Checklist, dict]:
    """Apply every accepted change, record rejected ones, and keep what is still pending.
    All or nothing: a result that doesn't validate (a circle, a removed item that others
    depend on) raises and leaves `cl` as it was."""
    work = cl.model_copy(deep=True)
    now = _now()
    applied = {"added": [], "updated": [], "removed": [], "rejected": []}
    remaining: list[Change] = []
    for change in work.pending:
        if change.state == "pending":
            remaining.append(change)
            continue
        label = change.item or change.id
        if change.state == "rejected":
            work.log.append(
                LogEntry(
                    at=now,
                    by="user",
                    item=label,
                    change=f"rejected {change.op}: {_summary(change)}",
                    reason=change.reason,
                )
            )
            applied["rejected"].append(label)
            continue
        entry_by = change.by
        if change.op == "add":
            new_id = f"c{work.next_item}"
            work.next_item += 1
            work.items.append(
                Item.model_validate(
                    {
                        "id": new_id,
                        **change.fields,
                        "history": [{"at": now, "by": entry_by, "change": "added", "reason": change.reason}],
                    }
                )
            )
            applied["added"].append(new_id)
        else:
            target = next((i for i in work.items if i.id == change.item), None)
            if target is None:
                raise ChecklistError(f"{change.item} is gone, so '{change.op}' can't be applied")
            if change.op == "remove":
                work.items.remove(target)
                work.log.append(
                    LogEntry(
                        at=now,
                        by=entry_by,
                        item=target.id,
                        change=f"removed '{target.title}'",
                        reason=change.reason,
                    )
                )
                applied["removed"].append(target.id)
            else:
                data = target.model_dump()
                data.update(change.fields)
                data["history"] = [
                    *data["history"],
                    {"at": now, "by": entry_by, "change": _summary(change), "reason": change.reason},
                ][-100:]
                idx = work.items.index(target)
                work.items[idx] = Item.model_validate(data)
                applied["updated"].append(target.id)
    work.pending = remaining
    work.log = work.log[-MAX_LOG:]
    problems = check(work)
    if problems:
        raise ChecklistError("; ".join(problems[:20]))
    return work, applied


def _summary(change: Change) -> str:
    if change.op == "remove":
        return "remove"
    parts = [f"{k} = {change.fields[k]}" for k in EDITABLE if k in change.fields]
    return "; ".join(parts)[:290] or change.op


# --- facts for the rest of the app ------------------------------------------------------


def counts(cl: Checklist) -> dict:
    live = [i for i in cl.items if i.status != "dropped"]
    return {
        "total": len(live),
        "done": sum(1 for i in live if i.status == "done"),
        "pending": sum(1 for c in cl.pending if c.state == "pending"),
        "staged": len(cl.pending),
    }


def view(folder: Path) -> dict:
    """The checklist as the API and the CLI show it, with its counts."""
    cl = load(folder)
    return {**cl.model_dump(), "counts": counts(cl)}


# --- the roadmap (ADR 0029 point 5) -----------------------------------------------------

_PRIORITY_RANK = {"high": 0, "medium": 1, None: 1, "low": 2}  # no priority counts as medium
_COLUMNS = (("now", "doing"), ("next", "decided"), ("later", "idea"), ("done", "done"))


def _natural(text: str) -> list:
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", text)]


def _order(item: Item) -> tuple:
    return (_PRIORITY_RANK[item.priority], int(item.id[1:]))


def roadmap(cl: Checklist) -> dict:
    """Now (doing), Next (decided), Later (ideas) and Done, from the confirmed items only, most
    important first, plus the same items grouped by phase for the timeline. Dropped items are left
    out. Pure: the same checklist always gives the same roadmap."""
    columns = {
        name: [i for i in sorted(cl.items, key=_order) if i.status == status] for name, status in _COLUMNS
    }
    live = [i for i in cl.items if i.status != "dropped"]
    names = sorted({i.phase for i in live if i.phase}, key=_natural)
    phases = [
        {"phase": name, "items": [i for i in sorted(live, key=_order) if i.phase == name]} for name in names
    ]
    unphased = [i for i in sorted(live, key=_order) if not i.phase]
    if unphased:
        phases.append({"phase": None, "items": unphased})
    dump = lambda items: [i.model_dump() for i in items]  # noqa: E731
    return {
        **{name: dump(items) for name, items in columns.items()},
        "phases": [{"phase": p["phase"], "items": dump(p["items"])} for p in phases],
        "pending": sum(1 for c in cl.pending if c.state != "rejected"),
    }


def roadmap_markdown(cl: Checklist, title: str = "Roadmap") -> str:
    """The roadmap as the Markdown a project keeps: Now / Next / Later, then Done."""
    data = roadmap(cl)
    lines = [f"# {title}", ""]
    for heading, key in (("Now", "now"), ("Next", "next"), ("Later", "later"), ("Done", "done")):
        lines += [f"## {heading}"]
        items = data[key]
        if not items:
            lines += ["- Nothing yet."] if key != "done" else ["- Nothing done yet."]
        for i in items:
            tail = [x for x in (i["phase"], f"{i['priority']} priority" if i["priority"] else None) if x]
            line = f"- **{i['title']}**" + (f" ({', '.join(tail)})" if tail else "")
            if i["note"]:
                line += f": {i['note']}"
            lines.append(line)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
