"""The composed study of a group (ADR 0027): members' studies read, not redone."""

from __future__ import annotations

import json

import pytest

from app.__main__ import main
from app.services import studies as st
from app.services import study_compose
from app.services.registry import load_registry

from .test_studies import model


def _load(settings):
    return load_registry(settings.registry_root, settings.repo_root, settings.workspace_dir)


def _page(settings, name: str, text: str) -> None:
    (settings.registry_root / "projects" / f"{name}.md").write_text(text, encoding="utf-8")


@pytest.fixture
def top(settings):
    """A group `top` in a folder of its own, with two members in folders inside it."""
    gamma = settings.repo_root.parent / "gamma"
    for member in ("ma", "mb"):
        (gamma / member).mkdir(exist_ok=True)
        (gamma / member / f"{member}.py").write_text("x = 1\n", encoding="utf-8")
    (gamma / "own.py").write_text("y = 2\n", encoding="utf-8")
    _page(settings, "top", "---\npath: ../gamma\ntype: group\nports: [20100]\n---\n# Top\n")
    _page(settings, "m-a", "---\npath: ../gamma/ma\ngroup: top\nports: [20201]\n---\n# A\n")
    _page(
        settings, "m-b", "---\npath: ../gamma/mb\ngroup: top\nports: [20202]\ndepends_on: [m-a]\n---\n# B\n"
    )


def _save(settings, project: str, **changes) -> None:
    data = model(project)
    data["meta"].update(changes.pop("meta", {}))
    data.update(changes)
    st.save(settings.registry_root, st.parse(data))


def test_a_group_with_no_studies_has_nothing_to_compose(top, settings):
    out = study_compose.compose(settings.registry_root, _load(settings), "top")
    assert out["model"] is None and out["own"] is None
    assert [m["project"] for m in out["members"]] == ["m-a", "m-b"]
    assert not any(m["has_study"] for m in out["members"])


def test_members_studies_are_put_inside_their_containers(top, settings):
    _save(settings, "m-a")
    _save(settings, "m-b")
    out = study_compose.compose(settings.registry_root, _load(settings), "top")
    assert out["problems"] == [] and out["model"] is not None
    comps = {c["id"]: c for c in out["model"]["components"]}
    assert comps["m-a"]["kind"] == "service" and comps["m-b"]["kind"] == "service"
    assert comps["m-a__api"]["parent"] == "m-a" and comps["m-a__routes"]["parent"] == "m-a__api"
    ids = {c["id"] for c in out["model"]["components"]}
    assert "m-a__db" in ids and "m-b__db" in ids and "api" not in ids  # nothing un-namespaced
    entities = {e["id"]: e for e in out["model"]["entities"]}
    assert entities["m-a__tags"]["fields"][0]["fk"] == "m-a__items.id"
    assert entities["m-a__items"]["store"] == "m-a__db"
    assert out["members"][0]["date"] == "2026-11-16" and out["members"][0]["valid"]


def test_a_member_without_a_study_is_an_empty_container(top, settings):
    _save(settings, "m-a")
    out = study_compose.compose(settings.registry_root, _load(settings), "top")
    comps = {c["id"]: c for c in out["model"]["components"]}
    assert comps["m-b"]["summary"] == "No study of this member yet."
    assert [m["has_study"] for m in out["members"]] == [True, False]


def test_the_members_study_wins_and_the_difference_is_reported(top, settings):
    _save(settings, "m-a")
    own = {
        "components": [
            {"id": "m-a", "name": "Member A", "kind": "service", "summary": "What the top level says"},
            {"id": "gateway", "name": "Gateway", "kind": "service"},
        ],
        "relations": [{"id": "g1", "from": "gateway", "to": "m-a", "kind": "http"}],
        "entities": [],
        "interfaces": {"exposes": [], "calls": []},
        "flows": [],
        "states": [],
        "activities": [],
        "findings": [],
        "meta": {"summary": "Top level"},
    }
    _save(settings, "top", **own)
    out = study_compose.compose(settings.registry_root, _load(settings), "top")
    assert out["overridden"] == [
        {
            "component": "m-a",
            "name": "Member A",
            "group_summary": "What the top level says",
            "member_summary": "The alpha service.",
            "differs": True,
        }
    ]
    comps = {c["id"]: c for c in out["model"]["components"]}
    assert (
        comps["m-a"]["summary"] == "The alpha service." and "gateway" in comps
    )  # the member's, not the group's
    assert any(r["from"] == "gateway" and r["to"] == "m-a" for r in out["model"]["relations"])


def test_links_found_in_the_code_become_relations_between_members(top, settings):
    _save(settings, "m-a")
    calls = {
        "interfaces": {
            "exposes": [],
            "calls": [{"id": "c1", "kind": "http", "port": 20201, "method": "GET", "path": "/x"}],
        }
    }
    _save(settings, "m-b", **calls)
    out = study_compose.compose(settings.registry_root, _load(settings), "top")
    links = [r for r in out["model"]["relations"] if r["from"] == "m-b" and r["to"] == "m-a"]
    assert links and links[0]["kind"] == "http" and "GET" in (links[0]["label"] or "")


def test_the_composed_endpoint(top, authed, settings):
    _save(settings, "m-a")
    r = authed.get("/api/studies/top/composed")
    assert r.status_code == 200
    body = r.json()
    assert body["model"] and body["members"][0]["project"] == "m-a" and "commits_since" in body["members"][0]
    assert authed.get("/api/studies/alpha/composed").status_code == 409  # not a group
    assert authed.get("/api/studies/nope/composed").status_code == 404


def test_a_groups_scan_leaves_its_members_folders_out(top, settings, capsys):
    assert main(["study", "scan", "top", "--json"], settings) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["excluded"] == ["ma", "mb"]
    assert [m["path"] for m in data["modules"]] == ["own.py"]
    assert main(["study", "scan", "top", "--json", "--include-members"], settings) == 0
    everything = json.loads(capsys.readouterr().out)
    assert everything["excluded"] == [] and len(everything["modules"]) == 3


def test_a_study_may_record_what_it_left_out():
    data = model("top")
    data["meta"]["excluded"] = ["ma", "mb"]
    assert st.parse(data).meta.excluded == ["ma", "mb"]


# --- break a group down and restudy it (ADR 0027, phase 5) ----------------------------------


@pytest.fixture
def bare(settings):
    """A group `top` whose folder holds three subsystems that aren't registered yet."""
    gamma = settings.repo_root.parent / "gamma"
    for folder in ("ma", "mb", "nested", "docs"):
        (gamma / folder).mkdir(exist_ok=True)
        (gamma / folder / "x.py").write_text("x = 1\n", encoding="utf-8")
    (gamma / "nested" / ".git").write_text("gitdir: x\n", encoding="utf-8")
    _page(settings, "top", "---\npath: ../gamma\ntype: group\n---\n# Top\n")
    own = {
        "components": [
            {"id": "svc-a", "name": "A", "kind": "service", "paths": ["ma/x.py"]},
            {"id": "svc-a-db", "name": "A db", "kind": "module", "parent": "svc-a", "paths": ["ma/db.py"]},
            {"id": "svc-b", "name": "B", "kind": "service", "paths": ["mb/x.py"]},
            {"id": "sub", "name": "Sub", "kind": "package", "paths": ["nested/x.py"]},
            {"id": "docs-site", "name": "Docs", "kind": "ui", "paths": ["docs/x.py"]},
            {"id": "top-file", "name": "Top file", "kind": "module", "paths": ["own.py"]},
        ],
        "relations": [],
        "entities": [],
        "interfaces": {"exposes": [], "calls": []},
        "flows": [],
        "states": [],
        "activities": [],
        "findings": [],
    }
    _save(settings, "top", **own)


def _plan(settings):
    from app.services.registry import plan_break_down

    reg = _load(settings)
    snap = next(iter(st.snapshots(settings.registry_root, "top")))
    return plan_break_down(settings.registry_root, reg, "top", st.load(snap)[0])


def test_the_groups_study_suggests_folders_as_members(bare, settings):
    plan = {p["folder"]: p for p in _plan(settings)}
    assert sorted(plan) == ["ma", "mb", "nested"]  # not docs (skipped), not a file at the top
    assert plan["ma"]["type"] == "module" and plan["ma"]["components"] == ["svc-a"]
    assert plan["nested"]["type"] == "project" and plan["nested"]["name"] == "nested"


def test_registered_folders_are_not_suggested_again(bare, settings):
    _page(settings, "already", "---\npath: ../gamma/ma\nparent: top\n---\n# A\n")
    assert sorted(p["folder"] for p in _plan(settings)) == ["mb", "nested"]


def test_registering_folders_makes_them_members(bare, settings):
    from app.services.registry import break_down

    pages = break_down(
        settings.registry_root,
        _load(settings),
        "top",
        [{"folder": "ma", "name": "part-a"}, {"folder": "nested", "name": "sub"}],
    )
    assert pages == ["projects/part-a.md", "projects/sub.md"]
    reg = _load(settings)
    assert reg.warnings == []
    assert reg.projects["part-a"].type == "module" and reg.projects["part-a"].owner == "top"
    assert reg.projects["sub"].type == "project" and reg.projects["sub"].parent == "top"
    assert sorted(reg.projects["top"].members) == ["part-a", "sub"]
    assert "parent: top" in (settings.registry_root / pages[0]).read_text(encoding="utf-8")


def test_breaking_down_is_all_or_none_and_stays_inside_the_group(bare, settings):
    from app.services.registry import RegisterError, break_down

    reg = _load(settings)
    for bad in (
        [{"folder": "ma", "name": "part-a"}, {"folder": "../beta", "name": "out"}],
        [{"folder": "ma", "name": "part-a"}, {"folder": "missing", "name": "gone"}],
        [{"folder": "ma", "name": "part-a"}, {"folder": "mb", "name": "part-a"}],
        [{"folder": "ma", "name": "Bad Name"}],
        [{"folder": "ma", "name": "alpha"}],
    ):
        with pytest.raises(RegisterError):
            break_down(settings.registry_root, reg, "top", bad)
    assert not (settings.registry_root / "projects" / "part-a.md").exists()


def test_break_down_cli_and_api(bare, authed, settings, capsys):
    r = authed.get("/api/registry/projects/top/break-down")
    assert r.status_code == 200 and sorted(p["folder"] for p in r.json()) == ["ma", "mb", "nested"]
    r = authed.post(
        "/api/registry/projects/top/break-down", json={"members": [{"folder": "mb", "name": "part-b"}]}
    )
    assert r.status_code == 201 and r.json()["pages"] == ["projects/part-b.md"]
    again = authed.post(
        "/api/registry/projects/top/break-down", json={"members": [{"folder": "mb", "name": "x"}]}
    )
    assert again.status_code == 409
    assert authed.get("/api/registry/projects/alpha/break-down").status_code == 409
    assert authed.get("/api/registry/projects/nope/break-down").status_code == 404

    assert main(["projects", "break-down", "top"], settings) == 0
    out = capsys.readouterr().out
    assert "ma: as ma (module)" in out and "mb:" not in out
    assert main(["projects", "break-down", "top", "--only", "ma"], settings) == 0
    assert "1 member(s) registered under top" in capsys.readouterr().out


def test_save_many_is_all_or_none(top, settings, monkeypatch):
    items = [(st.parse(model("top")), None), (st.parse(model("m-a")), "# Notes\n")]
    saved = st.save_many(settings.registry_root, items, keep=5)
    assert [s.project for s in saved] == ["top", "m-a"]
    assert (saved[1].folder / "notes.md").is_file()

    real = st.save
    calls = {"n": 0}

    def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("disk full")
        return real(*args, **kwargs)

    monkeypatch.setattr(st, "save", flaky)
    before = {p: [s.id for s in st.snapshots(settings.registry_root, p)] for p in ("top", "m-b")}
    with pytest.raises(OSError):
        st.save_many(
            settings.registry_root,
            [(st.parse(model("top", commit="1234567abc")), None), (st.parse(model("m-b")), None)],
        )
    after = {p: [s.id for s in st.snapshots(settings.registry_root, p)] for p in ("top", "m-b")}
    assert after == before  # the first one was taken back

    monkeypatch.setattr(st, "save", real)
    with pytest.raises(st.StudyError, match="appears twice"):
        st.save_many(settings.registry_root, [(st.parse(model("top")), None), (st.parse(model("top")), None)])


def test_save_set_cli(top, settings, tmp_path, capsys):
    both = tmp_path / "set.json"
    both.write_text(
        json.dumps({"studies": [{"model": model("top")}, {"model": model("m-a"), "notes": "# A\n"}]})
    )
    assert main(["study", "save-set", "top", "--file", str(both)], settings) == 0
    out = capsys.readouterr().out
    assert "top: snapshot" in out and "m-a: snapshot" in out and "Saved 2 snapshot(s)." in out
    stranger = tmp_path / "bad.json"
    stranger.write_text(json.dumps({"studies": [{"model": model("top")}, {"model": model("alpha")}]}))
    before = len(st.snapshots(settings.registry_root, "top"))
    assert main(["study", "save-set", "top", "--file", str(stranger)], settings) != 0
    assert "neither top nor one of its members" in capsys.readouterr().err
    assert len(st.snapshots(settings.registry_root, "top")) == before
