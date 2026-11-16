"""What a design asks of other projects, and built vs designed (ADR 0022, phase 4)."""

from __future__ import annotations

import json

from app.__main__ import main
from app.services import designs as dz
from app.services import studies as st
from app.services.sources import SourceManager

from .test_designs import BRIEF, model, run, work_folder


def study(project: str, *, exposes=(), calls=(), components=(), entities=()) -> st.Study:
    return st.parse(
        {
            "schema": 1,
            "meta": {"project": project, "date": "2026-11-16", "commit": "abcdef1234"},
            "components": list(components),
            "interfaces": {"exposes": list(exposes), "calls": list(calls)},
            "entities": list(entities),
        }
    )


def design_model(**extra) -> dict:
    base = model()
    base["interfaces"] = extra.pop("interfaces", base["interfaces"])
    base["structure"] = extra.pop("structure", {"ports": [20101], "depends_on": ["beta"]})
    base.update(extra)
    return base


def put_design(settings, tmp_path, mdl: dict) -> None:
    assert run(settings, "design", "init", "alpha") == 0
    folder = work_folder(tmp_path, mdl)
    assert run(settings, "design", "save", "alpha", "--dir", str(folder)) == 0


def kinds(settings, authed) -> dict[str, dict]:
    return {
        i["kind"] + ":" + str(i["neighbour"]): i for i in authed.get("/api/designs/alpha/main/impact").json()
    }


def test_calls_are_checked_against_what_neighbours_expose(repo, settings, tmp_path, authed):
    st.save(
        settings.registry_root,
        study("beta", exposes=[{"id": "x", "kind": "http", "method": "GET", "path": "/api/x"}]),
    )
    mdl = design_model(
        interfaces={
            "exposes": [],
            "calls": [
                {"id": "c1", "kind": "http", "target_project": "beta", "method": "GET", "path": "/api/x"},
                {"id": "c2", "kind": "http", "target_project": "beta", "method": "POST", "path": "/api/y"},
                {"id": "c3", "kind": "http", "target_project": "sub1", "method": "GET", "path": "/z"},
                {"id": "c4", "kind": "http", "target_project": "nope", "method": "GET", "path": "/z"},
                {"id": "c5", "kind": "http", "port": 20999, "method": "GET", "path": "/z"},
            ],
        },
        structure={"ports": [20101], "depends_on": ["sub1"]},
    )
    put_design(settings, tmp_path, mdl)
    found = kinds(settings, authed)
    # c1 matches what beta's study exposes: nothing to say.
    missing = found["missing-endpoint:beta"]
    assert missing["severity"] == "warn" and "POST /api/y" in missing["message"]
    assert "Please add it" in missing["suggestion"]
    assert "unverified:sub1" in found and found["unverified:sub1"]["severity"] == "info"
    assert "unknown-project:None" in found and "unresolved-call:None" in found
    # beta is called but not in depends_on; sub1 is listed but only unverified-called (still a call).
    assert "depends-on-missing:beta" in found
    assert "depends-on-unused:sub1" not in found


def test_a_neighbours_own_design_counts_as_planned(repo, settings, tmp_path, authed):
    assert run(settings, "design", "init", "beta") == 0
    beta = work_folder(
        tmp_path,
        {
            **model("beta"),
            "interfaces": {"exposes": [{"id": "n", "kind": "http", "method": "POST", "path": "/api/new"}]},
            "structure": {},
        },
        name="beta",
    )
    assert run(settings, "design", "save", "beta", "--dir", str(beta)) == 0
    put_design(
        settings,
        tmp_path,
        design_model(
            interfaces={
                "exposes": [],
                "calls": [
                    {
                        "id": "c1",
                        "kind": "http",
                        "target_project": "beta",
                        "method": "POST",
                        "path": "/api/new",
                    }
                ],
            }
        ),
    )
    found = kinds(settings, authed)
    assert found["planned-elsewhere:beta"]["severity"] == "info"
    assert "missing-endpoint:beta" not in found


def test_dropping_an_endpoint_others_call_is_flagged_for_the_caller(repo, settings, tmp_path, authed):
    st.save(
        settings.registry_root,
        study(
            "alpha", exposes=[{"id": "get-items", "kind": "http", "method": "GET", "path": "/api/items/{id}"}]
        ),
    )
    st.save(
        settings.registry_root,
        study(
            "beta",
            calls=[
                {
                    "id": "c1",
                    "kind": "http",
                    "target_project": "alpha",
                    "method": "GET",
                    "path": "/api/items/{id}",
                }
            ],
        ),
    )
    put_design(
        settings,
        tmp_path,
        design_model(interfaces={"exposes": [], "calls": []}, structure={"ports": [20101]}),
    )
    found = kinds(settings, authed)
    dropped = found["endpoint-dropped:beta"]
    assert dropped["severity"] == "warn" and "GET /api/items/{id}" in dropped["suggestion"]
    # Keeping the endpoint (under a differently named path parameter) removes the warning.
    keep = design_model(
        interfaces={
            "exposes": [{"id": "e", "kind": "http", "method": "GET", "path": "/api/items/{item_id}"}],
            "calls": [],
        },
        structure={"ports": [20101]},
    )
    assert (
        run(settings, "design", "save", "alpha", "--dir", str(work_folder(tmp_path, keep, name="keep"))) == 0
    )
    assert "endpoint-dropped:beta" not in kinds(settings, authed)


def test_a_port_taken_since_saving_blocks(repo, settings, tmp_path, authed):
    put_design(settings, tmp_path, design_model())
    (repo / "registry" / "projects" / "beta.md").write_text(
        "---\npath: ../beta\ngroup: g1\nports: [20101]\n---\n# Beta\n", encoding="utf-8"
    )
    SourceManager(
        settings.docs_root,
        settings.registry_root,
        settings.repo_root,
        settings.workspace_dir,
        settings.project_roots,
    )  # (the API reloads the registry on its own)
    authed.app.state.archeion.sources.reload()
    found = authed.get("/api/designs/alpha/main/impact").json()
    assert found[0]["kind"] == "port-clash" and found[0]["severity"] == "block"


def test_built_vs_designed_compares_by_name(repo, settings, tmp_path, authed):
    put_design(settings, tmp_path, design_model())
    assert authed.get("/api/designs/alpha/main/built").json() == {"studied": None, "sections": {}}
    st.save(
        settings.registry_root,
        study(
            "alpha",
            components=[
                {"id": "app", "name": "API", "kind": "service"},
                {"id": "cache", "name": "cache", "kind": "store"},
            ],
            exposes=[{"id": "l", "kind": "http", "method": "get", "path": "/api/items"}],
            entities=[{"id": "t", "name": "items"}],
        ),
    )
    out = authed.get("/api/designs/alpha/main/built").json()
    s = out["sections"]
    assert out["studied"].startswith("2026-11-16-abcdef1")
    assert s["components"] == {"designed_only": ["alpha.db"], "built_only": ["cache"], "both": 1}
    assert s["exposes"]["both"] == 1 and s["exposes"]["designed_only"] == []
    assert s["entities"]["built_only"] == ["items"]


def test_impact_and_built_need_login_and_a_design(client, authed):
    assert authed.get("/api/designs/alpha/main/impact").status_code == 404
    client.cookies.clear()
    assert client.get("/api/designs/alpha/main/impact").status_code == 401
    assert client.get("/api/designs/alpha/main/built").status_code == 401


def test_brief_text_is_kept_after_impact_reads(repo, settings, tmp_path, authed, capsys):
    """Reading checks never writes: the working copy is untouched."""
    put_design(settings, tmp_path, design_model())
    before = (dz.get(settings.registry_root, "alpha").folder / "brief.md").read_text(encoding="utf-8")
    authed.get("/api/designs/alpha/main/impact")
    authed.get("/api/designs/alpha/main/built")
    assert (dz.get(settings.registry_root, "alpha").folder / "brief.md").read_text(encoding="utf-8") == before
    assert BRIEF.strip().splitlines()[0] in before
    capsys.readouterr()
    assert main(["design", "show", "alpha", "--json"], settings) == 0
    assert json.loads(capsys.readouterr().out)["slug"] == "main"
