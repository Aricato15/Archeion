"""Managing roots and registering projects from the viewer (ADR 0010)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.registry import load_registry, register, split_frontmatter, survey
from app.services.roots import format_roots, parse_roots, write_env_roots


@pytest.fixture(autouse=True)
def _no_env_roots(monkeypatch):
    monkeypatch.delenv("ARCHEION_ROOTS", raising=False)


@pytest.fixture
def outside(tmp_path: Path) -> Path:
    """tmp/private, next to the workspace: omega (a project) and omega/collectors/o1."""
    base = tmp_path / "private folder"  # a space, so .env needs quoting
    omega = base / "omega"
    (omega / "collectors" / "o1").mkdir(parents=True)
    (omega / "CLAUDE.md").write_text("# omega\n", encoding="utf-8")
    (omega / "collectors" / "o1" / "package.json").write_text("{}\n", encoding="utf-8")
    return base


def _env(settings) -> Path:
    return settings.repo_root / ".env"


# --- .env -----------------------------------------------------------------------------


def test_write_env_roots_keeps_other_lines(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "# mine\nARCHEION_PORT=20300\nARCHEION_ROOTS=old=x\nOTHER=1\nARCHEION_ROOTS=dup\n", encoding="utf-8"
    )
    write_env_roots(env, "lab=../some folder/lab")
    assert env.read_text(encoding="utf-8") == (
        '# mine\nARCHEION_PORT=20300\nARCHEION_ROOTS="lab=../some folder/lab"\nOTHER=1\n'
    )
    assert "old=x" in (tmp_path / ".env.bak").read_text(encoding="utf-8")
    write_env_roots(env, "")
    assert "ARCHEION_ROOTS=\n" in env.read_text(encoding="utf-8")


def test_write_env_roots_creates_the_file(tmp_path):
    env = tmp_path / ".env"
    write_env_roots(env, "lab=x")
    assert env.read_text(encoding="utf-8").endswith("ARCHEION_ROOTS=lab=x\n")
    assert not (tmp_path / ".env.bak").exists()


def test_written_value_reads_back(settings, outside):
    raw, problems = format_roots([("private", str(outside))])
    assert problems == [] and "\\" not in raw
    write_env_roots(_env(settings), raw)
    from app.config import Settings

    again = Settings(_env_file=_env(settings), repo_root=settings.repo_root)
    assert again.project_roots.named == {"private": outside.resolve()}


def test_format_roots_refuses_separators():
    _, problems = format_roots([("a1", "x;y"), ("a2", ""), ("a3", 'x"y')])
    assert len(problems) == 3


# --- survey and register ----------------------------------------------------------------


def _roots(settings, outside):
    return parse_roots(f"private={outside}", settings.repo_root, settings.workspace_dir)


def test_survey_lists_every_root_with_registration(settings, outside):
    roots = _roots(settings, outside)
    reg = load_registry(settings.registry_root, settings.repo_root, roots)
    by_root = {r["name"]: r for r in survey(reg, settings.repo_root, roots)}
    ws = {i["folder"]: i["registered"] for i in by_root["workspace"]["items"]}
    assert ws == {"alpha": "alpha", "beta": "beta", "beta/collectors/sub1": "sub1", "gamma": None}
    private = {i["folder"]: i for i in by_root["private"]["items"]}
    assert private["omega"]["registered"] is None and private["omega"]["root"] == "private"
    assert private["omega/collectors/o1"]["parent_folder"] == "omega"
    assert private["omega/collectors/o1"]["parent"] is None  # omega isn't registered yet


def test_survey_shows_roots_that_arent_granted(settings):
    (settings.registry_root / "projects" / "far.md").write_text(
        "---\nroot: gone\npath: far\n---\n", encoding="utf-8"
    )
    reg = load_registry(settings.registry_root, settings.repo_root, settings.project_roots)
    last = survey(reg, settings.repo_root, settings.project_roots)[-1]
    assert last["name"] == "gone" and last["granted"] is False
    assert [i["registered"] for i in last["items"]] == ["far"]


def test_register_writes_a_stub_and_links_the_parent(settings, outside):
    roots = _roots(settings, outside)
    reg = load_registry(settings.registry_root, settings.repo_root, roots)
    page = register(
        settings.registry_root, reg, settings.repo_root, roots, root="private", path="omega", name="omega"
    )
    assert page == "projects/omega.md"
    meta, _, err = split_frontmatter((settings.registry_root / page).read_text(encoding="utf-8"))
    assert err is None and meta == {"name": "omega", "root": "private", "path": "omega", "status": "active"}

    reg = load_registry(settings.registry_root, settings.repo_root, roots)
    assert reg.projects["omega"].available
    register(
        settings.registry_root,
        reg,
        settings.repo_root,
        roots,
        root="private",
        path="omega/collectors/o1",
        name="o1",
    )
    reg = load_registry(settings.registry_root, settings.repo_root, roots)
    assert reg.projects["o1"].parent == "omega" and reg.warnings == []


@pytest.mark.parametrize(
    ("root", "path", "name", "expected"),
    [
        ("nope", "omega", "omega", "no root named"),
        ("private", "omega", "Bad Name", "isn't a valid project name"),
        ("private", "omega", "archeion", "reserved"),
        ("private", "omega", "alpha", "already registered"),
        ("private", "../ws/alpha", "x1", "isn't a project Archeion found"),
        ("private", "omega/collectors", "x1", "isn't a project Archeion found"),
        (None, "../alpha", "alpha2", "already registered as 'alpha'"),
    ],
)
def test_register_refuses(settings, outside, root, path, name, expected):
    roots = _roots(settings, outside)
    reg = load_registry(settings.registry_root, settings.repo_root, roots)
    with pytest.raises(ValueError, match=expected):
        register(settings.registry_root, reg, settings.repo_root, roots, root=root, path=path, name=name)


def test_register_never_overwrites(settings):
    page = settings.registry_root / "projects" / "gamma.md"
    page.write_text("# not a page with a name\n", encoding="utf-8")  # no frontmatter: id gamma, no path
    reg = load_registry(settings.registry_root, settings.repo_root, settings.project_roots)
    reg.projects.pop("gamma")  # as if it were skipped
    with pytest.raises(ValueError, match="already exists"):
        register(
            settings.registry_root,
            reg,
            settings.repo_root,
            settings.project_roots,
            root=None,
            path="../gamma",
            name="gamma",
        )
    assert page.read_text(encoding="utf-8") == "# not a page with a name\n"


# --- API ------------------------------------------------------------------------------


def test_api_roots_round_trip(authed, settings, outside):
    view = authed.get("/api/settings/roots").json()
    assert view["roots"] == [] and view["editable"] and view["workspace"]["name"] == "workspace"
    assert sorted(view["workspace"]["projects"]) == ["alpha", "beta", "sub1"]

    r = authed.put("/api/settings/roots", json={"roots": [{"name": "private", "folder": str(outside)}]})
    assert r.status_code == 200, r.text
    assert r.json()["roots"][0]["name"] == "private"
    assert "ARCHEION_ROOTS=" in _env(settings).read_text(encoding="utf-8")

    # Applied without a restart: the new root's projects can be registered at once.
    survey_ = authed.get("/api/registry/roots").json()
    assert [r["name"] for r in survey_] == ["workspace", "private"]
    r = authed.post("/api/registry/projects", json={"root": "private", "path": "omega", "name": "omega"})
    assert r.status_code == 201, r.text
    assert r.json()["project"]["available"] is True
    assert any(p["id"] == "omega" for p in authed.get("/api/registry").json()["projects"])

    # Removing the root makes the project unavailable, and the survey says the root is gone.
    assert authed.put("/api/settings/roots", json={"roots": []}).status_code == 200
    omega = next(p for p in authed.get("/api/registry").json()["projects"] if p["id"] == "omega")
    assert omega["available"] is False
    assert authed.get("/api/registry/roots").json()[-1] == {
        "name": "private",
        "folder": None,
        "granted": False,
        "items": [
            {
                "name": "omega",
                "path": "omega",
                "root": "private",
                "folder": "omega",
                "parent_folder": None,
                "parent": None,
                "registered": "omega",
            }
        ],
    }


def test_api_refuses_bad_roots_and_leaves_env_alone(authed, settings, outside):
    for roots in (
        [{"name": "Bad", "folder": str(outside)}],
        [{"name": "workspace", "folder": str(outside)}],
        [{"name": "gone", "folder": str(outside / "missing")}],
        [{"name": "a1", "folder": str(outside)}, {"name": "a1", "folder": str(outside)}],
        [{"name": "inside", "folder": "docs"}],
    ):
        r = authed.put("/api/settings/roots", json={"roots": roots})
        assert r.status_code == 400 and r.json()["detail"].startswith("Not saved"), (roots, r.text)
    assert not _env(settings).exists()


def test_api_roots_locked_by_the_environment(authed, settings, outside, monkeypatch):
    monkeypatch.setenv("ARCHEION_ROOTS", "")
    view = authed.get("/api/settings/roots").json()
    assert view["editable"] is False and "environment" in view["locked_reason"]
    r = authed.put("/api/settings/roots", json={"roots": [{"name": "private", "folder": str(outside)}]})
    assert r.status_code == 400 and not _env(settings).exists()


def test_api_register_refusal_is_a_400(authed):
    r = authed.post("/api/registry/projects", json={"root": None, "path": "../alpha", "name": "again"})
    assert r.status_code == 400 and "already registered" in r.json()["detail"]
    r = authed.post("/api/registry/projects", json={"root": None, "path": "../gamma", "name": "gamma"})
    assert r.status_code == 201 and r.json()["page"] == "projects/gamma.md"


def test_manage_routes_need_a_session(client):
    assert client.get("/api/settings/roots").status_code == 401
    assert client.put("/api/settings/roots", json={"roots": []}).status_code == 401
    assert client.get("/api/registry/roots").status_code == 401
    assert client.post("/api/registry/projects", json={"path": "x", "name": "x"}).status_code == 401


# --- no root by default (ADR 0012) --------------------------------------------------------


@pytest.fixture
def bare(settings):
    """The defaults: no workspace root and no named roots."""
    from app.config import Settings

    return Settings(**{**settings.model_dump(), "workspace_root": "", "_env_file": None})


def test_nothing_is_granted_by_default(bare):
    from app.config import Settings

    assert Settings.model_fields["workspace_root"].default == ""
    assert bare.workspace_dir is None and bare.project_roots.all() == []
    reg = load_registry(bare.registry_root, bare.repo_root, bare.project_roots)
    assert not any(p.available for p in reg.projects.values())
    assert any("no workspace folder is granted" in w["message"] for w in reg.warnings)
    assert survey(reg, bare.repo_root, bare.project_roots) == []


def test_api_starts_with_no_roots(bare, db, pw, outside):
    from fastapi.testclient import TestClient

    from app.main import create_app
    from tests.conftest import ORIGIN

    client = TestClient(create_app(bare), headers={"Origin": ORIGIN})
    assert client.post("/api/auth/login", json={"password": pw}).status_code == 204
    view = client.get("/api/settings/roots").json()
    assert view["workspace"] is None and view["roots"] == []
    assert client.get("/api/registry/roots").json() == []
    assert client.get("/api/registry").json()["unregistered"] == []

    r = client.put("/api/settings/roots", json={"roots": [{"name": "private", "folder": str(outside)}]})
    assert r.status_code == 200, r.text
    assert [x["name"] for x in client.get("/api/registry/roots").json()] == ["private"]


def test_api_removes_the_workspace_root(authed, settings):
    assert authed.get("/api/settings/roots").json()["workspace"] is not None
    r = authed.put("/api/settings/roots", json={"roots": [], "keep_workspace": False})
    assert r.status_code == 200 and r.json()["workspace"] is None
    env = (settings.repo_root / ".env").read_text(encoding="utf-8")
    assert "ARCHEION_WORKSPACE_ROOT=\n" in env and "ARCHEION_ROOTS=\n" in env
    assert not any(p["available"] for p in authed.get("/api/registry").json()["projects"])
