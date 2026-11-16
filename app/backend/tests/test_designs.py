"""Designs (ADR 0022): the model, the working copy and its revisions, approval, the handoff
package, the CLI and the API."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.__main__ import main
from app.services import designs as dz


def model(project: str = "alpha", **structure) -> dict:
    return {
        "schema": 1,
        "meta": {"project": project, "date": "2026-11-17", "summary": "Alpha, redesigned."},
        "components": [
            {"id": "api", "name": "API", "kind": "service"},
            {"id": "db", "name": "alpha.db", "kind": "database"},
        ],
        "relations": [{"id": "r1", "from": "api", "to": "db", "kind": "sql"}],
        "interfaces": {"exposes": [{"id": "list", "kind": "http", "method": "GET", "path": "/api/items"}]},
        "structure": {"ports": [20101], "depends_on": ["beta"], **structure},
    }


BRIEF = "# Brief\n\n## Purpose\n\nAlpha keeps the items and serves them to the other services.\n"


def work_folder(tmp_path: Path, mdl: dict | None = None, brief: str = BRIEF, name: str = "work") -> Path:
    folder = tmp_path / name
    folder.mkdir(exist_ok=True)
    (folder / "brief.md").write_text(brief, encoding="utf-8")
    (folder / "architecture.md").write_text(
        "# Architecture\n\n```mermaid\nflowchart LR\n  A --> B\n```\n", "utf-8"
    )
    (folder / "decisions").mkdir(exist_ok=True)
    (folder / "decisions" / "0001-use-sqlite.md").write_text("# 0001: Use SQLite\n", encoding="utf-8")
    (folder / "model.json").write_text(json.dumps(mdl or model()), encoding="utf-8")
    return folder


def run(settings, *argv: str) -> int:
    return main(list(argv), settings)


def started(settings, tmp_path: Path, slug: str = "main") -> Path:
    assert run(settings, "design", "init", "alpha", "--slug", slug) == 0
    folder = work_folder(tmp_path)
    assert run(settings, "design", "save", "alpha", "--slug", slug, "--dir", str(folder)) == 0
    return folder


# --- the model ----------------------------------------------------------------------------


def test_model_accepts_a_design_and_checks_ports_and_dependencies(manager=None):
    reg = type("R", (), {"projects": {"alpha": 1, "beta": 1}, "groups": {"g1": 1}})()
    ok = dz.parse(model(), project="alpha", registry=reg)
    assert ok.structure.ports == [20101]
    with pytest.raises(dz.DesignError, match="port range"):
        dz.parse(model(ports=[3000]), project="alpha", registry=reg)
    with pytest.raises(dz.DesignError, match="already recorded for beta"):
        dz.parse(model(), project="alpha", registry=reg, ports_taken={20101: ["beta"]})
    dz.parse(model(), project="alpha", registry=reg, ports_taken={20101: ["alpha"]})  # its own port is fine
    with pytest.raises(dz.DesignError, match="isn't a registered project"):
        dz.parse(model(depends_on=["nope"]), project="alpha", registry=reg)
    with pytest.raises(dz.DesignError, match="isn't a group"):
        dz.parse(model(group="nope"), project="alpha", registry=reg)
    with pytest.raises(dz.DesignError, match="not 'beta'"):
        dz.parse(model(), project="beta", registry=reg)
    with pytest.raises(dz.DesignError, match="itself"):
        dz.parse(model(depends_on=["alpha"]), project="alpha", registry=reg)


def test_model_reuses_the_study_reference_checks():
    bad = model()
    bad["relations"][0]["to"] = "missing"
    with pytest.raises(dz.DesignError, match="isn't a component"):
        dz.parse(bad, project="alpha")


def test_prose_refuses_absolute_paths_and_secrets():
    assert dz.prose_problems("a.md", "see docs/design.md") == []
    assert "absolute path" in dz.prose_problems("a.md", "in C:\\work\\alpha\\x")[0]
    assert "absolute path" in dz.prose_problems("a.md", "in /home/me/alpha/x")[0]  # sensitive-ok: test input
    fake = "sk-ant-" + "a1b2c3d4e5f6g7h8i9"
    assert "secret" in dz.prose_problems("a.md", f"key {fake}")[0]


# --- the working copy ---------------------------------------------------------------------


def test_init_save_show_and_list(repo, settings, tmp_path, capsys):
    started(settings, tmp_path)
    ref = dz.get(settings.registry_root, "alpha", "main")
    assert ref.stage == "brief"
    assert (ref.folder / "design.md").read_text(encoding="utf-8").startswith("---\nproject: alpha")
    assert "Alpha keeps the items" in (ref.folder / "brief.md").read_text(encoding="utf-8")
    assert (ref.folder / "decisions" / "0001-use-sqlite.md").is_file()
    row = dz.summary(ref)
    assert row["valid"] and row["counts"]["components"] == 2 and row["structure"]["ports"] == [20101]
    capsys.readouterr()
    assert run(settings, "design", "list") == 0
    assert "alpha" in capsys.readouterr().out
    assert run(settings, "design", "show", "alpha", "--json") == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["files"]["brief.md"].startswith("# Brief") and shown["model"]["meta"]["project"] == "alpha"
    # A second design of the same project, by slug.
    assert run(settings, "design", "init", "alpha", "--slug", "billing") == 0
    assert dz.slugs(settings.registry_root, "alpha") == ["billing", "main"]
    assert run(settings, "design", "init", "alpha", "--slug", "billing") == 1  # exists


def test_save_keeps_files_the_folder_lacks_and_rejects_bad_input(repo, settings, tmp_path, capsys):
    started(settings, tmp_path)
    only_plan = tmp_path / "plan"
    only_plan.mkdir()
    (only_plan / "plan.md").write_text("# Plan\n\nPhase 1 on 2026-12-01.\n", encoding="utf-8")
    assert run(settings, "design", "save", "alpha", "--dir", str(only_plan)) == 0
    ref = dz.get(settings.registry_root, "alpha")
    files = dz.read_files(ref.folder)
    assert "Phase 1" in files["plan.md"] and "Alpha keeps the items" in files["brief.md"]
    assert dz.load(ref.folder, "alpha")[1] == []  # the model stayed
    capsys.readouterr()
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "brief.md").write_text("# Brief\n\nSee C:\\Users\\me\\x\n", encoding="utf-8")
    assert run(settings, "design", "save", "alpha", "--dir", str(bad)) == 1
    assert "absolute path" in capsys.readouterr().err
    assert "Alpha keeps the items" in dz.read_files(ref.folder)["brief.md"]  # untouched
    (bad / "brief.md").write_text("ok\n", encoding="utf-8")
    (bad / "model.json").write_text(json.dumps(model(ports=[20101, 20101])), encoding="utf-8")
    assert run(settings, "design", "validate", "alpha", "--dir", str(bad)) == 1
    assert "listed twice" in capsys.readouterr().err
    stray = tmp_path / "stray"
    (stray / "decisions").mkdir(parents=True)
    (stray / "decisions" / "notes.md").write_text("x", encoding="utf-8")
    with pytest.raises(dz.DesignError, match="isn't a design file"):
        dz.save(settings.registry_root, ref, files={"decisions/notes.md": "x"}, model=None)


def test_stage_moves_only_between_the_three_working_stages(repo, settings, tmp_path, capsys):
    started(settings, tmp_path)
    assert run(settings, "design", "stage", "alpha", "plan") == 0
    assert dz.get(settings.registry_root, "alpha").stage == "plan"
    assert run(settings, "design", "stage", "alpha", "brief") == 0
    with pytest.raises(SystemExit):
        run(settings, "design", "stage", "alpha", "approved")


# --- approval -----------------------------------------------------------------------------


def test_approve_shows_a_plan_then_freezes_and_updates_only_structure_lines(repo, settings, tmp_path, capsys):
    started(settings, tmp_path)
    page = repo / "registry" / "projects" / "alpha.md"
    before = page.read_text(encoding="utf-8")
    capsys.readouterr()
    assert run(settings, "design", "approve", "alpha") == 0
    out = capsys.readouterr().out
    assert "ports: [20100] -> [20100, 20101]" in out and "Nothing was changed" in out
    assert page.read_text(encoding="utf-8") == before
    assert dz.revisions(dz.get(settings.registry_root, "alpha")) == []

    assert run(settings, "design", "approve", "alpha", "--yes") == 0
    ref = dz.get(settings.registry_root, "alpha")
    assert ref.stage == "approved" and dz.revisions(ref)[0]["number"] == 1
    after = page.read_text(encoding="utf-8")
    assert "ports: [20100, 20101]" in after
    # Everything else in the page stays: depends_on already had beta, so it's unchanged.
    assert after.replace("ports: [20100, 20101]", "ports: [20100]") == before
    # The revision is a frozen copy.
    rev, folder = dz.revision_folder(ref, 1)
    assert (folder / "brief.md").read_text(encoding="utf-8") == (ref.folder / "brief.md").read_text(
        encoding="utf-8"
    )


def test_approve_fills_group_and_kind_but_never_replaces_them(repo, settings, tmp_path, capsys):
    started(settings, tmp_path)
    folder = work_folder(tmp_path, model(group="g1", kind="service"), name="w2")
    assert run(settings, "design", "save", "alpha", "--dir", str(folder)) == 0
    assert run(settings, "design", "approve", "alpha", "--yes") == 0
    text = (repo / "registry" / "projects" / "alpha.md").read_text(encoding="utf-8")
    assert "kind: service" in text and text.count("group:") == 1  # g1 was already its group


def test_approve_refuses_an_empty_brief_and_a_block_list(repo, settings, tmp_path, capsys):
    assert run(settings, "design", "init", "alpha") == 0
    capsys.readouterr()
    assert run(settings, "design", "approve", "alpha", "--yes") == 1
    assert "brief is empty" in capsys.readouterr().err
    (repo / "registry" / "projects" / "alpha.md").write_text(
        "---\nname: alpha\npath: ../alpha\nports:\n  - 20100\ndepends_on: [beta]\n---\n# Alpha\n", "utf-8"
    )
    folder = work_folder(tmp_path)
    assert run(settings, "design", "save", "alpha", "--dir", str(folder)) == 0
    capsys.readouterr()
    assert run(settings, "design", "approve", "alpha", "--yes") == 1
    assert "block list" in capsys.readouterr().err
    assert dz.revisions(dz.get(settings.registry_root, "alpha")) == []


def test_saving_after_approval_goes_back_to_plan_and_keeps_the_revision(repo, settings, tmp_path, capsys):
    folder = started(settings, tmp_path)
    assert run(settings, "design", "approve", "alpha", "--yes") == 0
    (folder / "brief.md").write_text(BRIEF + "\nAlso: audit logs for every change.\n", encoding="utf-8")
    assert run(settings, "design", "save", "alpha", "--dir", str(folder)) == 0
    ref = dz.get(settings.registry_root, "alpha")
    row = dz.summary(ref)
    assert row["stage"] == "plan" and row["changed_since_revision"] and row["revision"] == 1
    _, rev_folder = dz.revision_folder(ref, "latest")
    assert "audit logs" not in (rev_folder / "brief.md").read_text(encoding="utf-8")
    assert run(settings, "design", "approve", "alpha", "--yes") == 0
    assert [r["number"] for r in dz.revisions(ref)] == [2, 1]


# --- preflight ----------------------------------------------------------------------------


def test_preflight_reports_each_problem_with_its_fix(repo, settings, tmp_path, capsys):
    capsys.readouterr()
    assert run(settings, "design", "preflight", "gamma", "--json") == 4  # in a root, not registered
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False and out["problems"][0]["fix"] == "projects scan --write --only gamma"
    assert run(settings, "design", "preflight", "nope", "--json") == 4
    assert json.loads(capsys.readouterr().out)["problems"][0]["code"] == "unknown-project"
    # alpha has code and no study: a warning, not a block.
    assert run(settings, "design", "preflight", "alpha", "--json") == 0
    codes = {p["code"]: p["severity"] for p in json.loads(capsys.readouterr().out)["problems"]}
    assert codes == {"no-study": "warn"}
    # A project with nothing but a CLAUDE.md has no code to study; without one, it's only noted.
    (repo.parent / "gamma").mkdir(exist_ok=True)
    (repo / "registry" / "projects" / "gamma.md").write_text("---\npath: ../gamma\n---\n# Gamma\n", "utf-8")
    assert run(settings, "design", "preflight", "gamma", "--json") == 0
    assert json.loads(capsys.readouterr().out)["problems"] == []
    (repo.parent / "gamma" / "CLAUDE.md").unlink()
    assert run(settings, "design", "preflight", "gamma", "--json") == 0
    assert [p["code"] for p in json.loads(capsys.readouterr().out)["problems"]] == ["no-claude-md"]


def test_preflight_for_handoff_needs_a_revision_and_inbox_edits(repo, settings, tmp_path, capsys):
    started(settings, tmp_path)
    capsys.readouterr()
    assert run(settings, "design", "preflight", "alpha", "--for", "handoff", "--json") == 4
    assert "not-approved" in {p["code"] for p in json.loads(capsys.readouterr().out)["problems"]}
    assert run(settings, "design", "approve", "alpha", "--yes") == 0
    assert run(settings, "design", "preflight", "alpha", "--for", "handoff", "--json") == 0
    assert run(settings, "projects", "inbox-edits", "alpha", "off") == 0
    capsys.readouterr()
    assert run(settings, "design", "preflight", "alpha", "--for", "handoff", "--json") == 4
    problems = json.loads(capsys.readouterr().out)["problems"]
    assert [p["fix"] for p in problems if p["code"] == "inbox-edits-off"] == ["projects inbox-edits alpha on"]
    assert run(settings, "design", "handoff", "alpha") == 1  # the handoff itself refuses


def test_context_gathers_the_system_around_the_project(repo, settings, tmp_path, capsys):
    capsys.readouterr()
    assert run(settings, "design", "context", "alpha", "--json") == 0
    ctx = json.loads(capsys.readouterr().out)
    assert ctx["has_code"] and "Rules for alpha" in ctx["claude_md"]
    assert {n["id"] for n in ctx["neighbours"]} >= {"beta"} and "alpha" not in {
        n["id"] for n in ctx["neighbours"]
    }
    assert {"port": 20100, "projects": ["alpha"]} in ctx["ports_in_use"]
    assert "g1" in ctx["groups"] and "20300-20399" in ctx["rules"]
    assert run(settings, "design", "context", "beta") == 0
    assert "(none: ask for the tech stack)" not in capsys.readouterr().out  # beta has a CLAUDE.md
    assert run(settings, "design", "context", "gamma") == 1  # not registered


# --- handoff ------------------------------------------------------------------------------


def test_handoff_creates_a_thread_and_the_package_is_a_plain_copy(repo, settings, tmp_path, capsys):
    started(settings, tmp_path)
    assert run(settings, "design", "approve", "alpha", "--yes") == 0
    capsys.readouterr()
    assert run(settings, "design", "handoff", "alpha", "--json") == 0
    item = json.loads(capsys.readouterr().out)
    from app.db import Database
    from app.services import feedback as fb

    with Database(settings.db_file).conn() as conn:
        row = fb.get(conn, item["id"])
    assert row["source"] == "archeion"
    assert row["anchor"]["task"] == {
        "type": "handoff-design",
        "project": "alpha",
        "slug": "main",
        "revision": 1,
    }
    assert dz.revisions(dz.get(settings.registry_root, "alpha"))[0]["handoff"]["thread"] == row["thread_id"]

    assert run(settings, "inbox", "show", str(item["id"])) == 0
    assert "deliver revision 1: design package alpha" in capsys.readouterr().out

    assert run(settings, "design", "package", "alpha") == 0
    target = repo.parent / "alpha" / ".archeion" / "designs" / "main"
    assert sorted(p.name for p in target.iterdir()) == [
        "architecture.md",
        "brief.md",
        "decisions",
        "handoff.json",
        "model.json",
        "plan.md",
        "questions.md",
    ]
    handoff = json.loads((target / "handoff.json").read_text(encoding="utf-8"))
    assert handoff["revision"] == 1 and handoff["slug"] == "main"
    # Nothing from the registry beyond this design: no other project is named but its own dependencies.
    assert "beta" in (target / "model.json").read_text(encoding="utf-8")
    assert not (target / "design.md").exists() and not (target / "info.json").exists()

    # A receipt left by an earlier consume survives a new delivery; stale package files don't.
    (target / "receipt.md").write_text("receipt\n", encoding="utf-8")
    (target / "stale.md").write_text("x", encoding="utf-8")
    assert run(settings, "design", "package", "alpha") == 0
    assert (target / "receipt.md").is_file() and not (target / "stale.md").exists()

    capsys.readouterr()
    assert run(settings, "design", "consumed", "alpha", "--revision", "1") == 0
    ref = dz.get(settings.registry_root, "alpha")
    assert ref.stage == "handed off"
    assert dz.revisions(ref)[0]["handoff"]["consumed"]


def test_consumed_does_not_move_a_design_that_has_moved_on(repo, settings, tmp_path, capsys):
    folder = started(settings, tmp_path)
    assert run(settings, "design", "approve", "alpha", "--yes") == 0
    (folder / "plan.md").write_text("# Plan\n\nNew phase.\n", encoding="utf-8")
    assert run(settings, "design", "save", "alpha", "--dir", str(folder)) == 0
    assert run(settings, "design", "consumed", "alpha", "--revision", "1") == 0
    assert dz.get(settings.registry_root, "alpha").stage == "plan"


def test_package_refuses_where_inbox_edits_are_off(repo, settings, tmp_path, capsys):
    started(settings, tmp_path)
    assert run(settings, "design", "approve", "alpha", "--yes") == 0
    assert run(settings, "projects", "inbox-edits", "alpha", "off") == 0
    capsys.readouterr()
    assert run(settings, "design", "package", "alpha") == 1
    assert "may not edit alpha" in capsys.readouterr().err
    assert not (repo.parent / "alpha" / ".archeion").exists()


def test_discard_deletes_the_design(repo, settings, tmp_path, capsys):
    started(settings, tmp_path)
    assert run(settings, "design", "discard", "alpha") == 0
    assert dz.slugs(settings.registry_root, "alpha") == []
    assert run(settings, "design", "show", "alpha") == 1


# --- the API ------------------------------------------------------------------------------


def test_api_requires_login(client):
    for path in (
        "/api/designs",
        "/api/designs/alpha",
        "/api/designs/alpha/main",
        "/api/designs/alpha/preflight",
    ):
        assert client.get(path).status_code == 401
    assert client.put("/api/designs/alpha/main/stage", json={"stage": "plan"}).status_code == 401
    assert client.post("/api/designs/alpha/main/approve").status_code == 401
    assert client.post("/api/designs/alpha/main/handoff").status_code == 401


def test_api_walks_a_design_from_draft_to_handoff(repo, settings, tmp_path, authed):
    started(settings, tmp_path)
    assert authed.get("/api/designs").json()[0]["stage"] == "brief"
    row = authed.get("/api/designs/alpha").json()[0]
    assert row["slug"] == "main" and row["valid"]
    one = authed.get("/api/designs/alpha/main").json()
    assert "Alpha keeps the items" in one["files"]["brief.md"] and one["model"]["components"]
    assert authed.get("/api/designs/alpha/other").status_code == 404
    assert authed.get("/api/designs/nope").status_code == 404

    assert authed.put("/api/designs/alpha/main/stage", json={"stage": "plan"}).json()["stage"] == "plan"
    assert authed.put("/api/designs/alpha/main/stage", json={"stage": "approved"}).status_code == 422

    plan = authed.get("/api/designs/alpha/main/approval").json()
    assert plan["problems"] == [] and plan["next_revision"] == 1
    assert plan["changes"][0]["key"] == "ports" and plan["changes"][0]["value"] == "[20100, 20101]"

    pre = authed.get("/api/designs/alpha/preflight", params={"for": "handoff"}).json()
    assert pre["ok"] is False  # not approved yet

    done = authed.post("/api/designs/alpha/main/approve").json()
    assert done["stage"] == "approved" and done["revision"] == 1
    assert authed.get("/api/registry").json()["projects"]  # the registry reloaded
    alpha = next(p for p in authed.get("/api/registry").json()["projects"] if p["id"] == "alpha")
    assert alpha["ports"] == [20100, 20101]
    assert (
        authed.get("/api/designs/alpha/main", params={"revision": "latest"}).json()["label"] == "revision 1"
    )
    assert authed.get("/api/designs/alpha/main", params={"revision": "9"}).status_code == 404

    item = authed.post("/api/designs/alpha/main/handoff")
    assert item.status_code == 201
    assert item.json()["anchor"]["task"]["type"] == "handoff-design"


def test_a_design_conversation_starts_from_the_viewer(repo, settings, tmp_path, authed):
    r = authed.post(
        "/api/feedback",
        json={
            "kind": "prompt",
            "body": "Design this project.",
            "anchor": {"task": {"type": "design", "project": "alpha", "slug": "main"}},
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["anchor"]["task"] == {"type": "design", "project": "alpha", "slug": "main"}
    bad = authed.post(
        "/api/feedback",
        json={
            "kind": "prompt",
            "body": "x",
            "anchor": {"task": {"type": "design", "project": "alpha", "slug": "No Way"}},
        },
    )
    assert bad.status_code == 422
