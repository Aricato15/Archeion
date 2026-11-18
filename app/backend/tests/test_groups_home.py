"""Groups with a home (ADR 0027): a project page of type `group`."""

from __future__ import annotations

import pytest

from app.__main__ import main
from app.services.registry import load_registry


def _load(settings):
    return load_registry(settings.registry_root, settings.repo_root, settings.workspace_dir)


def _page(settings, name: str, text: str, kind: str = "projects") -> None:
    (settings.registry_root / kind / f"{name}.md").write_text(text, encoding="utf-8")


def _make_group(settings, with_group_page: bool = True) -> None:
    (settings.repo_root.parent / "alpha" / "sub").mkdir(exist_ok=True)
    _page(settings, "top", "---\npath: ../alpha\ntype: group\n---\n# Top\n\nThe top layer.\n")
    if with_group_page:
        _page(settings, "top", "---\ntitle: The system\n---\n# The system\n\nNarrative.\n", "groups")
    _page(settings, "beta", "---\npath: ../beta\ngroup: top\n---\n# Beta\n")
    _page(settings, "alpha", "---\npath: ../alpha/sub\nparent: top\n---\n# Alpha\n")


def test_a_group_with_a_home_joins_its_group_page(settings):
    _make_group(settings)
    reg = _load(settings)
    top, group = reg.projects["top"], reg.groups["top"]
    assert top.type == "group" and top.type_source == "page" and top.owner is None
    assert group.home == "top" and group.title == "The system" and group.summary == "Narrative."
    assert sorted(group.projects) == ["alpha", "beta", "sub1"]  # sub1 follows beta
    assert sorted(top.members) == sorted(group.projects)
    assert reg.warnings == []


def test_a_group_without_a_group_page_makes_its_own(settings):
    _make_group(settings, with_group_page=False)
    reg = _load(settings)
    group = reg.groups["top"]
    assert group.home == "top" and group.page == "projects/top.md" and group.title == "Top"
    assert reg.warnings == []


def test_a_child_of_the_home_is_a_member_and_its_module_follows_the_group(settings):
    _make_group(settings)
    _page(settings, "mod", "---\npath: ../alpha/src\nparent: top\n---\n# Mod\n")
    (settings.repo_root.parent / "alpha" / "src").mkdir(exist_ok=True)
    reg = _load(settings)
    assert reg.projects["mod"].type == "module" and reg.projects["mod"].owner == "top"
    assert "mod" in reg.projects["top"].members and "mod" in reg.projects["top"].children


def test_groups_dont_nest(settings):
    _make_group(settings)
    _page(settings, "inner", "---\npath: ../beta\ntype: group\ngroup: top\nparent: top\n---\n# Inner\n")
    reg = _load(settings)
    messages = [w["message"] for w in reg.warnings if w["page"] == "projects/inner.md"]
    assert any("can't have `parent:`" in m for m in messages)
    assert any("can't be a member of a group" in m for m in messages)
    assert reg.projects["inner"].parent is None and reg.projects["inner"].group is None
    assert "inner" not in reg.groups["top"].projects


def test_a_project_and_a_group_sharing_a_name_warn(settings):
    _page(settings, "g1", "---\npath: ../alpha\n---\n# G1\n")
    reg = _load(settings)
    assert [w for w in reg.warnings if "both a project and a group" in w["message"]]
    assert reg.groups["g1"].home is None


def test_unknown_type_message_names_group(settings):
    _page(settings, "odd", "---\npath: ../alpha\ntype: nope\n---\n# Odd\n")
    reg = _load(settings)
    assert any("project, module or group" in w["message"] for w in reg.warnings)


@pytest.fixture
def group_home(settings):
    _make_group(settings)


def test_group_home_is_a_doc_source_with_the_project_allowlist(group_home, authed):
    ids = {s["id"] for s in authed.get("/api/sources").json()}
    assert "top" in ids
    tree = authed.get("/api/docs/tree", params={"source": "top"}).json()

    def files(node):
        return [node["path"]] if node["type"] == "file" else [p for c in node["children"] for p in files(c)]

    assert sorted(files(tree)) == ["CLAUDE.md", "README.md", "docs/api.md", "docs/roadmap.md"]
    r = authed.get("/api/docs/file", params={"source": "top", "path": "src/code.md"})
    assert r.status_code in (400, 403, 404)


def test_cli_lists_a_group_home_under_its_group(settings, capsys):
    _make_group(settings)
    assert main(["projects", "list"], settings) == 0
    out = capsys.readouterr().out
    assert "The system [top] (group, active)" in out
    assert "  - beta (" in out and "  - alpha (" in out
    assert "- top (" not in out
