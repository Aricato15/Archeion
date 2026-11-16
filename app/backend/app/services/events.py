"""In-process event bus feeding the SSE stream, plus the two producers:
a watcher on every doc source and a poller that notices feedback changes made by the CLI."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from watchfiles import Change, awatch

from ..db import Database
from .sources import SourceManager

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


def doc_change_events(sources: SourceManager, changes: set[tuple[Change, str]]) -> list[Event]:
    """Group raw watcher changes into one docs.changed event per (source, kind).

    Files a source doesn't serve (e.g. a project's src/ under a watched top-level file's
    folder) are dropped, so the browser only hears about docs it can show.
    """
    grouped: dict[tuple[str, str], set[str]] = {}
    for change, raw in changes:
        found = sources.locate(Path(raw))
        if found is None:
            continue
        source, rel = found
        if any(part.startswith(".") for part in rel.split("/")) or not source.allows(rel):
            continue
        grouped.setdefault((source.id, _KIND.get(change, "modified")), set()).add(rel)
    return [
        Event("docs.changed", {"source": sid, "kind": kind, "paths": sorted(paths)})
        for (sid, kind), paths in sorted(grouped.items())
    ]


def study_change_events(sources: SourceManager, changes: set[tuple[Change, str]]) -> list[Event]:
    """One studies.changed event naming the projects whose snapshots changed (ADR 0019).
    study.json isn't a doc, so doc_change_events never reports it."""
    root = (sources.registry_root / "studies").resolve()
    projects: set[str] = set()
    for _, raw in changes:
        try:
            rel = Path(raw).resolve().relative_to(root)
        except ValueError:
            continue
        if rel.parts and not rel.parts[0].startswith("."):
            projects.add(rel.parts[0])
    return [Event("studies.changed", {"projects": sorted(projects)})] if projects else []


def design_change_events(sources: SourceManager, changes: set[tuple[Change, str]]) -> list[Event]:
    """One designs.changed event naming the projects whose designs changed (ADR 0022)."""
    root = (sources.registry_root / "designs").resolve()
    projects: set[str] = set()
    for _, raw in changes:
        try:
            rel = Path(raw).resolve().relative_to(root)
        except ValueError:
            continue
        if rel.parts and not rel.parts[0].startswith("."):
            projects.add(rel.parts[0])
    return [Event("designs.changed", {"projects": sorted(projects)})] if projects else []


async def watch_sources(sources: SourceManager, bus: EventBus, stop: asyncio.Event) -> None:
    """Watch every source's docs; restart when the registry (and so the source list) changes.

    Two watchers run per cycle: one without recursion on project roots (their top-level
    files) and one with recursion on docs folders. Edits to registry pages reload the
    registry, publish registry.changed and restart both with the new sources' paths. A
    project's docs folder appearing for the first time also triggers a restart.
    """
    while not stop.is_set():
        sources.changed.clear()
        flat: set[Path] = set()
        deep: set[Path] = set()
        for s in sources.all():
            f, d = s.watch_paths()
            flat.update(f)
            deep.update(d)
        restart = asyncio.Event()

        async def relay(restart: asyncio.Event = restart) -> None:
            _, pending = await asyncio.wait(
                [asyncio.create_task(stop.wait()), asyncio.create_task(sources.changed.wait())],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for t in pending:
                t.cancel()
            restart.set()

        async def handle(changes: set[tuple[Change, str]]) -> None:
            events = doc_change_events(sources, changes)
            registry_touched = any(
                any(sources.is_registry_page(e.data["source"], p) for p in e.data["paths"]) for e in events
            )
            for event in [
                *events,
                *study_change_events(sources, changes),
                *design_change_events(sources, changes),
            ]:
                bus.publish(event)
            if registry_touched:
                await asyncio.to_thread(sources.reload)
                bus.publish(Event("registry.changed", {"version": sources.version}))
                sources.changed.set()  # new sources: restart the watch with their paths
            elif any(_is_new_docs_dir(sources, change, raw) for change, raw in changes):
                sources.changed.set()

        async def run(paths: set[Path], recursive: bool, restart: asyncio.Event = restart) -> None:
            if not paths:
                await restart.wait()
                return
            ordered = sorted(paths, key=str)
            async for changes in awatch(*ordered, debounce=200, stop_event=restart, recursive=recursive):
                await handle(changes)

        relay_task = asyncio.create_task(relay())
        try:
            await asyncio.gather(run(flat, False), run(deep, True))
        except Exception:  # pragma: no cover - keep the server up if the watcher dies
            log.exception("docs watcher stopped; retrying in 5 s")
            await asyncio.sleep(5)
        finally:
            relay_task.cancel()


def _is_new_docs_dir(sources: SourceManager, change: Change, raw: str) -> bool:
    if change != Change.added:
        return False
    p = Path(raw)
    return p.is_dir() and any(
        s.kind == "project" and s.docs_dir and p.resolve() == (s.root / s.docs_dir).resolve()
        for s in sources.all()
    )


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
