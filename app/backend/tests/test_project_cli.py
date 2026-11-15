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
