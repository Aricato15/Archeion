"""In-process event bus feeding the SSE stream, plus the two producers:
a watcher on docs/ and a poller that notices feedback changes made by the CLI."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from watchfiles import Change, awatch

from ..db import Database

log = logging.getLogger("archeion.events")


@dataclass(frozen=True)
class Event:
    type: str
    data: dict = field(default_factory=dict)

    def sse(self) -> str:
        return f"event: {self.type}\ndata: {json.dumps(self.data, separators=(',', ':'))}\n\n"


class EventBus:
    def __init__(self, max_queue: int = 100) -> None:
        self._subscribers: set[asyncio.Queue[Event]] = set()
        self._max_queue = max_queue

    def subscribe(self) -> asyncio.Queue[Event]:
        q: asyncio.Queue[Event] = asyncio.Queue(self._max_queue)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[Event]) -> None:
        self._subscribers.discard(q)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    def publish(self, event: Event) -> None:
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # A stuck client: drop its oldest event rather than block everyone.
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass


_KIND = {Change.added: "added", Change.modified: "modified", Change.deleted: "deleted"}


def doc_change_events(docs_root: Path, changes: set[tuple[Change, str]]) -> list[Event]:
    """Group raw watcher changes into one docs.changed event per kind."""
    root = docs_root.resolve()
    by_kind: dict[str, set[str]] = {}
    for change, raw in changes:
        p = Path(raw).absolute()
        try:
            rel = p.relative_to(root).as_posix()
        except ValueError:
            try:
                rel = p.resolve().relative_to(root).as_posix()
            except ValueError:
                continue
        if any(part.startswith(".") for part in rel.split("/")):
            continue
        by_kind.setdefault(_KIND.get(change, "modified"), set()).add(rel)
    return [Event("docs.changed", {"kind": kind, "paths": sorted(paths)}) for kind, paths in by_kind.items()]


async def watch_docs(docs_root: Path, bus: EventBus, stop: asyncio.Event) -> None:
    if not docs_root.is_dir():
        log.warning("docs/ not found at %s, not watching", docs_root)
        return
    try:
        async for changes in awatch(docs_root, debounce=200, stop_event=stop, recursive=True):
            for event in doc_change_events(docs_root, changes):
                bus.publish(event)
    except Exception:  # pragma: no cover - keep the server up if the watcher dies
        log.exception("docs watcher stopped")


def feedback_signature(db: Database) -> tuple:
    with db.conn() as conn:
        row = conn.execute("SELECT count(*), max(updated_at), total(id) FROM feedback").fetchone()
        return tuple(row)


async def poll_feedback(db: Database, bus: EventBus, stop: asyncio.Event, interval: float) -> None:
    """Publish feedback.changed whenever the feedback table changes, whoever changed it.

    PRAGMA data_version on a long-lived connection changes when another connection commits,
    which covers both the API and the inbox CLI. Session writes also bump it, so the
    feedback table's own signature decides whether to publish.
    """
    conn = db.connect()
    try:
        version = conn.execute("PRAGMA data_version").fetchone()[0]
        signature = await asyncio.to_thread(feedback_signature, db)
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
                break
            except TimeoutError:
                pass
            try:
                current = conn.execute("PRAGMA data_version").fetchone()[0]
                if current == version:
                    continue
                version = current
                new_sig = await asyncio.to_thread(feedback_signature, db)
                if new_sig != signature:
                    signature = new_sig
                    bus.publish(Event("feedback.changed", {}))
            except Exception:  # pragma: no cover
                log.exception("feedback poll failed")
    finally:
        conn.close()
