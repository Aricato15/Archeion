"""On-demand Claude (ADR 0020, ADR 0021). Launching and process checks are faked: no window opens."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services import feedback as fb
from app.services import responder, runner


class FakeOS:
    def __init__(self) -> None:
        self.procs: dict[int, int] = {}
        self.windows: list[str] = []  # done-marker paths
        self.headless: list[str] = []  # log paths
        self.dirs: list[list[str]] = []
        self.accept: list[bool] = []
        self.terminal_flags: list[list[str]] = []
        self.terminals: list[str] = []
        self.next_pid = 5100

    def _spawn(self) -> int:
        self.next_pid += 1
        self.procs[self.next_pid] = 1000 + self.next_pid
        return self.next_pid

    def launch_window(self, repo_root, dirs, done, accept_edits=True):
        self.windows.append(str(done))
        self.accept.append(accept_edits)
        self.dirs.append([str(d) for d in dirs])
        return self._spawn()

    def launch_headless(self, claude, repo_root, dirs, log):
        self.headless.append(str(log))
        return self._spawn()

    def launch_terminal(self, claude, interval, cwd, flags=None):
        self.terminals.append(interval)
        self.terminal_flags.append(list(flags or []))
        return runner.Launch(pid=self._spawn())

    def start_time(self, pid):
        return self.procs.get(pid)

    def kill(self, pid):
        self.procs.pop(pid, None)

    def end(self, pid: int) -> None:
        self.procs.pop(pid, None)


@pytest.fixture
def fake(monkeypatch) -> FakeOS:
    f = FakeOS()
    monkeypatch.setattr(runner, "supported", lambda: True)
    monkeypatch.setattr(runner, "find_claude", lambda: "claude.exe")
    monkeypatch.setattr(runner, "launch", f.launch_terminal)
    monkeypatch.setattr(runner, "process_start_time", f.start_time)
    monkeypatch.setattr(runner, "kill_tree", f.kill)
    monkeypatch.setattr(responder, "launch_window", f.launch_window)
    monkeypatch.setattr(responder, "launch_headless", f.launch_headless)
    return f


def _tick(db, settings):
    with db.conn() as conn:
        return responder.tick(conn, settings.repo_root, [settings.repo_root.parent], can_start=True)


def _message(db, body="hello"):
    with db.conn() as conn:
        return fb.create(conn, kind="prompt", body=body)


def test_a_visible_session_closes_when_its_turn_ends(authed, fake, db, settings):
    assert authed.get("/api/responder").json()["enabled"] is False
    _message(db)
    assert _tick(db, settings) is None  # switched off
    r = authed.put("/api/responder", json={"enabled": True})
    assert r.status_code == 200 and r.json()["enabled"] and r.json()["waiting"] == 1
    assert _tick(db, settings) == "started"
    assert len(fake.windows) == 1 and fake.dirs == [[str(settings.repo_root.parent)]]
    view = authed.get("/api/responder").json()
    assert view["running"] and view["jobs"][0]["mode"] == "window" and view["instances"] == 1
    assert _tick(db, settings) is None  # still working

    # The Stop hook writes the marker: the backend closes the window.
    marker = Path(fake.windows[0])
    assert marker.parent == settings.repo_root / "app" / "backend" / "data" / "responder"
    marker.write_text("done", encoding="ascii")
    assert _tick(db, settings) == "finished"
    assert not fake.procs and not marker.exists()
    assert authed.get("/api/responder").json()["running"] is False


def test_new_messages_start_runs_and_released_ones_dont(authed, fake, db, settings):
    authed.put("/api/responder", json={"enabled": True})
    _message(db)
    assert _tick(db, settings) == "started"
    item = _message(db, "during the run")
    assert _tick(db, settings) is None  # the one slot is taken
    fake.end(fake.next_pid)
    assert _tick(db, settings) == "started"  # the message written during the run
    with db.conn() as conn:
        fb.claim(conn, item["id"])
        fb.release(conn, item["id"])  # left open on purpose
    fake.end(fake.next_pid)
    assert _tick(db, settings) == "finished"
    assert _tick(db, settings) is None
    assert len(fake.windows) == 2


def test_headless_runs_open_no_window_and_log(authed, fake, db, settings):
    r = authed.put("/api/responder", json={"enabled": True, "headless": True})
    assert r.json()["headless"] is True
    _message(db)
    assert _tick(db, settings) == "started"
    assert fake.windows == [] and fake.headless[0].endswith(".log")
    assert authed.get("/api/responder").json()["jobs"][0]["mode"] == "headless"


def test_two_instances_run_side_by_side(authed, fake, db, settings):
    assert authed.put("/api/responder", json={"max_instances": 3}).status_code == 422
    r = authed.put("/api/responder", json={"enabled": True, "max_instances": 2})
    assert r.json()["max_instances"] == 2
    _message(db)
    assert _tick(db, settings) == "started"
    _message(db, "second")
    assert _tick(db, settings) == "started"  # a second run, in parallel
    _message(db, "third")
    assert _tick(db, settings) is None  # both slots taken
    view = authed.get("/api/responder").json()
    assert view["instances"] == 2 and not view["can_start"] and "most allowed" in view["reason"]
    assert authed.post("/api/runner/start", json={}).status_code == 400  # the terminal counts too
    r = authed.put("/api/responder", json={"max_instances": 1})
    assert r.status_code == 400 and "lowering" in r.json()["detail"]
    assert authed.post("/api/responder/stop").json()["running"] is False


def test_with_two_the_terminal_and_on_demand_share(authed, fake, db, settings):
    authed.put("/api/responder", json={"max_instances": 2, "enabled": True})
    assert authed.post("/api/runner/start", json={}).status_code == 200
    _message(db)
    assert _tick(db, settings) == "started"  # terminal + one run = 2
    _message(db, "more")
    assert _tick(db, settings) is None
    assert authed.put("/api/responder", json={"max_instances": 1}).status_code == 400


def test_with_one_the_terminal_and_on_demand_exclude_each_other(authed, fake, db, settings):
    assert authed.post("/api/runner/start", json={}).status_code == 200
    r = authed.put("/api/responder", json={"enabled": True})
    assert r.status_code == 400 and "Max Claude instances is 1" in r.json()["detail"]
    assert authed.post("/api/responder/run").status_code == 400
    authed.post("/api/runner/stop")

    assert authed.put("/api/responder", json={"enabled": True}).status_code == 200
    r = authed.post("/api/runner/start", json={})
    assert r.status_code == 400 and "switched on" in r.json()["detail"]
    authed.put("/api/responder", json={"enabled": False})
    assert authed.post("/api/responder/run").status_code == 200
    assert "working" in authed.post("/api/runner/start", json={}).json()["detail"]
    assert authed.post("/api/responder/run").status_code == 400  # no free slot
    authed.post("/api/responder/stop")
    assert authed.post("/api/runner/start", json={}).status_code == 200


def test_refused_when_the_backend_isnt_local(fake, db, settings):
    with db.conn() as conn:
        with pytest.raises(runner.RunnerError, match="another network interface"):
            responder.set_enabled(conn, True, can_start=False)
        responder.set_enabled(conn, False, can_start=False)  # switching off is always fine


def test_flags_allow_only_archeions_cli_and_the_granted_roots(tmp_path):
    flags = responder._flags([tmp_path])
    assert flags[:2] == ["--permission-mode", "auto"]
    assert any(f.startswith("Bash(powershell") and "archeion.ps1" in f for f in flags)
    assert flags[-2:] == ["--add-dir", str(tmp_path)]


def test_api_requires_login(client):
    assert client.get("/api/responder").status_code == 401
    assert client.post("/api/responder/run").status_code == 401


def test_edits_are_accepted_or_confirmed_in_both_terminals(authed, fake, db, settings):
    assert authed.get("/api/responder").json()["accept_edits"] is True
    assert authed.post("/api/runner/start", json={}).json()["running"]
    assert fake.terminal_flags[-1] == ["--permission-mode", "auto"]
    authed.post("/api/runner/stop")

    assert authed.put("/api/responder", json={"accept_edits": False}).json()["accept_edits"] is False
    authed.post("/api/runner/start", json={})
    assert fake.terminal_flags[-1] == []  # Claude asks before each edit
    authed.post("/api/runner/stop")
    authed.post("/api/responder/run")
    assert fake.accept[-1] is False
    authed.post("/api/responder/stop")
    assert "--permission-mode" not in responder._flags([], accept_edits=False)

    # Nobody can confirm a headless run's edits.
    r = authed.put("/api/responder", json={"headless": True})
    assert r.status_code == 400 and "no one to confirm" in r.json()["detail"]
    assert authed.put("/api/responder", json={"headless": True, "accept_edits": True}).status_code == 200
    r = authed.put("/api/responder", json={"accept_edits": False})
    assert r.status_code == 400
