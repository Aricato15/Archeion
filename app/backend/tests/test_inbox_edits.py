"""Whether Archeion's /inbox may edit a registered project's files (ADR 0017): from the
page's `inbox_edits:`, else a module follows its project, else allowed."""

from __future__ import annotations

import json

import pytest

from app.__main__ import main
from app.services.registry import (
    load_registry,
    register,
    set_inbox_edits,
    split_frontmatter,
    stub_page,
)


def _load(settings):
    return load_registry(settings.registry_root, settings.repo_root, settings.workspace_dir)


def _page(settings, name: str):
    return settings.registry_root / "projects" / f"{name}.md"


def _add_line(settings, name: str, after: str, line: str) -> None:
    page = _page(settings, name)
    page.write_text(page.read_text(encoding="utf-8").replace(after, after + line), encoding="utf-8")


def test_allowed_by_default(settings):
    reg = _load(settings)
    alpha, sub1 = reg.projects["alpha"], reg.projects["sub1"]
    assert (alpha.inbox_edits, alpha.inbox_edits_source) == (True, "default")
    assert (sub1.inbox_edits, sub1.inbox_edits_source) == (True, "owner")
    assert reg.warnings == []


def test_a_module_follows_its_project_unless_its_page_says(settings):
    _add_line(settings, "beta", "group: g1\n", "inbox_edits: false\n")
    sub1 = _load(settings).projects["sub1"]
    assert (sub1.inbox_edits, sub1.inbox_edits_source) == (False, "owner")
    _add_line(settings, "sub1", "parent: beta\n", "inbox_edits: true\n")
    sub1 = _load(settings).projects["sub1"]
    assert (sub1.inbox_edits, sub1.inbox_edits_source) == (True, "page")


def test_a_value_that_isnt_a_boolean_warns(settings):
    _add_line(settings, "alpha", "group: g1\n", "inbox_edits: maybe\n")
    reg = _load(settings)
    assert reg.projects["alpha"].inbox_edits is True
    assert any("inbox_edits 'maybe'" in w["message"] for w in reg.warnings)


def test_set_changes_only_that_line(settings):
    page = _page(settings, "beta")
    page.write_bytes(b"---\r\npath: ../beta\r\ngroup: g1\r\nstatus: active\r\n---\r\n# Beta\r\n")
    before = page.read_bytes()
    set_inbox_edits(settings.registry_root, _load(settings), "beta", False)
    assert page.read_bytes() == before.replace(
        b"status: active\r\n", b"status: active\r\ninbox_edits: false\r\n"
    )
    set_inbox_edits(settings.registry_root, _load(settings), "beta", True)
    assert b"inbox_edits: true\r\n" in page.read_bytes() and b"false" not in page.read_bytes()
    set_inbox_edits(settings.registry_root, _load(settings), "beta", None)
    assert page.read_bytes() == before
    with pytest.raises(KeyError):
        set_inbox_edits(settings.registry_root, _load(settings), "ghost", True)


def test_new_pages_say_it_for_projects_only(settings):
    assert "inbox_edits: true" in stub_page({"name": "x", "path": "x", "inbox_edits": True})
    assert "inbox_edits" not in stub_page({"name": "x", "path": "x"})
    ws = settings.workspace_dir
    register(
        settings.registry_root,
        _load(settings),
        settings.repo_root,
        ws,
        root=None,
        path="../gamma",
        name="gamma",
    )
    assert split_frontmatter(_page(settings, "gamma").read_text(encoding="utf-8"))[0]["inbox_edits"] is True
    (ws / "beta" / "collectors" / "sub2").mkdir()
    (ws / "beta" / "collectors" / "sub2" / "go.mod").write_text("module sub2\n", encoding="utf-8")
    register(
        settings.registry_root,
        _load(settings),
        settings.repo_root,
        ws,
        root=None,
        path="../beta/collectors/sub2",
        name="sub2",
    )
    assert "inbox_edits" not in split_frontmatter(_page(settings, "sub2").read_text(encoding="utf-8"))[0]
    assert _load(settings).projects["sub2"].inbox_edits_source == "owner"


def test_scan_write_says_it_for_projects(settings, capsys):
    assert main(["projects", "scan", "--write"], settings) == 0
    assert "inbox_edits: true" in _page(settings, "gamma").read_text(encoding="utf-8")


def test_api_sets_and_resets(authed, settings):
    url = "/api/registry/projects/beta/inbox-edits"
    r = authed.put(url, json={"inbox_edits": False})
    assert (
        r.status_code == 200 and r.json()["inbox_edits"] is False and r.json()["inbox_edits_source"] == "page"
    )
    assert _load(settings).projects["sub1"].inbox_edits is False
    r = authed.put(url, json={"inbox_edits": None})
    assert r.json()["inbox_edits"] is True and r.json()["inbox_edits_source"] == "default"
    assert (
        authed.put("/api/registry/projects/ghost/inbox-edits", json={"inbox_edits": True}).status_code == 404
    )
    assert authed.put(url, json={"inbox_edits": "sure"}).status_code == 422


def test_api_needs_a_session(client):
    r = client.put("/api/registry/projects/beta/inbox-edits", json={"inbox_edits": False})
    assert r.status_code == 401


def test_cli_switch_list_and_show(settings, capsys):
    assert main(["projects", "inbox-edits", "beta", "off"], settings) == 0
    assert "beta: inbox edits not allowed (set on its page)" in capsys.readouterr().out
    assert main(["projects", "show", "--project", "sub1"], settings) == 0
    assert "inbox edits: not allowed (from beta)" in capsys.readouterr().out
    assert main(["projects", "list"], settings) == 0
    assert "no inbox edits" in capsys.readouterr().out
    assert main(["projects", "inbox-edits", "beta", "auto"], settings) == 0
    assert "beta: inbox edits allowed (default)" in capsys.readouterr().out
    assert main(["projects", "inbox-edits", "ghost", "on"], settings) == 1


def test_inbox_show_names_the_target(settings, capsys, tmp_path):
    text = tmp_path / "item.md"
    text.write_text("Fix the readme.\n", encoding="utf-8")
    assert main(["inbox", "create", "--to", "sub1", "--file", str(text)], settings) == 0
    assert main(["inbox", "create", "--file", str(text)], settings) == 0
    capsys.readouterr()
    assert main(["inbox", "show", "1", "--json"], settings) == 0
    target = json.loads(capsys.readouterr().out)["target"]
    assert target["project"] == "sub1" and target["inbox_edits"] is True
    assert target["folder"].endswith("sub1") and target["repository"].endswith("beta")
    main(["projects", "inbox-edits", "beta", "off"], settings)
    capsys.readouterr()
    assert main(["inbox", "show", "1"], settings) == 0
    assert "inbox edits not allowed" in capsys.readouterr().out
    assert main(["inbox", "show", "2", "--json"], settings) == 0
    assert json.loads(capsys.readouterr().out)["target"] is None
