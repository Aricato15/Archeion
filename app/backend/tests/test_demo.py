"""The example project (ADR 0030): committed demo data, read from its own folder, and the rule that
nothing about it is written or reaches a database or Claude."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.paths import REPO_ROOT
from app.services import demo
from app.services import designs as dz
from app.services import feedback as fb
from app.services.registry import load_registry


@pytest.fixture
def home(tmp_path: Path) -> tuple[Path, Path]:
    """A repo holding the real demo folder, and an empty private registry next to it."""
    repo = tmp_path / "repo"
    shutil.copytree(REPO_ROOT / demo.DEMO_DIR, repo / demo.DEMO_DIR)
    registry = repo / "registry"
    registry.mkdir()
    return repo, registry


def test_the_shipped_demo_is_there():
    assert (demo.registry_root(REPO_ROOT) / "projects" / f"{demo.DEMO_PROJECT}.md").is_file()
    assert (REPO_ROOT / demo.DEMO_DIR / demo.DEMO_PROJECT / "README.md").is_file()


def test_the_demo_loads_as_a_project_without_touching_the_registry(home):
    repo, registry = home
    reg = load_registry(registry, repo, repo.parent)
    project = reg.projects[demo.DEMO_PROJECT]
    assert project.demo and project.available and project.title == "Example-Project"
    assert project.inbox_edits is False
    assert not reg.warnings
    assert list(registry.iterdir()) == []  # nothing was written into the private registry


def test_the_demo_design_is_read_from_its_own_folder(home):
    repo, _ = home
    root = demo.registry_root(repo)
    summary = dz.summary(dz.get(root, demo.DEMO_PROJECT))
    assert summary["stage"] == "approved" and summary["checklist"]["total"] == 7
    assert summary["checklist"]["pending"] == 3


def test_a_page_cannot_point_outside_the_demo_folder(home):
    repo, registry = home
    (registry / "projects").mkdir()
    (registry / "projects" / "sneaky.md").write_text(
        f"---\nname: sneaky\npath: {demo.DEMO_DIR}/../registry\n---\n# Sneaky\n",
        encoding="utf-8",
    )
    reg = load_registry(registry, repo, repo.parent)
    assert reg.projects["sneaky"].dir is None and not reg.projects["sneaky"].available


def test_nothing_about_the_demo_reaches_the_database(db):
    anchor = {"task": {"kind": "design", "project": demo.DEMO_PROJECT}}
    with db.conn() as conn:
        with pytest.raises(demo.DemoError):
            fb.create(conn, kind="prompt", body="hi", source=demo.DEMO_PROJECT)
        with pytest.raises(demo.DemoError):
            fb.create(conn, kind="prompt", body="hi", anchor=anchor)
        assert fb.list_threads(conn) == []
        ok = fb.create(conn, kind="prompt", body="a real note")  # other projects are unaffected
        assert ok["status"] == "open"


def test_a_follow_up_in_a_demo_thread_is_refused(db):
    # A thread can't start about the demo, so a follow-up can only meet a demo root if the row was
    # written some other way: simulate that.
    with db.conn() as conn:
        conn.execute(
            "INSERT INTO feedback (kind, source, body, created_at, updated_at, status, thread_id)"
            " VALUES ('prompt', ?, 'x', 'now', 'now', 'resolved', 1)",
            (demo.DEMO_PROJECT,),
        )
        conn.commit()
        with pytest.raises(demo.DemoError):
            fb.create(conn, kind="prompt", body="more", parent_id=1)


def test_the_api_refuses_feedback_about_the_demo(authed):
    r = authed.post("/api/feedback", json={"kind": "prompt", "body": "hello", "source": demo.DEMO_PROJECT})
    assert r.status_code == 400 and "demo data" in r.text


def test_the_demo_design_and_glossary_are_read_only(authed):
    base = f"/api/designs/{demo.DEMO_PROJECT}/main"
    # In the test workspace the demo folder isn't there, so the write is refused before anything is looked up.
    r = authed.post(f"{base}/checklist/confirm")
    assert r.status_code == 400 and "demo data" in r.text
    r = authed.post(f"/api/glossary/{demo.DEMO_PROJECT}", json={"term": "x", "definition": "y"})
    assert r.status_code == 400 and "demo data" in r.text
