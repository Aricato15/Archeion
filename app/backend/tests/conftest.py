from __future__ import annotations

import secrets
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import Database
from app.main import create_app
from app.security import set_pw

ORIGIN = "http://testserver:20301"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def make_pw() -> str:
    # Generated at runtime: a literal would trip the sensitive-content hook.
    return "pw-" + secrets.token_hex(8)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A workspace (tmp/ws) holding this repo (ws/repo) plus sibling projects:
    alpha (registered, own git repo), beta with sub-project collectors/sub1 (registered),
    gamma (not registered)."""
    ws = tmp_path / "ws"
    root = ws / "repo"
    docs = root / "docs"
    _make_projects(ws)
    (docs / "system").mkdir(parents=True)
    (docs / "roadmap").mkdir()
    (docs / "img").mkdir()
    (docs / "README.md").write_text("# Docs\n\nSee [overview](system/overview.md).\n", encoding="utf-8")
    (docs / "system" / "overview.md").write_text(
        "# Overview\n\nIntro line.\n\n## Shape\n\n```mermaid\nflowchart LR\n  A --> B\n```\n\n"
        "## Details\n\nNeedle in here.\n",
        encoding="utf-8",
    )
    (docs / "roadmap" / "roadmap.md").write_text(
        "# Roadmap\n\n_Last updated: 2026-11-15_\n\n## Now\n- Build it, see [plan](2026-11-15-plan.md).\n"
        "\n## Next\n- Use it\n\n## Later\n- Grow it, [outside](../../CLAUDE.md)\n",
        encoding="utf-8",
    )
    (docs / "roadmap" / "2026-11-15-plan.md").write_text("# The plan\n\nSteps.\n", encoding="utf-8")
    (docs / "img" / "pic.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
    (docs / ".hidden.md").write_text("secret-ish\n", encoding="utf-8")
    (root / "outside.md").write_text("# Not a doc\n", encoding="utf-8")
    (root / "VERSION").write_text("9.9.9\n", encoding="utf-8")
    reg = docs / "system" / "projects"
    reg.mkdir(parents=True)
    (docs / "system" / "groups").mkdir()
    (docs / "system" / "groups" / "g1.md").write_text(
        "---\ntitle: Group one\n---\n# Group one\n\nAlpha and beta together.\n", encoding="utf-8"
    )
    (reg / "alpha.md").write_text(
        "---\nname: alpha\npath: ../alpha\ngroup: g1\nports: [20100]\ndepends_on: [beta]\n"
        "verified: 2026-11-15\n---\n# Alpha\n\nThe alpha service.\n",
        encoding="utf-8",
    )
    (reg / "beta.md").write_text("---\npath: ../beta\ngroup: g1\n---\n# Beta\n", encoding="utf-8")
    (reg / "sub1.md").write_text(
        "---\npath: ../beta/collectors/sub1\nparent: beta\n---\n# Sub one\n", encoding="utf-8"
    )
    _git(root, "init", "-q")
    _git(root, "config", "user.name", "Test Author")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "core.autocrlf", "false")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "docs: initial")
    return root


def _make_projects(ws: Path) -> None:
    alpha = ws / "alpha"
    (alpha / "docs").mkdir(parents=True)
    (alpha / "src").mkdir()
    (alpha / "CLAUDE.md").write_text("# alpha\n\nRules for alpha.\n", encoding="utf-8")
    (alpha / "README.md").write_text("# Alpha readme\n\nSee [api](docs/api.md).\n", encoding="utf-8")
    (alpha / "docs" / "api.md").write_text(
        "# Alpha API\n\n```mermaid\nflowchart LR\n  X --> Y\n```\n\nAlpha haystack.\n", encoding="utf-8"
    )
    (alpha / "docs" / "roadmap.md").write_text("# Roadmap\n\n## Now\n- Ship alpha\n", encoding="utf-8")
    (alpha / "src" / "code.md").write_text("# not served\n", encoding="utf-8")
    (alpha / ".env").write_text("NOT=served\n", encoding="utf-8")
    _git(alpha, "init", "-q")
    _git(alpha, "config", "user.name", "Alpha Author")
    _git(alpha, "config", "user.email", "alpha@example.com")
    _git(alpha, "config", "core.autocrlf", "false")
    _git(alpha, "add", "-A")
    _git(alpha, "commit", "-q", "-m", "feat: alpha")
    beta = ws / "beta"
    sub1 = beta / "collectors" / "sub1"
    sub1.mkdir(parents=True)
    (beta / "CLAUDE.md").write_text("# beta\n", encoding="utf-8")
    (sub1 / "pyproject.toml").write_text("[project]\nname='sub1'\n", encoding="utf-8")
    (sub1 / "README.md").write_text("# Sub one readme\n", encoding="utf-8")
    (ws / "gamma").mkdir()
    (ws / "gamma" / "CLAUDE.md").write_text("# gamma\n", encoding="utf-8")
    (ws / "_shared").mkdir()
    (ws / "_shared" / "CLAUDE.md").write_text("# skipped\n", encoding="utf-8")


@pytest.fixture
def settings(repo: Path) -> Settings:
    return Settings(
        _env_file=None,
        repo_root=repo,
        workspace_root="..",
        db_path=str(repo / "data" / "test.db"),
        watch_docs=False,
        feedback_poll_seconds=0.05,
        login_fail_delay_seconds=0,
        extra_allowed_hosts=["testserver"],
    )


@pytest.fixture
def db(settings: Settings) -> Database:
    database = Database(settings.db_file)
    database.init()
    return database


@pytest.fixture
def pw(db: Database) -> str:
    value = make_pw()
    with db.conn() as conn:
        set_pw(conn, value)
    return value


@pytest.fixture
def app(settings: Settings, db: Database):
    return create_app(settings)


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app, headers={"Origin": ORIGIN})


@pytest.fixture
def authed(client: TestClient, pw: str) -> TestClient:
    r = client.post("/api/auth/login", json={"password": pw})
    assert r.status_code == 204, r.text
    return client
