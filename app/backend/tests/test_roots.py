"""Named project roots (ADR 0008): projects in a granted folder outside the workspace."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.__main__ import main
from app.config import Settings
from app.main import create_app
from app.services.registry import discover, load_registry, split_frontmatter, stub_page
from app.services.roots import WORKSPACE, parse_roots

from .conftest import ORIGIN, _git


@pytest.fixture
def outside(tmp_path: Path) -> Path:
    """A folder next to the workspace (tmp/ws), so outside it: tmp/private/omega, a git
    repo with docs, and a sub-project omega/collectors/o1."""
    base = tmp_path / "private"
    omega = base / "omega"
    (omega / "docs").mkdir(parents=True)
    (omega / "CLAUDE.md").write_text("# omega\n", encoding="utf-8")
    (omega / "docs" / "guide.md").write_text("# Omega guide\n", encoding="utf-8")
    (omega / "secret.txt").write_text("not served\n", encoding="utf-8")
    sub = omega / "collectors" / "o1"
    sub.mkdir(parents=True)
    (sub / "package.json").write_text("{}\n", encoding="utf-8")
    _git(omega, "init", "-q")
    _git(omega, "config", "user.name", "Omega Author")
    _git(omega, "config", "user.email", "omega@example.com")
    _git(omega, "config", "core.autocrlf", "false")
    _git(omega, "add", "-A")
    _git(omega, "commit", "-q", "-m", "feat: omega")
    return base


def _with_roots(settings: Settings, raw: str) -> Settings:
    return Settings(**{**settings.model_dump(), "roots": raw, "_env_file": None})


@pytest.fixture
def rsettings(settings: Settings, outside: Path) -> Settings:
    return _with_roots(settings, f"private={outside}")


def _page(settings: Settings, name: str, text: str) -> None:
    (settings.registry_root / "projects" / f"{name}.md").write_text(text, encoding="utf-8")


def _load(settings: Settings):
    return load_registry(settings.registry_root, settings.repo_root, settings.project_roots)


# --- parsing --------------------------------------------------------------------------


def test_parse_roots_accepts_good_entries(settings, outside):
    roots = parse_roots(f" private={outside} ; ", settings.repo_root, settings.workspace_dir)
    assert roots.errors == [] and roots.named == {"private": outside.resolve()}
    assert roots.get(WORKSPACE) == settings.workspace_dir and roots.get("nope") is None
    assert [n for n, _ in roots.all()] == ["workspace", "private"]
    assert parse_roots("", settings.repo_root, settings.workspace_dir).named == {}


def test_parse_roots_refuses_bad_entries(settings, outside):
    drive = Path(outside.anchor)
    cases = {
        "private": "must look like name=folder",
        f"Private={outside}": "lowercase letters",
        f"x={outside}": "lowercase letters",
        f"workspace={outside}": "reserved",
        f"a1={outside};a1={outside}": "listed twice",
        f"gone={outside / 'missing'}": "isn't an existing folder",
        f"drive={drive}": "whole drive",
        f"home={Path.home()}": "home folder",
        "inside=docs": "inside Archeion's own folder",
    }
    for raw, expected in cases.items():
        roots = parse_roots(raw, settings.repo_root, settings.workspace_dir)
        assert any(expected in e for e in roots.errors), (raw, roots.errors)
    assert parse_roots(f"a1={outside};a1={outside}", settings.repo_root, settings.workspace_dir).named


def test_bad_roots_show_as_registry_warnings(settings):
    reg = _load(_with_roots(settings, "Bad=nowhere"))
    assert any(w["page"] == "" and w["message"].startswith(".env: ") for w in reg.warnings)


# --- registry -------------------------------------------------------------------------


def test_page_with_root_resolves_inside_it(rsettings, outside):
    _page(rsettings, "omega", "---\nroot: private\npath: omega\n---\n# Omega\n")
    reg = _load(rsettings)
    omega = reg.projects["omega"]
    assert omega.root == "private" and omega.available and omega.dir == (outside / "omega").resolve()
    assert reg.warnings == []
    # Pages without a root still resolve against this repo, inside the workspace.
    assert reg.projects["alpha"].root is None and reg.projects["alpha"].available
    assert reg.project_for_dir(outside / "omega" / "docs").id == "omega"


def test_root_problems(rsettings, outside):
    _page(rsettings, "ghost", "---\nroot: elsewhere\npath: omega\n---\n")
    _page(rsettings, "escape", "---\nroot: private\npath: ../ws/alpha\n---\n")
    _page(rsettings, "absolute", f"---\nroot: private\npath: {(outside / 'omega').as_posix()}\n---\n")
    _page(rsettings, "missing", "---\nroot: private\npath: nothing-here\n---\n")
    reg = _load(rsettings)
    text = " | ".join(f"{w['page']}: {w['message']}" for w in reg.warnings)
    assert "root 'elsewhere' isn't configured on this machine" in text
    assert "points outside the root 'private'" in text
    assert "must be relative to the root 'private'" in text
    assert "doesn't exist on this machine" in text
    assert not any(reg.projects[p].available for p in ("ghost", "escape", "absolute", "missing"))


def test_removing_a_root_makes_its_projects_unavailable(rsettings, settings):
    _page(rsettings, "omega", "---\nroot: private\npath: omega\n---\n")
    reg = _load(settings)  # the same registry, without the root granted
    assert reg.projects["omega"].available is False
    assert any("isn't configured" in w["message"] for w in reg.warnings)


def test_here_explains_a_root_that_isnt_granted(rsettings, settings, outside, monkeypatch, capsys):
    _page(rsettings, "omega", "---\nroot: private\npath: omega\n---\n")
    monkeypatch.setenv("ARCHEION_CALLER_DIR", str(outside / "omega"))
    assert main(["inbox", "count", "--here"], settings) == 1  # settings: no root granted
    err = capsys.readouterr().err
    assert "its root isn't configured on this machine" in err and "omega (root 'private')" in err


def test_discover_covers_every_root(rsettings):
    found = discover(rsettings.repo_root, rsettings.project_roots)
    by_name = {f["name"]: (f["root"], f["path"], f["parent"]) for f in found}
    assert by_name["omega"] == ("private", "omega", None)
    assert by_name["o1"] == ("private", "omega/collectors/o1", "omega")
    assert by_name["alpha"] == (None, "../alpha", None)
    only = discover(rsettings.repo_root, rsettings.project_roots, "private")
    assert {f["name"] for f in only} == {"omega", "o1"}


def test_overlapping_roots_report_a_folder_once(settings):
    s = _with_roots(settings, f"lab={settings.workspace_dir}")
    names = [f["name"] for f in discover(s.repo_root, s.project_roots)]
    assert names.count("alpha") == 1


def test_stub_page_with_root_round_trips():
    page = stub_page({"name": "omega", "path": "omega", "root": "private", "parent": None}, "2026-11-15")
    meta, _, err = split_frontmatter(page)
    assert err is None and meta["root"] == "private" and meta["path"] == "omega"


# --- CLI ------------------------------------------------------------------------------


def test_cli_scan_root_and_only(rsettings, capsys):
    assert main(["projects", "scan", "--root", "nope"], rsettings) == 1
    assert "no root named 'nope'" in capsys.readouterr().err

    assert main(["projects", "scan", "--root", "private"], rsettings) == 0
    out = capsys.readouterr().out
    assert "would create omega (private:omega)" in out and "gamma" not in out

    assert main(["projects", "scan", "--only", "nobody"], rsettings) == 1
    assert "not an unregistered folder: nobody" in capsys.readouterr().err

    assert main(["projects", "scan", "--root", "private", "--only", "omega", "--write"], rsettings) == 0
    page = rsettings.registry_root / "projects" / "omega.md"
    assert "root: private\npath: omega\n" in page.read_text(encoding="utf-8")
    assert not (rsettings.registry_root / "projects" / "o1.md").exists()

    assert main(["projects", "list"], rsettings) == 0
    assert "- omega (active, root private)" in capsys.readouterr().out


def test_cli_here_finds_a_project_in_a_root(rsettings, outside, monkeypatch, capsys):
    _page(rsettings, "omega", "---\nroot: private\npath: omega\n---\n")
    monkeypatch.setenv("ARCHEION_CALLER_DIR", str(outside / "omega" / "docs"))
    assert main(["inbox", "count", "--here"], rsettings) == 0
    assert capsys.readouterr().out.strip() == "0"


# --- API ------------------------------------------------------------------------------


def test_api_serves_a_project_in_a_root(rsettings, db, pw, outside):
    _page(rsettings, "omega", "---\nroot: private\npath: omega\n---\n# Omega\n")
    client = TestClient(create_app(rsettings), headers={"Origin": ORIGIN})
    assert client.post("/api/auth/login", json={"password": pw}).status_code == 204

    reg = client.get("/api/registry").json()
    omega = next(p for p in reg["projects"] if p["id"] == "omega")
    assert omega["root"] == "private" and omega["available"] is True
    assert any(u["name"] == "o1" and u["root"] == "private" for u in reg["unregistered"])

    r = client.get("/api/docs/file", params={"source": "omega", "path": "docs/guide.md"})
    assert r.status_code == 200 and r.json()["content"].startswith("# Omega guide")
    # Only the allowlisted files, as for any project.
    assert client.get("/api/docs/file", params={"source": "omega", "path": "secret.txt"}).status_code != 200

    (outside / "omega" / "docs" / "guide.md").write_text("# Omega guide v2\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(outside / "omega"), "commit", "-qam", "docs: v2"], check=True)
    hist = client.get("/api/docs/history", params={"source": "omega", "path": "docs/guide.md"}).json()
    assert [c["subject"] for c in hist] == ["docs: v2", "feat: omega"]
