"""On-demand Claude (ADR 0020). Launching and process checks are faked: no window opens."""

from __future__ import annotations

import pytest

from app.services import feedback as fb
from app.services import responder, runner


class FakeOS:
    def __init__(self) -> None:
        self.procs: dict[int, int] = {}
        self.runs: list[list[str]] = []
        self.terminals: list[str] = []
        self.next_pid = 5100

    def _spawn(self) -> int:
        self.next_pid += 1
        self.procs[self.next_pid] = 1000 + self.next_pid
        return self.next_pid

    def launch_responder(self, repo_root, log, dirs):
        self.runs.append([str(d) for d in dirs])
        return self._spawn()

    def launch_terminal(self, claude, interval, cwd):
        self.terminals.append(interval)
        return runner.Launch(pid=self._spawn())

    def start_time(self, pid):
        return self.procs.get(pid)

    def kill(self, pid):
        self.procs.pop(pid, None)

    def finish_all(self):
        self.procs.clear()


@pytest.fixture
def fake(monkeypatch) -> FakeOS:
    f = FakeOS()
    monkeypatch.setattr(runner, "supported", lambda: True)
    monkeypatch.setattr(runner, "find_claude", lambda: "claude.exe")
    monkeypatch.setattr(runner, "launch", f.launch_terminal)
    monkeypatch.setattr(runner, "process_start_time", f.start_time)
    monkeypatch.setattr(runner, "kill_tree", f.kill)
    monkeypatch.setattr(responder, "launch", f.launch_responder)
    return f


def _tick(db, settings):
    with db.conn() as conn:
        return responder.tick(conn, settings.repo_root, [settings.repo_root.parent], can_start=True)


def _message(db, body="hello", **kw):
    with db.conn() as conn:
        return fb.create(conn, kind="prompt", body=body, **kw)


def test_runs_only_when_switched_on_and_something_new_waits(authed, fake, db, settings):
    assert authed.get("/api/responder").json()["enabled"] is False
    _message(db)
    assert _tick(db, settings) is None  # switched off
    r = authed.put("/api/responder", json={"enabled": True})
    assert r.status_code == 200 and r.json()["enabled"] and r.json()["waiting"] == 1
    assert _tick(db, settings) == "started"
    assert fake.runs == [[str(settings.repo_root.parent)]]
    view = authed.get("/api/responder").json()
    assert view["running"] and view["pid"] and view["waiting"] == 0
    assert _tick(db, settings) is None  # still running: no second run

    item = _message(db, "during the run")
    fake.finish_all()
    assert _tick(db, settings) == "finished"
    assert _tick(db, settings) == "started"  # the message written during the run
    assert len(fake.runs) == 2

    # Claude claims and releases it: left open on purpose, so it doesn't start a run again.
    with db.conn() as conn:
        fb.claim(conn, item["id"])
        fb.release(conn, item["id"])
    fake.finish_all()
    assert _tick(db, settings) == "finished"
    assert _tick(db, settings) is None
    assert len(fake.runs) == 2


def test_one_claude_job_at_a_time(authed, fake, db, settings):
    # The terminal runs: on-demand can't be switched on or run.
    assert authed.post("/api/runner/start", json={}).status_code == 200
    r = authed.put("/api/responder", json={"enabled": True})
    assert r.status_code == 400 and "inbox terminal is running" in r.json()["detail"]
    assert authed.post("/api/responder/run").status_code == 400
    assert authed.get("/api/responder").json()["can_start"] is False
    authed.post("/api/runner/stop")

    # On-demand is switched on: the terminal can't start.
    assert authed.put("/api/responder", json={"enabled": True}).status_code == 200
    r = authed.post("/api/runner/start", json={})
    assert r.status_code == 400 and "switched on" in r.json()["detail"]
    assert authed.get("/api/runner").json()["can_start"] is False

    # Switched off but a run is going: still refused until it ends.
    authed.put("/api/responder", json={"enabled": False})
    assert authed.post("/api/responder/run").status_code == 200
    assert "working on the inbox" in authed.post("/api/runner/start", json={}).json()["detail"]
    assert authed.post("/api/responder/run").status_code == 400  # already running
    assert authed.post("/api/responder/stop").json()["running"] is False
    assert authed.post("/api/runner/start", json={}).status_code == 200


def test_refused_when_the_backend_isnt_local(fake, db, settings):
    with db.conn() as conn:
        with pytest.raises(runner.RunnerError, match="another network interface"):
            responder.set_enabled(conn, True, can_start=False)
        responder.set_enabled(conn, False, can_start=False)  # switching off is always fine


def test_api_requires_login(client):
    assert client.get("/api/responder").status_code == 401
    assert client.post("/api/responder/run").status_code == 401
