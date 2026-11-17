from __future__ import annotations

import os
import subprocess

import pytest

from app.paths import DocNotFound, DocPathError, resolve_doc_path, validate_rel_path

BAD_PATHS = [
    "../outside.md",
    "system/../../outside.md",
    "/etc/passwd",
    "C:/Windows/win.ini",  # sensitive-ok: test input, not a real path
    "system\\overview.md",
    ".hidden.md",
    "system//overview.md",
    "README.md\x00.png",
    "",
]


@pytest.mark.parametrize("bad", BAD_PATHS)
def test_validate_rejects(bad):
    with pytest.raises(DocPathError):
        validate_rel_path(bad)


def test_resolve(repo):
    docs = repo / "docs"
    assert resolve_doc_path(docs, "system/overview.md").name == "overview.md"
    with pytest.raises(DocNotFound):
        resolve_doc_path(docs, "nope.md")
    with pytest.raises(DocPathError):
        resolve_doc_path(docs, "img/pic.svg", allowed={".md"})
    (docs / "notes.txt").write_text("x", encoding="utf-8")
    with pytest.raises(DocPathError):
        resolve_doc_path(docs, "notes.txt")


def test_symlink_out_of_docs_rejected(repo):
    link = repo / "docs" / "escape.md"
    try:
        os.symlink(repo / "outside.md", link)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not available")
    with pytest.raises(DocPathError):
        resolve_doc_path(repo / "docs", "escape.md")


def test_tree(authed):
    tree = authed.get("/api/docs/tree").json()
    names = [c["name"] for c in tree["children"]]
    assert names[:3] == ["img", "roadmap", "system"]  # dirs first
    assert "README.md" in names
    assert ".hidden.md" not in names


def test_file(authed):
    r = authed.get("/api/docs/file", params={"path": "system/overview.md"})
    assert r.status_code == 200
    body = r.json()
    assert body["content"].startswith("# Overview")
    assert body["dirty"] is False
    assert len(body["sha"]) == 64


@pytest.mark.parametrize("bad", ["../outside.md", "..%2foutside.md", "/etc/passwd", ".hidden.md"])
def test_file_rejects_traversal(authed, bad):
    r = authed.get("/api/docs/file", params={"path": bad})
    assert r.status_code in (400, 404)
    assert "Not a doc" not in r.text


def test_file_missing_and_wrong_type(authed):
    assert authed.get("/api/docs/file", params={"path": "missing.md"}).status_code == 404
    assert authed.get("/api/docs/file", params={"path": "img/pic.svg"}).status_code == 400


def test_dirty_and_worktree_diff(authed, repo):
    path = repo / "docs" / "README.md"
    path.write_text(path.read_text(encoding="utf-8") + "\nNew line.\n", encoding="utf-8")
    assert authed.get("/api/docs/file", params={"path": "README.md"}).json()["dirty"] is True
    diff = authed.get("/api/docs/diff", params={"path": "README.md", "rev": "WORKTREE"}).json()["diff"]
    assert "+New line." in diff


def test_untracked_doc_diff(authed, repo):
    (repo / "docs" / "new.md").write_text("# New\n", encoding="utf-8")
    diff = authed.get("/api/docs/diff", params={"path": "new.md", "rev": "WORKTREE"}).json()["diff"]
    assert "--- /dev/null" in diff and "+# New" in diff


def test_raw_image(authed):
    r = authed.get("/api/docs/raw", params={"path": "img/pic.svg"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")
    assert "sandbox" in r.headers["content-security-policy"]
    assert authed.get("/api/docs/raw", params={"path": "README.md"}).status_code == 400


def test_history_diff_and_at(authed, repo):
    path = repo / "docs" / "README.md"
    path.write_text("# Docs v2\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "commit", "-qam", "docs: second"], check=True)
    hist = authed.get("/api/docs/history", params={"path": "README.md"}).json()
    assert [c["subject"] for c in hist] == ["docs: second", "docs: initial"]
    assert hist[0]["author_name"] == "Test Author"
    assert all("example.com" not in str(c) for c in hist)  # no emails leave the backend

    rev = hist[0]["rev"]
    diff = authed.get("/api/docs/diff", params={"path": "README.md", "rev": rev}).json()["diff"]
    assert "+# Docs v2" in diff
    old = authed.get("/api/docs/at", params={"path": "README.md", "rev": hist[1]["short"]}).json()
    assert old["content"].startswith("# Docs\n")


@pytest.mark.parametrize("rev", ["HEAD", "main", "--output=x", "abc", "deadbeef;rm"])
def test_invalid_revs(authed, rev):
    assert authed.get("/api/docs/diff", params={"path": "README.md", "rev": rev}).status_code == 400
    assert authed.get("/api/docs/at", params={"path": "README.md", "rev": rev}).status_code == 400


def test_unknown_rev(authed):
    r = authed.get("/api/docs/at", params={"path": "README.md", "rev": "0" * 40})
    assert r.status_code == 404


def test_roadmap(authed):
    data = authed.get("/api/roadmap").json()
    rm = data["cross"]
    by_project = {p["project"]: p["roadmap"] for p in data["projects"]}
    assert by_project["alpha"]["now"][0]["text"] == "Ship alpha"
    assert by_project["beta"] is None
    assert rm["updated"] == "2026-11-15"
    assert rm["now"][0]["links"] == [{"label": "plan", "path": "roadmap/2026-11-15-plan.md"}]
    assert rm["next"][0]["text"] == "Use it"
    assert rm["later"][0]["links"] == []  # links outside docs/ are dropped
    assert rm["plans"] == [{"path": "roadmap/2026-11-15-plan.md", "title": "The plan", "date": "2026-11-15"}]


def test_diagrams(authed):
    d = authed.get("/api/diagrams").json()
    assert {(x["source"], x["path"]) for x in d} == {
        ("archeion", "system/overview.md"),
        ("alpha", "docs/api.md"),
    }
    d = authed.get("/api/diagrams", params={"source": "archeion"}).json()
    assert d == [
        {
            "source": "archeion",
            "path": "system/overview.md",
            "heading": "Shape",
            "index": 0,
            "line": 7,
            "code": "flowchart LR\n  A --> B",
        }
    ]


def test_search(authed):
    hits = authed.get("/api/search", params={"q": "needle"}).json()
    assert hits == [
        {"source": "archeion", "path": "system/overview.md", "line": 14, "snippet": "Needle in here."}
    ]
    assert authed.get("/api/search", params={"q": "haystack"}).json()[0]["source"] == "alpha"
    assert authed.get("/api/search", params={"q": "x"}).status_code == 422


def test_changelog_is_read_from_the_repo_root(authed, settings):
    assert authed.get("/api/changelog").status_code == 404
    (settings.repo_root / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [1.0.0] - 2026-01-01\n", encoding="utf-8"
    )
    assert "## [1.0.0]" in authed.get("/api/changelog").json()["content"]


def test_changelog_needs_login(client):
    assert client.get("/api/changelog").status_code == 401
