from __future__ import annotations

from app.__main__ import main
from app.services.registry import discover, load_registry, split_frontmatter, stub_page


def _load(settings):
    return load_registry(settings.registry_root, settings.repo_root, settings.workspace_dir)


def test_frontmatter():
    meta, body, err = split_frontmatter("---\nname: x\nports: [1, 2]\n---\n# X\n")
    assert meta == {"name": "x", "ports": [1, 2]} and body == "# X\n" and err is None
    assert split_frontmatter("# No frontmatter\n") == ({}, "# No frontmatter\n", None)
    assert split_frontmatter("---\n: [bad\n---\nbody")[2].startswith("invalid frontmatter")


def test_registry_structure(settings):
    reg = _load(settings)
    assert set(reg.projects) == {"alpha", "beta", "sub1"}
    alpha, beta, sub1 = reg.projects["alpha"], reg.projects["beta"], reg.projects["sub1"]
    assert alpha.title == "Alpha" and alpha.summary == "The alpha service." and alpha.ports == [20100]
    assert alpha.verified == "2026-11-15" and alpha.available
    assert alpha.depends_on == ["beta"] and beta.used_by == ["alpha"]
    assert sub1.parent == "beta" and beta.children == ["sub1"]
    # sub1 has no group of its own: it belongs to its parent's
    assert sorted(reg.groups["g1"].projects) == ["alpha", "beta", "sub1"]
    assert reg.groups["g1"].title == "Group one"
    assert reg.warnings == []


def test_registry_warnings(settings):
    reg_dir = settings.registry_root / "projects"
    (reg_dir / "broken.md").write_text(
        "---\npath: ../nowhere\nparent: ghost\ngroup: nogroup\ndepends_on: [ghost, broken]\n"
        "status: weird\nports: [abc]\n---\n# Broken\n",
        encoding="utf-8",
    )
    (reg_dir / "escape.md").write_text("---\npath: ../../outside\n---\n", encoding="utf-8")
    absolute = "---\npath: C:/x\n---\n"  # sensitive-ok: test input, not a real path
    (reg_dir / "absolute.md").write_text(absolute, encoding="utf-8")
    (reg_dir / "self.md").write_text("---\npath: .\n---\n", encoding="utf-8")
    (reg_dir / "archeion.md").write_text("---\npath: .\n---\n", encoding="utf-8")
    (reg_dir / "registry.md").write_text("---\n---\n", encoding="utf-8")
    (reg_dir / "dup.md").write_text("---\nname: alpha\n---\n", encoding="utf-8")
    (reg_dir / "Bad Name.md").write_text("# x\n", encoding="utf-8")
    reg = _load(settings)
    messages = {(w["page"].split("/")[-1], w["message"].split(":")[0].split(" '")[0]) for w in reg.warnings}
    text = " | ".join(f"{w['page']}: {w['message']}" for w in reg.warnings)
    assert "doesn't exist on this machine" in text
    assert "parent 'ghost' isn't a registered project" in text
    assert "depends_on 'ghost'" in text and "can't depend on itself" in text
    assert "group 'nogroup' has no page" in text
    assert "unknown status 'weird'" in text and "port 'abc'" in text
    assert "outside the workspace" in text
    assert "must be relative" in text
    assert "points at this repo itself" in text
    assert "is reserved for Archeion" in text
    assert "duplicate project name 'alpha'" in text
    assert "isn't a valid project name" in text
    assert reg.projects["broken"].available is False and reg.projects["broken"].parent is None
    assert messages  # all collected without raising


def test_parent_cycle_is_broken(settings):
    reg_dir = settings.registry_root / "projects"
    (reg_dir / "c1.md").write_text("---\nparent: c2\n---\n", encoding="utf-8")
    (reg_dir / "c2.md").write_text("---\nparent: c1\n---\n", encoding="utf-8")
    reg = _load(settings)
    assert any("makes a cycle" in w["message"] for w in reg.warnings)
    assert reg.projects["c1"].parent is None or reg.projects["c2"].parent is None


def test_project_for_dir(settings):
    reg = _load(settings)
    ws = settings.repo_root.parent
    assert reg.project_for_dir(ws / "beta" / "collectors" / "sub1").id == "sub1"
    assert reg.project_for_dir(ws / "beta" / "collectors").id == "beta"
    assert reg.project_for_dir(ws / "gamma") is None


def test_discover_and_unregistered(settings):
    found = discover(settings.repo_root, settings.workspace_dir)
    assert {(f["name"], f["path"], f["parent"]) for f in found} == {
        ("alpha", "../alpha", None),
        ("beta", "../beta", None),
        ("sub1", "../beta/collectors/sub1", "beta"),
        ("gamma", "../gamma", None),
    }  # _shared and this repo are skipped
    from app.services.sources import SourceManager

    manager = SourceManager(
        settings.docs_root, settings.registry_root, settings.repo_root, settings.workspace_dir
    )
    assert [u["name"] for u in manager.unregistered()] == ["gamma"]


def test_stub_page_round_trips():
    page = stub_page({"name": "coll", "path": "../svc/collectors/coll", "parent": "svc"}, "2026-11-15")
    meta, body, err = split_frontmatter(page)
    assert err is None and meta["parent"] == "svc" and meta["path"] == "../svc/collectors/coll"
    assert body.startswith("\n# coll")


def test_cli_projects(settings, capsys):
    assert main(["projects", "list"], settings) == 0
    out = capsys.readouterr().out
    assert "Group one [g1]" in out and "- beta (active)" in out and "    - sub1 (active)" in out
    assert "- alpha (active) -> beta" in out and "1 folder(s)" in out

    assert main(["projects", "scan"], settings) == 0
    assert "would create gamma (../gamma)" in capsys.readouterr().out
    page = settings.registry_root / "projects" / "gamma.md"
    assert not page.exists()
    assert main(["projects", "scan", "--write"], settings) == 0
    assert page.exists() and "path: ../gamma" in page.read_text(encoding="utf-8")
    assert main(["projects", "scan"], settings) == 0
    assert "Every project in the workspace is registered." in capsys.readouterr().out


def test_templates_are_ignored_and_registry_is_a_source(settings, authed):
    reg = _load(settings)
    assert "ignored" not in reg.projects and "_template" not in reg.groups
    tree = authed.get("/api/docs/tree", params={"source": "registry"}).json()
    names = {c["name"] for c in tree["children"]}
    assert {"projects", "groups"} <= names
    # archeion's docs/ no longer holds the registry
    assert authed.get("/api/docs/file", params={"path": "system/projects/alpha.md"}).status_code == 404


def test_cli_own_sources(settings, authed, capsys):
    authed.post(
        "/api/feedback",
        json={
            "kind": "comment",
            "body": "Fix alpha's page.",
            "source": "registry",
            "doc_path": "projects/alpha.md",
        },
    )
    authed.post("/api/feedback", json={"kind": "prompt", "body": "Archeion task."})
    import json

    assert main(["inbox", "list", "--json", "--project", "archeion"], settings) == 0
    assert sorted(i["body"] for i in json.loads(capsys.readouterr().out)) == [
        "Archeion task.",
        "Fix alpha's page.",
    ]
