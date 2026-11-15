"""Project sources: read-only access to a registered project's own docs (ADR 0006)."""

from __future__ import annotations

import subprocess

import pytest


def test_sources_and_registry_endpoints(authed):
    ids = {s["id"] for s in authed.get("/api/sources").json()}
    assert ids == {"archeion", "alpha", "beta", "sub1"}
    reg = authed.get("/api/registry").json()
    assert {p["id"] for p in reg["projects"]} == {"alpha", "beta", "sub1"}
    assert "dir" not in reg["projects"][0]  # no machine paths leave the backend
    assert [u["name"] for u in reg["unregistered"]] == ["gamma"]


def test_project_tree_shows_only_served_files(authed):
    tree = authed.get("/api/docs/tree", params={"source": "alpha"}).json()

    def files(node):
        return [node["path"]] if node["type"] == "file" else [p for c in node["children"] for p in files(c)]

    assert sorted(files(tree)) == ["CLAUDE.md", "README.md", "docs/api.md", "docs/roadmap.md"]


def test_project_file(authed):
    r = authed.get("/api/docs/file", params={"source": "alpha", "path": "docs/api.md"})
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "alpha" and body["content"].startswith("# Alpha API") and body["dirty"] is False
    assert authed.get("/api/docs/file", params={"source": "alpha", "path": "CLAUDE.md"}).status_code == 200


@pytest.mark.parametrize(
    "path",
    [
        "src/code.md",
        ".env",
        "../repo/docs/README.md",
        "docs/../src/code.md",
        "pyproject.toml",
        "CLAUDE.local.md",
    ],
)
def test_project_files_outside_the_allowlist_are_refused(authed, path):
    r = authed.get("/api/docs/file", params={"source": "alpha", "path": path})
    assert r.status_code in (400, 404)
    assert "not served" not in r.text and "NOT=served" not in r.text


def test_unknown_source(authed):
    r = authed.get("/api/docs/file", params={"source": "nope", "path": "README.md"})
    assert r.status_code == 404 and "nope" in r.json()["detail"]


def test_sub_project_is_its_own_source(authed):
    r = authed.get("/api/docs/file", params={"source": "sub1", "path": "README.md"})
    assert r.json()["content"].strip() == "# Sub one readme"  # Windows writes CRLF
    # beta doesn't serve its sub-project's files
    assert (
        authed.get(
            "/api/docs/file", params={"source": "beta", "path": "collectors/sub1/README.md"}
        ).status_code
        == 400
    )


def test_project_history_uses_its_own_repo(authed, repo):
    alpha = repo.parent / "alpha"
    (alpha / "docs" / "api.md").write_text("# Alpha API v2\n", encoding="utf-8")
    assert (
        authed.get("/api/docs/file", params={"source": "alpha", "path": "docs/api.md"}).json()["dirty"]
        is True
    )
    diff = authed.get(
        "/api/docs/diff", params={"source": "alpha", "path": "docs/api.md", "rev": "WORKTREE"}
    ).json()
    assert "+# Alpha API v2" in diff["diff"]
    subprocess.run(["git", "-C", str(alpha), "commit", "-qam", "docs: v2"], check=True)
    hist = authed.get("/api/docs/history", params={"source": "alpha", "path": "docs/api.md"}).json()
    assert [c["subject"] for c in hist] == ["docs: v2", "feat: alpha"]
    assert all("example.com" not in str(c) for c in hist)
    old = authed.get(
        "/api/docs/at", params={"source": "alpha", "path": "docs/api.md", "rev": hist[1]["short"]}
    ).json()
    assert old["content"].startswith("# Alpha API\n")


def test_project_without_git_is_never_dirty(authed):
    r = authed.get("/api/docs/file", params={"source": "sub1", "path": "README.md"})
    # sub1 lives in beta, which isn't a git repo in the fixture
    assert r.json()["dirty"] is False
    assert authed.get("/api/docs/history", params={"source": "sub1", "path": "README.md"}).json() == []


def test_registry_frontmatter_is_returned(authed):
    body = authed.get("/api/docs/file", params={"path": "system/projects/alpha.md"}).json()
    assert body["frontmatter"]["depends_on"] == ["beta"]
    assert authed.get("/api/docs/file", params={"path": "README.md"}).json()["frontmatter"] is None
