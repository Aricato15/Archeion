"""Creating a new project or group in a granted root from Archeion (ADR 0028)."""

from __future__ import annotations

import pytest

from app.__main__ import main
from app.services.registry import RegisterError, load_registry, split_frontmatter


def _load(settings):
    return load_registry(settings.registry_root, settings.repo_root, settings.workspace_dir)


def _ws(settings):
    return settings.repo_root.parent


def test_dry_run_changes_nothing(settings, capsys):
    assert main(["projects", "new", "fresh", "--root", "workspace", "--dry-run"], settings) == 0
    out = capsys.readouterr().out
    assert "would create project fresh in ../fresh: README.md, CLAUDE.md, git repository" in out
    assert not (_ws(settings) / "fresh").exists()
    assert not (settings.registry_root / "projects" / "fresh.md").exists()


def test_creates_the_folder_files_repository_and_page(settings):
    args = ["projects", "new", "fresh", "--root", "workspace", "--title", "Fresh one"]
    args += ["--description", "A brief description."]
    assert main(args, settings) == 0
    folder = _ws(settings) / "fresh"
    assert sorted(p.name for p in folder.iterdir()) == [".git", "CLAUDE.md", "README.md"]
    assert "A brief description." in (folder / "README.md").read_text(encoding="utf-8")
    claude = (folder / "CLAUDE.md").read_text(encoding="utf-8")
    assert claude.startswith("# Fresh one") and "Planned." in claude
    reg = _load(settings)
    page = reg.projects["fresh"]
    assert reg.warnings == []
    assert page.status == "planned" and page.title == "Fresh one" and page.type == "project"
    assert page.available and page.inbox_edits and page.summary == "A brief description."
    meta = split_frontmatter((settings.registry_root / page.page).read_text(encoding="utf-8"))[0]
    assert meta["path"] == "../fresh" and "root" not in meta


def test_git_is_a_choice(settings):
    assert main(["projects", "new", "plain", "--root", "workspace", "--no-git"], settings) == 0
    assert not (_ws(settings) / "plain" / ".git").exists()


def test_a_group_gets_a_folder_and_type_group(settings):
    assert main(["projects", "new", "system", "--root", "workspace", "--kind", "group"], settings) == 0
    reg = _load(settings)
    assert reg.projects["system"].type == "group" and reg.groups["system"].home == "system"
    assert reg.warnings == []


def test_it_never_writes_into_an_existing_folder_or_name(settings, capsys):
    (_ws(settings) / "taken").mkdir()
    assert main(["projects", "new", "taken", "--root", "workspace"], settings) != 0
    assert "already exists" in capsys.readouterr().err
    assert list((_ws(settings) / "taken").iterdir()) == []
    assert main(["projects", "new", "g1", "--root", "workspace"], settings) != 0  # a group's name
    assert main(["projects", "new", "Bad Name", "--root", "workspace"], settings) != 0
    assert main(["projects", "new", "x", "--root", "nowhere"], settings) != 0


def test_a_member_of_a_group_beside_it_or_inside_it(settings):
    assert main(["projects", "new", "top", "--root", "workspace", "--kind", "group"], settings) == 0
    # linked into the group, but in the root
    assert main(["projects", "new", "beside", "--root", "workspace", "--group", "top"], settings) == 0
    # inside the group's folder: a sub-project with its own repository, or a module without one
    assert main(["projects", "new", "inner", "--group", "top", "--inside-group"], settings) == 0
    assert main(["projects", "new", "part", "--group", "top", "--inside-group", "--no-git"], settings) == 0
    reg = _load(settings)
    assert reg.warnings == []
    assert (_ws(settings) / "top" / "inner" / "README.md").is_file()
    assert reg.projects["beside"].group == "top" and reg.projects["beside"].parent is None
    assert reg.projects["inner"].parent == "top" and reg.projects["inner"].type == "project"
    assert reg.projects["part"].type == "module" and reg.projects["part"].owner == "top"
    assert sorted(reg.projects["top"].members) == ["beside", "inner", "part"]


def test_group_rules(settings):
    assert main(["projects", "new", "top", "--root", "workspace", "--kind", "group"], settings) == 0
    assert (
        main(
            ["projects", "new", "nested", "--root", "workspace", "--kind", "group", "--group", "top"],
            settings,
        )
        != 0
    )
    assert main(["projects", "new", "ghost", "--root", "workspace", "--group", "nope"], settings) != 0
    # --inside-group needs a group that has a folder; g1 is a virtual one
    assert main(["projects", "new", "lost", "--group", "g1", "--inside-group"], settings) != 0
    assert not (_ws(settings) / "lost").exists()


def test_a_failure_removes_what_it_made(settings, monkeypatch):
    from app.services import git, scaffold

    def boom(_cwd):
        raise git.GitError("no git here")

    monkeypatch.setattr(git, "init", boom)
    reg = _load(settings)
    roots = _sources_roots(settings)
    with pytest.raises(RegisterError, match="git init failed"):
        scaffold.create(
            settings.registry_root, reg, roots, settings.repo_root, root="workspace", name="doomed"
        )
    assert not (_ws(settings) / "doomed").exists()
    assert not (settings.registry_root / "projects" / "doomed.md").exists()


def _sources_roots(settings):
    from app.__main__ import _sources

    return _sources(settings).roots


def test_the_title_and_description_cant_break_the_page(settings):
    args = ["projects", "new", "quoted", "--root", "workspace", "--title", 'Say "hi": ---']
    args += ["--description", "line one\n---\nname: evil"]
    assert main(args, settings) == 0
    page = _load(settings).projects["quoted"]
    assert page.title == 'Say "hi": ---' and page.id == "quoted"


def test_the_api(authed, settings):
    body = {"root": "workspace", "name": "viaapi", "description": "From the viewer."}
    dry = authed.post("/api/registry/new", json={**body, "dry_run": True})
    assert dry.status_code == 201 and dry.json()["files"] == ["README.md", "CLAUDE.md"]
    assert "_target" not in dry.json() and not (_ws(settings) / "viaapi").exists()
    made = authed.post("/api/registry/new", json=body)
    assert made.status_code == 201 and (_ws(settings) / "viaapi" / "CLAUDE.md").is_file()
    assert "viaapi" in {p["id"] for p in authed.get("/api/registry").json()["projects"]}
    again = authed.post("/api/registry/new", json=body)
    assert again.status_code == 409
    odd = authed.post("/api/registry/new", json={**body, "name": "oddstatus", "status": "nope"})
    assert odd.status_code == 409
    assert authed.post("/api/registry/new", json={**body, "name": "../escape"}).status_code == 409
    assert not (_ws(settings).parent / "escape").exists()
