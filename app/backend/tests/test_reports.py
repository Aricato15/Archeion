"""Project PDF reports (ADR 0025): the catalog, presets and validation, and the CLI."""

from __future__ import annotations

import json

import pytest

from app.__main__ import main
from app.services import reports as rp
from app.services import studies as st
from app.services.sources import SourceManager

from .test_studies import model


@pytest.fixture
def manager(settings) -> SourceManager:
    return SourceManager(
        settings.docs_root,
        settings.registry_root,
        settings.repo_root,
        settings.workspace_dir,
        settings.project_roots,
    )


def ids(entries: list[dict], only_available: bool = False) -> list[str]:
    return [e["id"] for e in entries if e["available"] or not only_available]


def by_id(entries: list[dict]) -> dict[str, dict]:
    return {e["id"]: e for e in entries}


def test_catalog_without_a_study_lists_it_as_unavailable(manager, settings):
    entries = by_id(rp.catalog(manager, settings.registry_root, "alpha"))
    assert entries["overview.facts"]["available"]
    assert entries["overview.notes"]["available"]  # the page has a paragraph after its title
    assert not entries["study.map"]["available"] and entries["study.map"]["reason"] == "no study yet"
    assert not entries["design.brief"]["available"]
    assert not entries["glossary.terms"]["available"]
    assert entries["system.group"]["available"] and entries["system.dependencies"]["available"]


def test_catalog_with_a_study_has_a_diagram_per_sub_system(manager, settings):
    st.save(settings.registry_root, st.parse(model()), notes="# Notes\n\nBody.\n")
    entries = by_id(rp.catalog(manager, settings.registry_root, "alpha"))
    assert entries["study.map"]["available"]
    sub = entries["study.sub:api"]  # `routes` has `api` as its parent
    assert sub["parent"] == "study.map" and sub["kind"] == "diagram"
    assert "study.sub:db" not in entries and "study.sub:routes" not in entries
    for wanted in ("study.flow:read", "study.schema", "study.interfaces", "study.notes"):
        assert entries[wanted]["available"], wanted


def test_catalog_lists_the_projects_docs(manager, settings, repo):
    (repo.parent / "alpha" / "README.md").write_text("# Alpha\n", encoding="utf-8")
    manager.reload()
    entries = rp.catalog(manager, settings.registry_root, "alpha")
    assert "docs:README.md" in ids(entries, only_available=True)


def test_catalog_unknown_project(manager, settings):
    with pytest.raises(KeyError):
        rp.catalog(manager, settings.registry_root, "nope")


def standard(entries: list[dict], *wanted: str, name: str = "full") -> dict:
    return {"name": name, "mode": "standard", "sections": [{"id": w} for w in wanted]}


def test_a_valid_standard_preset_keeps_the_order_and_fills_the_options(manager, settings):
    entries = rp.catalog(manager, settings.registry_root, "alpha")
    preset = rp.validate_preset(standard(entries, "system.dependencies", "overview.facts"), entries)
    assert [s["id"] for s in preset["sections"]] == ["system.dependencies", "overview.facts"]
    assert preset["options"] == rp.DEFAULT_OPTIONS and "prompt" not in preset


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ({"name": "Bad Name", "sections": [{"id": "overview.facts"}]}, "name"),
        ({"name": "x", "sections": []}, "at least one"),
        ({"name": "x", "sections": [{"id": "overview.facts"}, {"id": "overview.facts"}]}, "twice"),
        ({"name": "x", "sections": [{"id": "nope.nope"}]}, "no section"),
        ({"name": "x", "sections": [{"id": "study.map"}]}, "unavailable"),
        ({"name": "x", "mode": "other", "sections": [{"id": "overview.facts"}]}, "mode"),
        ({"name": "x", "options": {"page_size": "A0"}, "sections": [{"id": "overview.facts"}]}, "page_size"),
        ({"name": "x", "options": {"color": 1}, "sections": [{"id": "overview.facts"}]}, "unknown"),
        ({"name": "x", "prompt": "be brief", "sections": [{"id": "overview.facts"}]}, "guided"),
        (
            {
                "name": "x",
                "sections": [{"id": "authored:summary", "title": "T", "body": "B", "cites": ["x"]}],
            },
            "only a guided report",
        ),
    ],
)
def test_invalid_presets_are_refused(manager, settings, raw, message):
    entries = rp.catalog(manager, settings.registry_root, "alpha")
    with pytest.raises(rp.ReportError, match=message):
        rp.validate_preset(raw, entries)


def guided(*sections: dict) -> dict:
    return {
        "name": "exec",
        "mode": "guided",
        "prompt": "For executives",
        "outline": "1. overview",
        "sections": list(sections),
    }


def test_guided_authored_sections_need_a_title_a_body_and_citations(manager, settings):
    entries = rp.catalog(manager, settings.registry_root, "alpha")
    good = {
        "id": "authored:summary",
        "title": "Summary",
        "body": "Alpha owns items.",
        "cites": ["overview.facts"],
    }
    preset = rp.validate_preset(guided(good, {"id": "overview.facts"}), entries)
    assert preset["sections"][0]["cites"] == ["overview.facts"] and preset["prompt"] == "For executives"
    for bad, message in (
        ({**good, "cites": []}, "cites at least one"),
        ({**good, "cites": ["study.map"]}, "unavailable"),
        ({**good, "cites": ["nope"]}, "isn't in the catalog"),
        ({**good, "body": ""}, "body"),
        ({**good, "id": "authored:Bad Slug"}, "slug"),
    ):
        with pytest.raises(rp.ReportError, match=message):
            rp.validate_preset(guided(bad), entries)


def test_presets_round_trip_and_delete(manager, settings):
    root = settings.registry_root
    entries = rp.catalog(manager, root, "alpha")
    assert rp.list_presets(root, "alpha") == []
    rp.save_preset(root, "alpha", standard(entries, "overview.facts"), entries)
    rp.save_preset(root, "alpha", standard(entries, "overview.facts", "overview.notes"), entries)  # replaces
    assert [len(p["sections"]) for p in rp.list_presets(root, "alpha")] == [2]
    assert rp.get_preset(root, "alpha", "full")["mode"] == "standard"
    rp.delete_preset(root, "alpha", "full")
    with pytest.raises(rp.PresetNotFound):
        rp.get_preset(root, "alpha", "full")
    with pytest.raises(rp.PresetNotFound):
        rp.delete_preset(root, "alpha", "full")


def test_project_name_cannot_leave_the_folder(settings):
    with pytest.raises(rp.ReportError):
        rp.list_presets(settings.registry_root, "../x")


def test_a_preset_is_stored_in_the_registry_only(manager, settings, repo):
    entries = rp.catalog(manager, settings.registry_root, "alpha")
    rp.save_preset(settings.registry_root, "alpha", standard(entries, "overview.facts"), entries)
    assert (settings.registry_root / "reports" / "alpha" / "presets.json").is_file()
    assert not (repo.parent / "alpha" / "reports").exists()


def test_find_browser_uses_the_override_only_when_it_exists(tmp_path):
    exe = tmp_path / "edge.exe"
    exe.write_text("", encoding="utf-8")
    assert rp.find_browser(str(exe)) == exe
    assert rp.find_browser(str(tmp_path / "missing.exe")) is None


def test_preflight_reports_a_missing_browser(manager, settings, tmp_path):
    result = rp.preflight(manager, settings.registry_root, "alpha", str(tmp_path / "missing.exe"))
    assert not result["ok"] and not result["browser"] and "Edge" in result["problems"][0]
    exe = tmp_path / "edge.exe"
    exe.write_text("", encoding="utf-8")
    assert rp.preflight(manager, settings.registry_root, "alpha", str(exe))["ok"]


def test_cli(settings, capsys, tmp_path):
    assert main(["report", "catalog", "alpha"], settings) == 0
    assert "[x] study.map: Component map (top level)  (no study yet)" in capsys.readouterr().out
    assert main(["report", "default", "alpha", "--name", "all"], settings) == 0
    preset = json.loads(capsys.readouterr().out)
    assert preset["name"] == "all" and {"id": "overview.facts"} in preset["sections"]
    path = tmp_path / "preset.json"
    path.write_text(json.dumps(preset), encoding="utf-8")
    assert main(["report", "validate", "alpha", "--file", str(path)], settings) == 0
    assert main(["report", "preset", "save", "alpha", "--file", str(path)], settings) == 0
    assert main(["report", "preset", "list", "alpha"], settings) == 0
    assert "all (standard)" in capsys.readouterr().out
    assert main(["report", "preset", "show", "alpha", "all"], settings) == 0
    assert main(["report", "preset", "delete", "alpha", "all"], settings) == 0
    assert main(["report", "preset", "show", "alpha", "all"], settings) == 1
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"name": "x", "sections": [{"id": "nope"}]}), encoding="utf-8")
    assert main(["report", "validate", "alpha", "--file", str(bad)], settings) == 1
    assert main(["report", "catalog", "nope"], settings) == 1
    capsys.readouterr()
    assert main(["report", "preflight", "alpha", "--json"], settings) in (0, 1)
    assert json.loads(capsys.readouterr().out)["project"] == "alpha"
