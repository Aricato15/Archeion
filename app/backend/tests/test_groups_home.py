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


# --- promote and demote (ADR 0027, phase 2) ------------------------------------------------


def _front(settings, name: str) -> str:
    return (settings.registry_root / "projects" / f"{name}.md").read_text(encoding="utf-8")


@pytest.fixture
def solo(settings):
    """A top-level project with one module and a sub-project of its own."""
    gamma = settings.repo_root.parent / "gamma"
    (gamma / "mod").mkdir(exist_ok=True)
    (gamma / "nested").mkdir(exist_ok=True)
    (gamma / "nested" / ".git").write_text("gitdir: x\n", encoding="utf-8")
    _page(settings, "solo", "---\npath: ../gamma\n---\n# Solo\n")
    _page(settings, "solo-mod", "---\npath: ../gamma/mod\nparent: solo\n---\n# Mod\n")
    _page(settings, "solo-sub", "---\npath: ../gamma/nested\nparent: solo\n---\n# Sub\n")


def test_promote_dry_run_changes_nothing(solo, settings, capsys):
    before = _front(settings, "solo")
    assert main(["projects", "promote", "solo", "--dry-run"], settings) == 0
    out = capsys.readouterr().out
    assert "becomes a group with a home. Members: solo-mod, solo-sub" in out and "Dry run" in out
    assert _front(settings, "solo") == before


def test_promote_writes_only_type_and_stamp(solo, settings):
    before = _front(settings, "solo")
    assert main(["projects", "promote", "solo"], settings) == 0
    after = _front(settings, "solo")
    added = [line for line in after.splitlines() if line not in before.splitlines()]
    assert sorted(line.split(":")[0] for line in added) == ["promoted", "type"]
    reg = _load(settings)
    page = reg.projects["solo"]
    assert page.type == "group" and page.promoted and reg.groups["solo"].home == "solo"
    assert sorted(page.members) == ["solo-mod", "solo-sub"]
    assert reg.projects["solo-mod"].type == "module" and reg.projects["solo-mod"].owner == "solo"
    assert reg.projects["solo-sub"].type == "project"
    assert reg.warnings == []


def test_a_member_of_a_group_cant_be_promoted(settings, capsys):
    assert main(["projects", "promote", "alpha"], settings) == 1  # alpha has `group: g1`
    assert "member of group 'g1'" in capsys.readouterr().err
    assert "type: group" not in _front(settings, "alpha")


def test_a_module_cant_be_promoted(settings, capsys):
    assert main(["projects", "promote", "sub1"], settings) == 1
    assert "it's a module of beta" in capsys.readouterr().err


def test_promote_merges_a_duplicate_pair(settings, capsys):
    # A group page and a project page of one name (the placeholder case), members by `group:`.
    _page(settings, "g1", "---\npath: ../gamma\n---\n# G1\n")
    assert [w for w in _load(settings).warnings if "both a project and a group" in w["message"]]
    assert main(["projects", "promote", "g1"], settings) == 0
    assert "keeps registry/groups/g1.md as its narrative" in capsys.readouterr().out
    reg = _load(settings)
    assert reg.warnings == []
    assert reg.groups["g1"].home == "g1" and reg.groups["g1"].title == "Group one"
    assert sorted(reg.projects["g1"].members) == ["alpha", "beta", "sub1"]


def test_demote_removes_both_lines_and_needs_no_members(solo, settings):
    from app.services.registry import RegisterError, demote

    assert main(["projects", "promote", "solo"], settings) == 0
    with pytest.raises(RegisterError, match="still has 2 member"):
        demote(settings.registry_root, _load(settings), "solo")
    for name in ("solo-mod", "solo-sub"):
        (settings.registry_root / "projects" / f"{name}.md").unlink()
    assert main(["projects", "demote", "solo"], settings) == 0
    assert _front(settings, "solo") == "---\npath: ../gamma\n---\n# Solo\n"
    assert _load(settings).projects["solo"].type == "project"


def test_set_type_refuses_a_group(solo, settings):
    from app.services.registry import RegisterError, set_type

    assert main(["projects", "promote", "solo"], settings) == 0
    with pytest.raises(RegisterError, match="is a group"):
        set_type(settings.registry_root, _load(settings), "solo", "project")


def test_a_study_older_than_the_promotion_needs_a_restudy(solo, settings):
    import json
    import os

    snap = settings.registry_root / "studies" / "solo" / "2026-01-01-abcdef0"
    snap.mkdir(parents=True)
    (snap / "study.json").write_text(json.dumps({}), encoding="utf-8")
    os.utime(snap / "study.json", (1_700_000_000, 1_700_000_000))
    assert main(["projects", "promote", "solo"], settings) == 0
    assert _load(settings).projects["solo"].needs_restudy is True
    newer = snap.parent / "2026-11-19-abcdef1"
    newer.mkdir()
    (newer / "study.json").write_text("{}", encoding="utf-8")
    assert _load(settings).projects["solo"].needs_restudy is False


def test_promote_and_demote_endpoints(solo, authed, settings):
    r = authed.post("/api/registry/projects/solo/promote", json={"dry_run": True})
    assert r.status_code == 200 and r.json()["ok"] and r.json()["members"] == ["solo-mod", "solo-sub"]
    assert "type: group" not in _front(settings, "solo")
    r = authed.post("/api/registry/projects/solo/promote", json={})
    assert r.status_code == 200 and r.json()["project_page"]["type"] == "group"
    assert authed.post("/api/registry/projects/solo/promote", json={}).status_code == 409
    assert authed.post("/api/registry/projects/solo/demote").status_code == 409  # has members
    assert authed.post("/api/registry/projects/nope/promote", json={}).status_code == 404
    assert authed.post("/api/registry/projects/nope/demote").status_code == 404


# --- groups and the rest of the system (ADR 0027, phase 3) -----------------------------------


def test_depends_on_can_name_a_group_without_a_home(settings):
    _page(settings, "other", "---\npath: ../gamma\ndepends_on: [g1]\n---\n# Other\n")
    reg = _load(settings)
    other = reg.projects["other"]
    assert other.depends_on == [] and other.depends_on_groups == ["g1"]
    assert reg.groups["g1"].used_by == ["other"]
    assert reg.warnings == []


def test_depends_on_a_group_with_a_home_is_a_plain_dependency(settings):
    _make_group(settings)
    _page(settings, "other", "---\npath: ../gamma\ndepends_on: [top]\n---\n# Other\n")
    reg = _load(settings)
    assert reg.projects["other"].depends_on == ["top"] and reg.projects["top"].used_by == ["other"]
    assert reg.projects["other"].depends_on_groups == []


def test_a_member_cant_depend_on_its_own_group_and_unknown_names_warn(settings):
    _page(settings, "alpha", "---\npath: ../alpha\ngroup: g1\ndepends_on: [g1, nowhere]\n---\n# Alpha\n")
    reg = _load(settings)
    messages = [w["message"] for w in reg.warnings if w["page"] == "projects/alpha.md"]
    assert any("is the group it's part of" in m for m in messages)
    assert any("'nowhere' isn't a registered project or group" in m for m in messages)
    assert reg.projects["alpha"].depends_on_groups == []


def test_a_groups_inbox_covers_its_members(settings):
    from app.__main__ import _with_modules

    _make_group(settings)
    (settings.repo_root.parent / "alpha" / "src").mkdir(exist_ok=True)
    _page(settings, "mod", "---\npath: ../alpha/src\nparent: top\n---\n# Mod\n")
    reg = _load(settings)
    assert _with_modules(reg, reg.projects["top"]) == ["alpha", "beta", "mod", "sub1", "top"]
    # a member project keeps its own inbox, which still includes its modules
    assert _with_modules(reg, reg.projects["beta"]) == ["beta", "sub1"]


def test_projects_show_lists_a_groups_members(settings, capsys):
    _make_group(settings)
    assert main(["projects", "show", "--project", "top"], settings) == 0
    out = capsys.readouterr().out
    assert "type: group" in out and "members: alpha, beta, sub1" in out
