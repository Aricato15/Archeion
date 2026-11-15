"""Projects and modules (ADR 0016): detected from the folder, set on the page, or from the viewer."""

from __future__ import annotations

import pytest

from app.__main__ import main
from app.services.registry import RegisterError, load_registry, register, set_type, split_frontmatter, survey


def _load(settings):
    return load_registry(settings.registry_root, settings.repo_root, settings.workspace_dir)


def _page(settings, name: str):
    return settings.registry_root / "projects" / f"{name}.md"


def test_detected_types(settings):
    reg = _load(settings)
    alpha, beta, sub1 = reg.projects["alpha"], reg.projects["beta"], reg.projects["sub1"]
    # No parent: a project, repository or not. Inside one, without its own .git: a module.
    assert (alpha.type, beta.type, sub1.type) == ("project", "project", "module")
    assert sub1.type_source == "detected" and sub1.owner == "beta" and beta.owner is None
    assert reg.warnings == []


def test_a_nested_repository_is_a_project(settings):
    (settings.repo_root.parent / "beta" / "collectors" / "sub1" / ".git").write_text(
        "gitdir: x\n", encoding="utf-8"
    )
    sub1 = _load(settings).projects["sub1"]
    assert sub1.type == "project" and sub1.owner is None


def test_a_folder_that_isnt_here_falls_back_on_parent(settings):
    _page(settings, "far").write_text(
        "---\npath: ../nowhere/far\nparent: beta\n---\n# Far\n", encoding="utf-8"
    )
    assert _load(settings).projects["far"].type == "module"


def test_the_page_overrides_detection(settings):
    page = _page(settings, "sub1")
    page.write_text(
        page.read_text(encoding="utf-8").replace("parent: beta\n", "parent: beta\ntype: project\n")
    )
    sub1 = _load(settings).projects["sub1"]
    assert (sub1.type, sub1.type_source, sub1.detected_type) == ("project", "page", "module")


def test_bad_and_orphan_types_warn(settings):
    page = _page(settings, "sub1")
    page.write_text(page.read_text(encoding="utf-8").replace("parent: beta\n", "parent: beta\ntype: lib\n"))
    beta = _page(settings, "beta")
    beta.write_text(beta.read_text(encoding="utf-8").replace("group: g1\n", "group: g1\ntype: module\n"))
    reg = _load(settings)
    assert reg.projects["sub1"].type == "module"  # detected, since 'lib' isn't a type
    messages = {w["page"]: w["message"] for w in reg.warnings}
    assert "unknown type 'lib'" in messages["projects/sub1.md"]
    assert "needs `parent:`" in messages["projects/beta.md"]


def test_set_type_changes_only_that_line(settings):
    page = _page(settings, "sub1")
    page.write_bytes(
        b"---\r\npath: ../beta/collectors/sub1\r\nparent: beta\r\n---\r\n# Sub one\r\n\r\nNotes.\r\n"
    )
    before = page.read_bytes()
    set_type(settings.registry_root, _load(settings), "sub1", "project")
    assert page.read_bytes() == before.replace(b"parent: beta\r\n", b"parent: beta\r\ntype: project\r\n")
    set_type(settings.registry_root, _load(settings), "sub1", "module")
    assert b"type: module\r\n" in page.read_bytes() and b"type: project" not in page.read_bytes()
    set_type(settings.registry_root, _load(settings), "sub1", None)
    assert page.read_bytes() == before
    assert not list(page.parent.glob(".*.tmp"))


def test_set_type_refuses(settings):
    reg = _load(settings)
    with pytest.raises(RegisterError, match="can't be a module"):
        set_type(settings.registry_root, reg, "alpha", "module")
    with pytest.raises(RegisterError, match="must be project or module"):
        set_type(settings.registry_root, reg, "alpha", "lib")
    with pytest.raises(KeyError):
        set_type(settings.registry_root, reg, "ghost", "project")


def test_api_sets_and_resets_the_type(authed, settings):
    r = authed.put("/api/registry/projects/sub1/type", json={"type": "project"})
    assert r.status_code == 200 and r.json()["type"] == "project" and r.json()["type_source"] == "page"
    meta, body, _ = split_frontmatter(_page(settings, "sub1").read_text(encoding="utf-8"))
    assert meta["type"] == "project" and body.startswith("# Sub one")
    r = authed.put("/api/registry/projects/sub1/type", json={"type": None})
    assert r.json()["type"] == "module" and r.json()["type_source"] == "detected"
    assert "type" not in split_frontmatter(_page(settings, "sub1").read_text(encoding="utf-8"))[0]
    assert authed.put("/api/registry/projects/ghost/type", json={"type": "project"}).status_code == 404
    assert authed.put("/api/registry/projects/sub1/type", json={"type": "lib"}).status_code == 422
    assert authed.put("/api/registry/projects/alpha/type", json={"type": "module"}).status_code == 400


def test_api_type_needs_a_session(client):
    assert client.put("/api/registry/projects/sub1/type", json={"type": "project"}).status_code == 401


def test_cli_type_and_show(settings, capsys):
    assert main(["projects", "show", "--project", "sub1"], settings) == 0
    assert "type: module of beta (detected)" in capsys.readouterr().out
    assert main(["projects", "show", "--project", "beta"], settings) == 0
    assert "modules: sub1" in capsys.readouterr().out
    assert main(["projects", "type", "sub1", "project"], settings) == 0
    assert "sub1: project (set on its page)" in capsys.readouterr().out
    assert main(["projects", "type", "sub1", "auto"], settings) == 0
    assert "sub1: module of beta (detected)" in capsys.readouterr().out
    assert main(["projects", "type", "alpha", "module"], settings) == 1


def test_register_with_a_type(settings):
    reg = _load(settings)
    ws = settings.workspace_dir
    (ws / "beta" / "collectors" / "sub2").mkdir()
    (ws / "beta" / "collectors" / "sub2" / "go.mod").write_text("module sub2\n", encoding="utf-8")
    items = [i for r in survey(reg, settings.repo_root, ws) for i in r["items"]]
    item = next(i for i in items if i["folder"].endswith("sub2"))
    assert item["detected_type"] == "module" and item["registered"] is None
    register(
        settings.registry_root,
        reg,
        settings.repo_root,
        ws,
        root=None,
        path=item["path"],
        name="sub2",
        type="project",
    )
    assert split_frontmatter(_page(settings, "sub2").read_text(encoding="utf-8"))[0]["type"] == "project"
    assert _load(settings).projects["sub2"].type == "project"
    with pytest.raises(RegisterError, match="inside a registered project"):
        register(
            settings.registry_root,
            _load(settings),
            settings.repo_root,
            ws,
            root=None,
            path="../gamma",
            name="gamma",
            type="module",
        )
