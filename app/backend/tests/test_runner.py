"""The inbox terminal (ADR 0013). Launching and process checks are faked: no window opens."""

from __future__ import annotations

import pytest

from app.services import runner


class FakeOS:
    """Processes by PID with their start time; launch() adds one."""

    def __init__(self) -> None:
        self.procs: dict[int, int] = {}
        self.launched: list[tuple[str, str, str]] = []
        self.killed: list[int] = []
        self.next_pid = 4100

    def launch(self, claude, interval, cwd, flags=None):
        self.next_pid += 1
        self.procs[self.next_pid] = 1000 + self.next_pid
        self.launched.append((claude, interval, str(cwd)))
        return runner.Launch(pid=self.next_pid)

    def start_time(self, pid):
        return self.procs.get(pid)

    def kill(self, pid):
        self.killed.append(pid)
        self.procs.pop(pid, None)


@pytest.fixture
def fake(monkeypatch) -> FakeOS:
    f = FakeOS()
    monkeypatch.setattr(runner, "supported", lambda: True)
    monkeypatch.setattr(runner, "find_claude", lambda: "claude.exe")
    monkeypatch.setattr(runner, "launch", f.launch)
    monkeypatch.setattr(runner, "process_start_time", f.start_time)
    monkeypatch.setattr(runner, "kill_tree", f.kill)
    return f


@pytest.mark.parametrize("value", ["1m", "10m", " 30M ", "1h", "24h"])
def test_good_intervals(value):
    assert runner.normalize_interval(value) == value.strip().lower()


@pytest.mark.parametrize("value", ["", "0m", "10", "10s", "1d", "25h", "10m /evil", "m"])
def test_bad_intervals(value):
    with pytest.raises(runner.RunnerError):
        runner.normalize_interval(value)


def test_starts_tracks_and_stops(authed, fake, settings):
    r = authed.get("/api/runner")
    assert r.json() == {
        "running": False,
        "interval": "10m",
        "pid": None,
        "started_at": None,
        "can_start": True,
        "reason": None,
    }

    r = authed.post("/api/runner/start", json={"interval": "30m"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["running"] and body["interval"] == "30m" and body["pid"] == 4101
    assert fake.launched == [("claude.exe", "30m", str(settings.repo_root))]

    # a second start is refused while it runs
    r = authed.post("/api/runner/start", json={})
    assert r.status_code == 400 and "already running" in r.json()["detail"]

    # the window was closed by hand: it's reported as stopped
    fake.procs.clear()
    assert authed.get("/api/runner").json()["running"] is False

    # started again with the saved interval
    assert authed.post("/api/runner/start", json={}).json()["interval"] == "30m"
    r = authed.post("/api/runner/stop")
    assert r.json()["running"] is False
    assert fake.killed == [4102]


def test_a_reused_pid_is_not_the_terminal(authed, fake):
    pid = authed.post("/api/runner/start", json={}).json()["pid"]
    fake.procs[pid] = 1  # same PID, another process (different start time)
    assert authed.get("/api/runner").json()["running"] is False
    authed.post("/api/runner/stop")
    assert fake.killed == []  # never kills a process it didn't start


def test_interval_is_saved_and_validated(authed, fake):
    assert authed.put("/api/runner", json={"interval": "1h"}).json()["interval"] == "1h"
    assert authed.get("/api/runner").json()["interval"] == "1h"
    r = authed.put("/api/runner", json={"interval": "5 minutes"})
    assert r.status_code == 400
    r = authed.post("/api/runner/start", json={"interval": "2d"})
    assert r.status_code == 400 and fake.launched == []


def test_refuses_without_claude(authed, fake, monkeypatch):
    monkeypatch.setattr(runner, "find_claude", lambda: None)
    body = authed.get("/api/runner").json()
    assert body["can_start"] is False and "PATH" in body["reason"]
    assert authed.post("/api/runner/start", json={}).status_code == 400
    assert fake.launched == []


def test_refuses_when_not_on_loopback(authed, fake, settings):
    settings.host = "192.168.1.20"
    body = authed.get("/api/runner").json()
    assert body["can_start"] is False and "another network interface" in body["reason"]
    assert authed.post("/api/runner/start", json={}).status_code == 400
    assert fake.launched == []


def test_needs_a_session(client, fake):
    assert client.get("/api/runner").status_code == 401
    assert client.post("/api/runner/start", json={}).status_code == 401
    assert fake.launched == []
