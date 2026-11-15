from __future__ import annotations

import asyncio

from watchfiles import Change

from app.services import feedback as fb
from app.services.events import Event, EventBus, doc_change_events, poll_feedback, watch_docs


def test_event_format():
    assert (
        Event("docs.changed", {"paths": ["a.md"]}).sse()
        == 'event: docs.changed\ndata: {"paths":["a.md"]}\n\n'
    )


def test_doc_change_grouping(repo):
    docs = repo / "docs"
    changes = {
        (Change.modified, str(docs / "README.md")),
        (Change.added, str(docs / "system" / "new.md")),
        (Change.modified, str(docs / ".hidden.md")),
        (Change.modified, str(repo / "outside.md")),
    }
    events = {e.data["kind"]: e.data["paths"] for e in doc_change_events(docs, changes)}
    assert events == {"modified": ["README.md"], "added": ["system/new.md"]}


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


def test_watcher_sees_doc_edits(repo):
    docs = repo / "docs"

    async def run():
        bus = EventBus()
        q = bus.subscribe()
        stop = asyncio.Event()
        task = asyncio.create_task(watch_docs(docs, bus, stop))
        await asyncio.sleep(0.5)
        (docs / "README.md").write_text("# Changed\n", encoding="utf-8")
        try:
            while True:
                event = await asyncio.wait_for(q.get(), timeout=5)
                if "README.md" in event.data["paths"]:
                    return event
        finally:
            stop.set()
            await asyncio.wait_for(task, timeout=5)

    event = asyncio.run(run())
    assert event.type == "docs.changed"


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
