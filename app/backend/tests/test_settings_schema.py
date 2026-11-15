"""scripts/settings.schema.json (used by configure.bat) and the backend's Settings must agree."""

from __future__ import annotations

import json

from app.config import Settings
from app.paths import REPO_ROOT

SCHEMA = json.loads((REPO_ROOT / "scripts" / "settings.schema.json").read_text(encoding="utf-8"))
SETTINGS = [s for g in SCHEMA["groups"] for s in g["settings"]]
TYPES = {"host", "port", "int", "number", "relpath", "string", "roots", "secret"}


def test_schema_entries_are_well_formed():
    names = [s["name"] for s in SETTINGS]
    assert len(names) == len(set(names)), "duplicate setting names"
    for s in SETTINGS:
        assert s["name"].startswith("ARCHEION_"), s["name"]
        assert s["type"] in TYPES, s
        assert s["description"].strip(), s["name"]
        if s["type"] == "secret":
            assert s.get("default", "") == "", f"{s['name']}: secrets can't have a default"
        else:
            assert isinstance(s["default"], str), s["name"]


def test_schema_defaults_match_backend_defaults():
    fields = Settings.model_fields
    for s in SETTINGS:
        key = s["name"].removeprefix("ARCHEION_").lower()
        if key not in fields:
            continue  # a setting only the scripts or the frontend read
        default = fields[key].default
        assert str(default) == s["default"] or (
            isinstance(default, float) and float(s["default"]) == default
        ), f"{s['name']}: schema default {s['default']!r} != backend default {default!r}"


def test_every_env_setting_of_the_backend_is_in_the_schema():
    in_schema = {s["name"].removeprefix("ARCHEION_").lower() for s in SETTINGS}
    # Fields deliberately not configurable through .env (tests set them directly).
    internal = {
        "repo_root",
        "watch_docs",
        "feedback_poll_seconds",
        "login_max_failures",
        "login_window_seconds",
        "login_fail_delay_seconds",
        "extra_allowed_hosts",
    }
    missing = set(Settings.model_fields) - in_schema - internal
    assert not missing, f"add these to scripts/settings.schema.json: {sorted(missing)}"
