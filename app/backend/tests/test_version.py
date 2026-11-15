"""VERSION at the repo root is the single source of truth (ADR 0005). The manifests must match."""

from __future__ import annotations

import json
import re
import tomllib

from app.config import read_version
from app.paths import REPO_ROOT

SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")


def test_version_is_semver():
    assert SEMVER.match(read_version())


def test_backend_manifest_matches():
    data = tomllib.loads((REPO_ROOT / "app" / "backend" / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["version"] == read_version()


def test_frontend_manifests_match():
    frontend = REPO_ROOT / "app" / "frontend"
    pkg = json.loads((frontend / "package.json").read_text(encoding="utf-8"))
    assert pkg["version"] == read_version()
    lock_path = frontend / "package-lock.json"
    if lock_path.exists():
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        assert lock["version"] == read_version()
        assert lock["packages"][""]["version"] == read_version()


def test_changelog_mentions_version():
    changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [{read_version()}]" in changelog
