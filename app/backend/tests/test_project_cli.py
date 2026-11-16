"""The CLI commands the Archeion plugin's skills run from a project session (ADR 0009)."""

from __future__ import annotations

import json

from app.__main__ import main
from app.db import Database


def _here(monkeypatch, folder) -> None:
    monkeypatch.setenv("ARCHEION_CALLER_DIR", str(folder))


def test_projects_show_here(settings, monkeypatch, capsys):
    ws = settings.repo_root.parent
    _here(monkeypatch, ws / "beta" / "collectors" / "sub1")
    assert main(["projects", "show", "--here"], settings) == 0
    out = capsys.readouterr().out
    assert out.startswith("sub1 (Sub one)")
    assert "group: g1 (Group one) (from its parent)" in out
    assert "part of: beta" in out and "used by: none" in out

    assert main(["projects", "show", "--project", "alpha", "--json"], settings) == 0
    facts = json.loads(capsys.readouterr().out)
    assert facts["id"] == "alpha" and facts["depends_on"] == ["beta"] and facts["ports"] == [20100]
    assert facts["group_members"] == ["alpha", "beta", "sub1"] and facts["group_inherited"] is False
    assert facts["notes"].startswith("# Alpha")
    assert "dir" not in facts


def test_projects_show_refuses_unknown_places(settings, monkeypatch, capsys):
    _here(monkeypatch, settings.repo_root.parent / "gamma")
    assert main(["projects", "show", "--here"], settings) == 1
    assert "isn't inside a registered project" in capsys.readouterr().err
    _here(monkeypatch, settings.repo_root / "docs")
    assert main(["projects", "show", "--here"], settings) == 1
    assert "this is Archeion itself" in capsys.readouterr().err
    assert main(["projects", "show", "--project", "nobody"], settings) == 1


def test_projects_ports(settings, capsys):
    (settings.registry_root / "projects" / "beta.md").write_text(
        "---\npath: ../beta\ngroup: g1\nports: [20100, 20101]\n---\n# Beta\n", encoding="utf-8"
    )
    assert main(["projects", "ports", "--json"], settings) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["ports"] == [
        {"port": 20100, "projects": ["alpha", "beta"]},
        {"port": 20101, "projects": ["beta"]},
    ]
    assert data["clashes"] == [{"port": 20100, "projects": ["alpha", "beta"]}]
    assert main(["projects", "ports"], settings) == 0
    out = capsys.readouterr().out
    assert "20100  alpha, beta  <- used twice" in out and "1 port(s)" in out


def test_inbox_create_records_the_origin(settings, monkeypatch, tmp_path, capsys):
    note = tmp_path / "note.md"
    note.write_text("I moved to port 20105.\n", encoding="utf-8")
    _here(monkeypatch, settings.repo_root.parent / "alpha" / "docs")
    assert main(["inbox", "create", "--file", str(note)], settings) == 0
    assert "for archeion from alpha" in capsys.readouterr().out

    with Database(settings.db_file).conn() as conn:
        row = conn.execute("SELECT kind, source, origin, status, body FROM feedback").fetchone()
    assert dict(row) == {
        "kind": "prompt",
        "source": "archeion",
        "origin": "alpha",
        "status": "open",
        "body": "I moved to port 20105.",
    }
    assert main(["inbox", "list", "--project", "archeion"], settings) == 0
    assert "from alpha" in capsys.readouterr().out

    # To another project, from a folder that isn't registered: no origin.
    _here(monkeypatch, settings.repo_root.parent / "gamma")
    assert main(["inbox", "create", "--to", "beta", "--kind", "review", "--file", str(note)], settings) == 0
    assert capsys.readouterr().out.startswith("Created #2 (review) for beta.")
    assert main(["inbox", "create", "--to", "nobody", "--file", str(note)], settings) == 1
    note.write_text("  \n", encoding="utf-8")
    assert main(["inbox", "create", "--file", str(note)], settings) == 1
    assert "empty" in capsys.readouterr().err


def test_origin_is_in_the_api(settings, authed, monkeypatch, tmp_path):
    note = tmp_path / "note.md"
    note.write_text("Hello from alpha.\n", encoding="utf-8")
    _here(monkeypatch, settings.repo_root.parent / "alpha")
    assert main(["inbox", "create", "--file", str(note)], settings) == 0
    items = authed.get("/api/feedback").json()
    assert items[0]["origin"] == "alpha"


def test_version(settings, capsys):
    assert main(["version"], settings) == 0
    assert capsys.readouterr().out.strip() == "9.9.9"


def _answer(settings, item_id: int, text: str) -> None:
    from app.services import feedback as fb

    with Database(settings.db_file).conn() as conn:
        fb.claim(conn, item_id)
        fb.reply(conn, item_id, text)


def test_a_session_carries_on_a_thread(settings, monkeypatch, tmp_path, capsys):
    """/archeion:report and /archeion:inbox add to a conversation, as a reply in the viewer does."""
    note = tmp_path / "note.md"
    note.write_text("I moved to port 20105.\n", encoding="utf-8")
    _here(monkeypatch, settings.repo_root.parent / "alpha" / "docs")
    assert main(["inbox", "create", "--kind", "review", "--json", "--file", str(note)], settings) == 0
    created = json.loads(capsys.readouterr().out)
    assert (created["id"], created["thread_id"], created["status"]) == (1, 1, "open")

    # Waiting for Archeion: a second message is refused, as in the viewer.
    assert main(["inbox", "create", "--in", "1", "--file", str(note)], settings) == 1
    assert "still waits for Claude" in capsys.readouterr().err

    _answer(settings, 1, "Which port does the worker use?")
    note.write_text("The worker uses 20106.\n", encoding="utf-8")
    assert main(["inbox", "create", "--in", "1", "--file", str(note)], settings) == 0
    out = capsys.readouterr().out
    assert "Added #2 to thread #1 (for archeion), after #1; open." in out
    assert "ids: item #2, thread #1" in out

    with Database(settings.db_file).conn() as conn:
        row = conn.execute("SELECT * FROM feedback WHERE id = 2").fetchone()
    assert (row["thread_id"], row["parent_id"], row["kind"], row["source"], row["origin"]) == (
        1,
        1,
        "review",
        "archeion",
        "alpha",
    )
    assert main(["inbox", "show", "2"], settings) == 0
    out = capsys.readouterr().out
    assert "Which port does the worker use?" in out and "Your request now (#2" in out
    assert "ids: item #2, thread #1" in out and "thread #1: 2 message(s), newest #2 (open)" in out
    assert main(["inbox", "show", "1", "--json"], settings) == 0
    shown = json.loads(capsys.readouterr().out)
    assert (shown["id"], shown["thread_id"], shown["latest_id"]) == (1, 1, 2)

    # The project's own threads, one row each, and nothing from elsewhere.
    _here(monkeypatch, settings.repo_root.parent / "gamma")
    assert main(["inbox", "create", "--file", str(note)], settings) == 0
    _here(monkeypatch, settings.repo_root.parent / "alpha")
    capsys.readouterr()
    assert main(["inbox", "threads", "--from-here", "--json"], settings) == 0
    threads = json.loads(capsys.readouterr().out)
    assert [(t["id"], t["messages"], t["latest_id"], t["status"]) for t in threads] == [(1, 2, 2, "open")]
    assert main(["inbox", "threads", "--from-here"], settings) == 0
    out = capsys.readouterr().out
    assert "2 message(s), latest #2" in out and "last reply: Which port" in out

    # Resolving closes the whole thread; it then leaves the active list.
    _answer(settings, 2, "Recorded both ports.")
    assert main(["inbox", "resolve", "2"], settings) == 0
    assert "Resolved thread #1." in capsys.readouterr().out
    assert main(["inbox", "threads", "--from-here"], settings) == 0
    assert "No active threads." in capsys.readouterr().out
    assert main(["inbox", "threads", "--from-here", "--status", "all", "--json"], settings) == 0
    assert json.loads(capsys.readouterr().out)[0]["status"] == "resolved"


def test_a_session_records_and_answers_a_follow_up(settings, monkeypatch, tmp_path, capsys):
    """A follow-up typed in the chat goes into the thread already claimed, so it never shows as
    open and on-demand Claude doesn't pick it up."""
    note = tmp_path / "note.md"
    note.write_text("Fix the README.\n", encoding="utf-8")
    _here(monkeypatch, settings.repo_root.parent / "gamma")
    assert main(["inbox", "create", "--to", "alpha", "--file", str(note)], settings) == 0
    _answer(settings, 1, "Fixed the install section.")
    _here(monkeypatch, settings.repo_root.parent / "alpha")
    note.write_text("Also the usage section.\n", encoding="utf-8")
    assert (
        main(["inbox", "create", "--in", "1", "--claim", "--to", "beta", "--file", str(note)], settings) == 1
    )
    assert "--to and --in" in capsys.readouterr().err
    assert main(["inbox", "create", "--claim", "--file", str(note)], settings) == 1
    assert main(["inbox", "create", "--in", "1", "--claim", "--file", str(note)], settings) == 0
    out = capsys.readouterr().out
    assert "claimed, answer it with: inbox reply 2" in out and "ids: item #2, thread #1" in out
    with Database(settings.db_file).conn() as conn:
        row = conn.execute("SELECT status, claimed_at, source, origin FROM feedback WHERE id = 2").fetchone()
    assert row["status"] == "in_progress" and row["claimed_at"]
    assert (row["source"], row["origin"]) == ("alpha", "alpha")
    assert main(["inbox", "threads", "--here", "--json"], settings) == 0
    assert json.loads(capsys.readouterr().out)[0]["status"] == "in_progress"
    reply = tmp_path / "reply.md"
    reply.write_text("Done.\n", encoding="utf-8")
    assert main(["inbox", "reply", "2", "--json", "--file", str(reply)], settings) == 0
    replied = json.loads(capsys.readouterr().out)
    assert (replied["id"], replied["thread_id"], replied["status"]) == (2, 1, "answered")
