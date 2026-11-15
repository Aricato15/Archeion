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
    root = tmp_path / "repo"
    docs = root / "docs"
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
    _git(root, "init", "-q")
    _git(root, "config", "user.name", "Test Author")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "core.autocrlf", "false")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "docs: initial")
    return root


@pytest.fixture
def settings(repo: Path) -> Settings:
    return Settings(
        _env_file=None,
        repo_root=repo,
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
