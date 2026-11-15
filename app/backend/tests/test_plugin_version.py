"""The Archeion plugin's version is recorded in three places that must agree (ADR 0009):
plugin.json, its marketplace entry and its changelog. Its minimum Archeion version must be
one this repo has reached, and the README must state the same minimum."""

from __future__ import annotations

import json
import re

from app.config import read_version
from app.paths import REPO_ROOT

PLUGIN = REPO_ROOT / "plugins" / "archeion"
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def _ver(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split("."))


def _plugin_version() -> str:
    return json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]


def test_plugin_and_marketplace_versions_agree():
    version = _plugin_version()
    assert SEMVER.match(version), version
    market = json.loads((REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    entries = [p for p in market["plugins"] if p["name"] == "archeion"]
    assert len(entries) == 1 and entries[0]["source"] == "./plugins/archeion"
    assert entries[0]["version"] == version, "run scripts/bump-version.ps1 -Target plugin"


def test_plugin_changelog_has_the_current_version_first():
    log = (PLUGIN / "CHANGELOG.md").read_text(encoding="utf-8")
    releases = re.findall(r"^## \[(\d+\.\d+\.\d+)\] - \d{4}-\d{2}-\d{2}$", log, re.M)
    assert releases and releases[0] == _plugin_version(), "the newest release in the changelog"
    assert "## [Unreleased]" in log


def test_minimum_archeion_version_is_reached_and_documented():
    launcher = (PLUGIN / "scripts" / "archeion.ps1").read_text(encoding="utf-8")
    m = re.search(r"^\$MinArcheion = '(\d+\.\d+\.\d+)'", launcher, re.M)
    assert m, "scripts/archeion.ps1 must set $MinArcheion"
    minimum = m.group(1)
    assert _ver(minimum) <= _ver(read_version()), f"the plugin needs Archeion {minimum}"
    assert f"Requires Archeion {minimum} or later" in (PLUGIN / "README.md").read_text(encoding="utf-8")


def test_skills_call_the_launcher():
    for skill in sorted((PLUGIN / "skills").glob("*/SKILL.md")):
        text = skill.read_text(encoding="utf-8")
        assert text.startswith("---\nname: "), skill
        assert '"${CLAUDE_PLUGIN_ROOT}/scripts/archeion.ps1"' in text, skill
