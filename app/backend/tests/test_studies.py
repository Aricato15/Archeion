"""Code studies (ADR 0019): the model, snapshots, the inventory, the CLI and the API."""

from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

import pytest
from watchfiles import Change

from app.__main__ import main
from app.services import studies as st
from app.services.events import study_change_events
from app.services.sources import SourceManager
from app.services.study_scan import scan, text_report


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def model(project: str = "alpha", commit: str = "abcdef1234", **extra) -> dict:
    data = {
        "schema": 1,
        "meta": {"project": project, "date": "2026-11-16", "commit": commit, "summary": "The alpha service."},
        "components": [
            {"id": "api", "name": "API", "kind": "service", "cites": [{"path": "src/app.py", "line": 3}]},
            {"id": "routes", "name": "routes", "kind": "module", "parent": "api"},
            {"id": "db", "name": "alpha.db", "kind": "database"},
        ],
        "relations": [{"id": "r1", "from": "routes", "to": "db", "kind": "sql", "label": "SELECT items"}],
        "interfaces": {
            "exposes": [{"id": "get-items", "kind": "http", "method": "GET", "path": "/api/items/{id}"}],
            "calls": [{"id": "c1", "kind": "http", "port": 20200, "method": "GET", "path": "/api/x"}],
        },
        "entities": [
            {
                "id": "items",
                "name": "items",
                "store": "db",
                "fields": [{"name": "id", "type": "int", "pk": True}],
            },
            {
                "id": "tags",
                "name": "tags",
                "store": "db",
                "fields": [{"name": "item_id", "type": "int", "fk": "items.id"}],
            },
        ],
        "flows": [
            {
                "id": "read",
                "title": "Read an item",
                "participants": ["routes", "db"],
                "steps": [
                    {"from": "routes", "to": "db", "label": "SELECT"},
                    {
                        "block": "alt",
                        "label": "found",
                        "steps": [{"from": "db", "to": "routes", "label": "row", "reply": True}],
                        "others": [{"label": "missing", "steps": [{"note": "404", "over": ["routes"]}]}],
                    },
                ],
            }
        ],
        "activities": [
            {
                "id": "sync",
                "title": "Sync",
                "nodes": [
                    {"id": "s", "kind": "start"},
                    {"id": "a", "label": "fetch"},
                    {"id": "e", "kind": "end"},
                ],
                "edges": [{"from": "s", "to": "a"}, {"from": "a", "to": "e"}],
            }
        ],
        "states": [
            {
                "id": "item-life",
                "title": "Item",
                "entity": "items",
                "states": [{"id": "new"}, {"id": "done"}],
                "initial": "new",
                "final": ["done"],
                "transitions": [{"from": "new", "to": "done", "label": "finish"}],
            }
        ],
        "findings": [{"id": "f1", "severity": "warn", "title": "No index on tags.item_id"}],
        "questions": ["Who deletes old items?"],
    }
    data.update(extra)
    return data


# --- the model --------------------------------------------------------------------------


def test_a_full_model_validates_and_round_trips():
    study = st.parse(model())
    dumped = st.dump(study)
    assert dumped["relations"][0]["from"] == "routes"
    assert dumped["flows"][0]["steps"][1]["others"][0]["steps"][0]["note"] == "404"
    assert st.dump(st.parse(dumped)) == dumped


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda m: m["relations"][0].update({"to": "ghost"}), "'ghost' isn't a component"),
        (
            lambda m: m["components"].append({"id": "api", "name": "x", "kind": "module"}),
            "duplicate id 'api'",
        ),
        (lambda m: m["components"][0].update({"parent": "routes"}), "make a cycle"),
        (
            lambda m: m["flows"][0]["steps"].append({"from": "api", "to": "db"}),
            "isn't one of its participants",
        ),
        (lambda m: m["entities"][1]["fields"][0].update({"fk": "nowhere.id"}), "isn't <entity id>.<field>"),
        (lambda m: m["activities"][0]["edges"].append({"from": "a", "to": "zz"}), "'zz', which isn't one"),
        (lambda m: m["states"][0].update({"initial": "gone"}), "'gone' isn't one of its states"),
        (lambda m: m["interfaces"]["calls"][0].pop("port"), "needs target_project, target_url or port"),
        (lambda m: m["meta"].update({"commit": "not-a-hash"}), "git hash"),
        (lambda m: m.update({"surprise": 1}), "surprise"),
        (lambda m: m["components"][0].update({"id": "bad id"}), "components.0.id"),
    ],
)
def test_invalid_models_say_why(change, message):
    data = copy.deepcopy(model())
    change(data)
    with pytest.raises(st.StudyError, match=message):
        st.parse(data)


def test_citations_are_relative_and_never_secrets():
    for bad in ("/etc/x", "a/../b", "a\\b", ".env", "conf/.env.local"):
        data = model()
        data["components"][0]["cites"] = [{"path": bad}]
        with pytest.raises(st.StudyError):
            st.parse(data)
    data = model()
    data["components"][0]["cites"] = [{"path": ".env.example", "line": 2}]
    st.parse(data)
    # Built at runtime so this file doesn't trip the commit hook.
    leaked = "api_key = '" + "Z" * 24 + "'"
    data["components"][0]["cites"] = [{"path": "src/app.py", "line": 1, "snippet": leaked}]
    with pytest.raises(st.StudyError, match="looks like it holds a secret"):
        st.parse(data)
    data["components"][0]["cites"] = [{"path": "src/app.py", "line": 1, "snippet": "x\n" * 40}]
    with pytest.raises(st.StudyError, match="at most 30 lines"):
        st.parse(data)
    data["components"][0]["cites"] = [{"path": "src/app.py", "line": 5, "end": 2}]
    with pytest.raises(st.StudyError, match="can't come before"):
        st.parse(data)


# --- snapshots --------------------------------------------------------------------------


def test_save_names_lists_and_prunes(tmp_path):
    reg = tmp_path / "registry"
    first, pruned = st.save(reg, st.parse(model()), notes="# Notes\n", keep=2)
    assert first.id == "2026-11-16-abcdef1" and pruned == []
    assert (first.folder / "notes.md").read_text(encoding="utf-8") == "# Notes\n"
    second, _ = st.save(reg, st.parse(model()), keep=2)
    assert second.id == "2026-11-16-abcdef1-2"
    third, pruned = st.save(reg, st.parse(model(commit="1234567abc")), keep=2)
    assert pruned == [first.id]
    ids = [s.id for s in st.snapshots(reg, "alpha")]
    assert ids == [third.id, second.id]
    assert st.get_snapshot(reg, "alpha", "latest").id == third.id
    assert st.latest_by_project(reg)["alpha"].id == third.id
    with pytest.raises(st.StudyNotFound):
        st.get_snapshot(reg, "alpha", first.id)
    with pytest.raises(st.StudyNotFound):
        st.get_snapshot(reg, "../x", "latest")
    # Leftovers that aren't snapshots are ignored.
    (reg / "studies" / "alpha" / "scratch").mkdir()
    assert len(st.snapshots(reg, "alpha")) == 2


def test_a_broken_snapshot_is_listed_with_its_problems(tmp_path):
    reg = tmp_path / "registry"
    snap, _ = st.save(reg, st.parse(model()))
    data = json.loads((snap.folder / "study.json").read_text(encoding="utf-8"))
    data["relations"][0]["to"] = "ghost"
    (snap.folder / "study.json").write_text(json.dumps(data), encoding="utf-8")
    raw, problems = st.load(snap)
    assert raw["relations"][0]["to"] == "ghost" and "ghost" in problems[0]
    row = st.summary(snap)
    assert row["valid"] is False and row["counts"]["components"] == 3 and row["counts"]["exposes"] == 1


def test_diff_ignores_citations():
    old = st.dump(st.parse(model()))
    new_model = model()
    new_model["components"][0]["cites"] = [{"path": "src/app.py", "line": 99}]
    new_model["components"][1]["summary"] = "now with docs"
    new_model["components"].append({"id": "cache", "name": "cache", "kind": "store"})
    new_model["findings"] = []
    d = st.diff(old, st.dump(st.parse(new_model)))
    assert d["components"]["added"] == [{"id": "cache", "label": "cache"}]
    assert d["components"]["changed"] == [{"id": "routes", "label": "routes", "fields": ["summary"]}]
    assert d["findings"]["removed"][0]["id"] == "f1"
    assert d["relations"] == {"added": [], "removed": [], "changed": []}


def test_system_links_match_calls_to_exposed_endpoints_and_report_drift():
    a = model("alpha")
    a["interfaces"]["calls"] = [
        {"id": "by-port", "kind": "http", "port": 20200, "method": "GET", "path": "/api/items/42"},
        {"id": "by-url", "kind": "http", "target_url": "http://127.0.0.1:20200/api/nope", "method": "POST"},
        {"id": "outside", "kind": "http", "target_url": "https://example.com/v1"},
    ]
    b = model("beta")
    b["interfaces"]["calls"] = []
    out = st.system_links(
        {"alpha": [20100], "beta": [20200], "gamma": []},
        {"alpha": ["gamma"], "beta": []},
        {"alpha": st.dump(st.parse(a)), "beta": st.dump(st.parse(b))},
    )
    (link,) = out["links"]
    assert (link["from"], link["to"]) == ("alpha", "beta")
    calls = {c["id"]: c for c in link["calls"]}
    assert calls["by-port"]["exposed"] == "get-items" and calls["by-port"]["resolved_by"] == "port"
    assert calls["by-url"]["exposed"] is None
    assert out["unresolved"] == [{"from": "alpha", "call": "outside", "target": "https://example.com/v1"}]
    assert out["drift"] == [{"project": "alpha", "code_only": ["beta"], "registry_only": ["gamma"]}]


# --- the inventory ----------------------------------------------------------------------


def _code(alpha: Path) -> None:
    pkg = alpha / "src" / "svc"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "db.py").write_text(
        "import sqlite3\n\nSCHEMA = 'CREATE TABLE IF NOT EXISTS items (id INTEGER)'\n\n"
        "def connect():\n    return sqlite3.connect('x.db')\n",
        encoding="utf-8",
    )
    (pkg / "api.py").write_text(
        "import os\nimport httpx\nfrom fastapi import APIRouter, FastAPI\nfrom . import db\n\n"
        "router = APIRouter(prefix='/api')\napp = FastAPI()\nPORT = os.getenv('SVC_PORT')\n\n"
        "@router.get('/items/{item_id}')\ndef item(item_id: int):\n    db.connect()\n"
        "    return httpx.get('http://127.0.0.1:20200/api/x')\n\n"
        "class Thing:\n    def run(self):\n        pass\n\n"
        "if __name__ == '__main__':\n    pass\n",
        encoding="utf-8",
    )
    web = alpha / "web" / "src"
    web.mkdir(parents=True)
    (web / "client.ts").write_text(
        "import { useQuery } from '@tanstack/react-query'\nimport { thing } from './util'\n"
        "export function load() {\n  return fetch('/api/items/1')\n}\nconst p = import.meta.env.VITE_PORT\n",
        encoding="utf-8",
    )
    (web / "util.ts").write_text("export const thing = 1\n", encoding="utf-8")
    (alpha / "pyproject.toml").write_text(
        "[project]\nname='svc'\ndependencies=['fastapi','httpx']\n[project.scripts]\nsvc='svc.api:main'\n",
        encoding="utf-8",
    )
    (alpha / ".env.example").write_text("SVC_PORT=20100\n", encoding="utf-8")
    (alpha / ".env").write_text("NOT=read 20999\n", encoding="utf-8")
    (alpha / "node_modules" / "x").mkdir(parents=True)
    (alpha / "node_modules" / "x" / "index.js").write_text("fetch('/never')\n", encoding="utf-8")
    (alpha / "data").mkdir()
    (alpha / "data" / "alpha.db").write_bytes(b"SQLite format 3\0")


def test_scan_inventories_python_and_typescript(repo):
    alpha = repo.parent / "alpha"
    _code(alpha)
    inv = scan(alpha, "alpha")
    files = {m["path"]: m for m in inv.modules}
    assert "node_modules/x/index.js" not in files and inv.languages["python"]["files"] == 3
    assert all(not s.endswith((".env", ".db")) for s in [*files, *inv.skipped])
    api = files["src/svc/api.py"]
    assert api["module"] == "svc.api" and api["imports"] == ["src/svc/db.py"]
    assert "httpx" in api["external"] and "os" in api["external"]
    assert {"name": "Thing.run", "kind": "method", "line": 16, "end": 17} in api["defs"]
    assert inv.routes == [
        {
            "path": "src/svc/api.py",
            "line": 11,
            "method": "GET",
            "route": "/api/items/{item_id}",
            "handler": "svc.api.item",
            "framework": "python",
        }
    ]
    urls = {(c["lib"], c["url"]) for c in inv.http_calls}
    assert ("httpx", "http://127.0.0.1:20200/api/x") in urls and ("fetch", "/api/items/1") in urls
    assert {t["name"] for t in inv.sql_tables} == {"items"}
    assert {e["name"] for e in inv.env_vars} == {"SVC_PORT", "VITE_PORT"}
    assert {p["port"] for p in inv.ports} == {20100}
    kinds = {e["kind"] for e in inv.entry_points}
    assert {"script", "main", "app", "sqlite"} <= kinds
    client = files["web/src/client.ts"]
    assert client["imports"] == ["web/src/util.ts"] and client["external"] == ["@tanstack/react-query"]
    assert {"from": "web/src", "to": "web/src", "imports": 1} not in inv.package_graph
    assert "stdlib" not in inv.external_imports and "os" not in inv.external_imports
    assert "fastapi" in inv.external_imports
    report = text_report(inv)
    assert "GET /api/items/{item_id}" in report and "ports: 20100" in report


# --- CLI --------------------------------------------------------------------------------


def _commit_code(repo: Path) -> str:
    alpha = repo.parent / "alpha"
    _code(alpha)
    _git(alpha, "add", "-A")
    _git(alpha, "commit", "-q", "-m", "feat: code")
    return _git(alpha, "rev-parse", "HEAD")


def test_cli_scan_save_list_show_and_changes(repo, settings, capsys, tmp_path):
    head = _commit_code(repo)
    out_file = tmp_path / "inv.json"
    assert main(["study", "scan", "alpha", "--out", str(out_file)], settings) == 0
    assert "GET /api/items/{item_id}" in capsys.readouterr().out
    assert json.loads(out_file.read_text(encoding="utf-8"))["commit"] == head

    path = tmp_path / "study.json"
    path.write_text(json.dumps(model(commit=head)), encoding="utf-8")
    assert main(["study", "validate", "--file", str(path)], settings) == 0
    assert "Valid." in capsys.readouterr().out
    notes = tmp_path / "notes.md"
    notes.write_text("# How alpha works\n", encoding="utf-8")
    assert main(["study", "save", "alpha", "--file", str(path), "--notes", str(notes)], settings) == 0
    assert f"Saved snapshot 2026-11-16-{head[:7]}" in capsys.readouterr().out

    assert main(["study", "list"], settings) == 0
    assert "(current)" in capsys.readouterr().out
    assert main(["study", "show", "alpha", "--json"], settings) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["notes"] == "# How alpha works\n" and shown["problems"] == []

    alpha = repo.parent / "alpha"
    (alpha / "src" / "svc" / "db.py").write_text("# changed\n", encoding="utf-8")
    _git(alpha, "commit", "-qam", "fix: db")
    assert main(["study", "list", "alpha"], settings) == 0
    assert "(1 commits since)" in capsys.readouterr().out
    assert main(["study", "changes", "alpha"], settings) == 0
    assert "src/svc/db.py" in capsys.readouterr().out

    # Refused: the wrong project, an invalid model, an unknown project, a missing snapshot.
    assert main(["study", "save", "beta", "--file", str(path)], settings) == 1
    assert "not 'beta'" in capsys.readouterr().err
    path.write_text(
        json.dumps(model(relations=[{"id": "r", "from": "x", "to": "y", "kind": "sql"}])), "utf-8"
    )
    assert main(["study", "save", "alpha", "--file", str(path)], settings) == 1
    assert "isn't a component" in capsys.readouterr().err
    assert main(["study", "scan", "nobody"], settings) == 1
    assert main(["study", "show", "beta"], settings) == 1
    assert "No study snapshot" in capsys.readouterr().err


# --- API --------------------------------------------------------------------------------


def test_api_lists_serves_and_diffs_snapshots(authed, settings):
    reg = settings.registry_root
    assert authed.get("/api/studies").json() == []
    first, _ = st.save(reg, st.parse(model()), notes="# Notes\n")
    changed = model(commit="1234567abc")
    changed["components"].append({"id": "cache", "name": "cache", "kind": "store"})
    second, _ = st.save(reg, st.parse(changed))
    rows = authed.get("/api/studies").json()
    assert [r["id"] for r in rows] == [second.id]
    snaps = authed.get("/api/studies/alpha").json()
    assert [s["id"] for s in snaps] == [second.id, first.id]
    # The commits aren't in alpha's repo, so staleness is unknown rather than wrong.
    assert snaps[0]["commits_since"] is None
    body = authed.get(f"/api/studies/alpha/{first.id}").json()
    assert body["notes_text"] == "# Notes\n" and body["model"]["meta"]["project"] == "alpha"
    assert authed.get("/api/studies/alpha/latest").json()["id"] == second.id
    d = authed.get(f"/api/studies/alpha/diff?from={first.id}").json()
    assert d["to"] == second.id and d["sections"]["components"]["added"][0]["id"] == "cache"
    assert authed.get("/api/studies/nobody").status_code == 404
    assert authed.get("/api/studies/alpha/2020-01-01-0000000").status_code == 404
    assert authed.get("/api/studies/alpha/..%2Fx").status_code in (404, 422)
    assert authed.get("/api/studies/alpha/diff?from=2020-01-01-0000000").status_code == 404


def test_api_system_links(authed, settings):
    reg = settings.registry_root
    st.save(reg, st.parse(model("alpha")))
    beta = model("beta")
    beta["interfaces"]["calls"] = []
    st.save(reg, st.parse(beta))
    # Registry ports: alpha 20100; give beta 20200 so alpha's call resolves to it.
    page = reg / "projects" / "beta.md"
    page.write_text("---\npath: ../beta\ngroup: g1\nports: [20200]\n---\n# Beta\n", encoding="utf-8")
    authed.app.state.archeion.sources.reload()
    out = authed.get("/api/system/links").json()
    assert out["links"][0]["from"] == "alpha" and out["links"][0]["to"] == "beta"
    assert out["drift"] == []  # alpha's page already depends on beta


def test_api_requires_login(client):
    assert client.get("/api/studies").status_code == 401
    assert client.get("/api/system/links").status_code == 401


def test_study_changes_publish_an_event(settings):
    sources = SourceManager(
        settings.docs_root, settings.registry_root, settings.repo_root, settings.workspace_dir
    )
    snap_file = settings.registry_root / "studies" / "alpha" / "2026-11-16-abcdef1" / "study.json"
    events = study_change_events(
        sources, {(Change.added, str(snap_file)), (Change.modified, str(settings.registry_root / "x.md"))}
    )
    assert [(e.type, e.data) for e in events] == [("studies.changed", {"projects": ["alpha"]})]
