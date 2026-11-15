from __future__ import annotations

import asyncio

from watchfiles import Change

from app.services import feedback as fb
from app.services.events import Event, EventBus, doc_change_events, poll_feedback, watch_sources
from app.services.sources import SourceManager


def test_event_format():
    assert (
        Event("docs.changed", {"paths": ["a.md"]}).sse()
        == 'event: docs.changed\ndata: {"paths":["a.md"]}\n\n'
    )


def _manager(settings):
    return SourceManager(
        settings.docs_root, settings.registry_root, settings.repo_root, settings.workspace_dir
    )


def test_doc_change_grouping(repo, settings):
    docs = repo / "docs"
    ws = repo.parent
    changes = {
        (Change.modified, str(docs / "README.md")),
        (Change.added, str(docs / "system" / "new.md")),
        (Change.modified, str(docs / ".hidden.md")),
        (Change.modified, str(repo / "outside.md")),
        (Change.modified, str(ws / "alpha" / "docs" / "api.md")),
        (Change.modified, str(ws / "alpha" / "src" / "code.md")),  # not served: dropped
        (Change.modified, str(ws / "beta" / "collectors" / "sub1" / "README.md")),
    }
    events = {
        (e.data["source"], e.data["kind"]): e.data["paths"]
        for e in doc_change_events(_manager(settings), changes)
    }
    assert events == {
        ("archeion", "modified"): ["README.md"],
        ("archeion", "added"): ["system/new.md"],
        ("alpha", "modified"): ["docs/api.md"],
        ("sub1", "modified"): ["README.md"],  # the deepest source wins, not beta
    }


def test_bus_drops_oldest_when_full():
    async def run():
        bus = EventBus(max_queue=2)
        q = bus.subscribe()
        for i in range(3):
            bus.publish(Event("e", {"i": i}))
        got = [q.get_nowait().data["i"] for _ in range(2)]
        bus.unsubscribe(q)
        assert bus.subscriber_count == 0
        return got

    assert asyncio.run(run()) == [1, 2]


def test_poll_feedback_publishes_on_change(db):
    async def run():
        bus = EventBus()
        q = bus.subscribe()
        stop = asyncio.Event()
        task = asyncio.create_task(poll_feedback(db, bus, stop, 0.02))
        await asyncio.sleep(0.1)
        # A session write alone bumps data_version but must not publish.
        with db.conn() as conn:
            conn.execute("INSERT INTO sessions VALUES ('h', 'x', 'x', 'x')")
        await asyncio.sleep(0.1)
        assert q.empty()
        await asyncio.to_thread(_create, db)
        event = await asyncio.wait_for(q.get(), timeout=2)
        stop.set()
        await task
        return event

    assert asyncio.run(run()).type == "feedback.changed"


def _create(db):
    with db.conn() as conn:
        fb.create(conn, kind="prompt", body="from the CLI")


def test_watcher_sees_edits_and_registry_changes(repo, settings):
    docs = repo / "docs"
    alpha = repo.parent / "alpha"
    sources = _manager(settings)

    async def run():
        bus = EventBus()
        q = bus.subscribe()
        stop = asyncio.Event()
        task = asyncio.create_task(watch_sources(sources, bus, stop))
        await asyncio.sleep(0.6)
        seen = []

        async def wait_for(pred):
            while True:
                event = await asyncio.wait_for(q.get(), timeout=6)
                seen.append(event)
                if pred(event):
                    return event

        try:
            (docs / "README.md").write_text("# Changed\n", encoding="utf-8")
            await wait_for(lambda e: e.data.get("source") == "archeion" and "README.md" in e.data["paths"])
            (alpha / "docs" / "api.md").write_text("# Alpha API v2\n", encoding="utf-8")
            await wait_for(lambda e: e.data.get("source") == "alpha")
            # Registering gamma reloads the registry and starts watching it.
            (repo / "registry" / "projects" / "gamma.md").write_text(
                "---\npath: ../gamma\n---\n# Gamma\n", encoding="utf-8"
            )
            await wait_for(lambda e: e.type == "registry.changed")
            assert "gamma" in sources.sources
            await asyncio.sleep(0.6)
            (repo.parent / "gamma" / "README.md").write_text("# Gamma readme\n", encoding="utf-8")
            return await wait_for(lambda e: e.data.get("source") == "gamma")
        finally:
            stop.set()
            await asyncio.wait_for(task, timeout=5)

    event = asyncio.run(run())
    assert event.data["paths"] == ["README.md"]


def test_sse_stream(app, authed):
    state = app.state.archeion
    with authed.stream("GET", "/api/events") as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        lines = r.iter_lines()
        seen = []
        for line in lines:
            seen.append(line)
            if line.startswith("event: hello"):
                break
        # End the stream: set stop, then publish so the loop wakes up and exits.
        state.stop.set()
        state.bus.publish(Event("docs.changed", {"kind": "modified", "paths": ["README.md"]}))
        rest = "\n".join(lines)
    assert "event: hello" in seen
    assert "docs.changed" in rest
