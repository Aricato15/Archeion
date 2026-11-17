"""Project glossaries (ADR 0023): the service, the API and the CLI."""

from __future__ import annotations

import pytest

from app.__main__ import main
from app.services import glossary as gl

ORIGIN = {"Origin": "http://testserver:20301"}


def test_upsert_load_remove(tmp_path):
    entry = gl.upsert(
        tmp_path, "alpha", {"term": "Gateway", "definition": "The front door.", "aliases": ["GW", "gw"]}
    )
    assert entry == {"id": "gateway", "term": "Gateway", "aliases": ["GW"], "definition": "The front door."}
    gl.upsert(tmp_path, "alpha", {"term": "audit log", "definition": "Who did what."})
    assert [t["term"] for t in gl.load(tmp_path, "alpha")] == ["audit log", "Gateway"]
    gl.remove(tmp_path, "alpha", "gateway")
    assert [t["id"] for t in gl.load(tmp_path, "alpha")] == ["audit-log"]
    with pytest.raises(gl.TermNotFound):
        gl.remove(tmp_path, "alpha", "gateway")


def test_names_and_aliases_are_unique_ignoring_case(tmp_path):
    gl.upsert(tmp_path, "alpha", {"term": "Gateway", "definition": "x", "aliases": ["GW"]})
    with pytest.raises(gl.GlossaryError):
        gl.upsert(tmp_path, "alpha", {"term": "gateway", "definition": "y"})
    with pytest.raises(gl.GlossaryError):
        gl.upsert(tmp_path, "alpha", {"term": "Other", "definition": "y", "aliases": ["gw"]})


def test_rename_keeps_one_entry(tmp_path):
    gl.upsert(tmp_path, "alpha", {"term": "Gateway", "definition": "x"})
    gl.upsert(tmp_path, "alpha", {"term": "Edge", "definition": "x"}, replace="gateway")
    assert [t["id"] for t in gl.load(tmp_path, "alpha")] == ["edge"]


@pytest.mark.parametrize(
    "raw",
    [{"term": "", "definition": "x"}, {"term": "x", "definition": " "}, {"term": "!!!", "definition": "x"}],
)
def test_invalid_entries_are_refused(tmp_path, raw):
    with pytest.raises(gl.GlossaryError):
        gl.upsert(tmp_path, "alpha", raw)


def test_unreadable_file_is_an_empty_glossary(tmp_path):
    (tmp_path / "glossary").mkdir()
    (tmp_path / "glossary" / "alpha.json").write_text("{not json", encoding="utf-8")
    assert gl.load(tmp_path, "alpha") == []


def test_project_name_cannot_leave_the_folder(tmp_path):
    with pytest.raises(gl.GlossaryError):
        gl.load(tmp_path, "../x")


def test_api_needs_login(client):
    assert client.get("/api/glossary/alpha").status_code == 401


def test_api_round_trip(authed):
    assert authed.get("/api/glossary/alpha").json() == []
    r = authed.post(
        "/api/glossary/alpha", json={"term": "Gateway", "definition": "The front door."}, headers=ORIGIN
    )
    assert r.status_code == 201 and r.json()["id"] == "gateway"
    r = authed.put(
        "/api/glossary/alpha/gateway",
        json={"term": "Gateway", "definition": "Changed.", "aliases": ["GW"]},
        headers=ORIGIN,
    )
    assert r.status_code == 200
    assert authed.get("/api/glossary/alpha").json()[0]["aliases"] == ["GW"]
    assert (
        authed.post("/api/glossary/alpha", json={"term": "gw", "definition": "x"}, headers=ORIGIN).status_code
        == 422
    )
    assert authed.delete("/api/glossary/alpha/gateway", headers=ORIGIN).status_code == 204
    assert authed.delete("/api/glossary/alpha/gateway", headers=ORIGIN).status_code == 404


def test_api_unknown_project(authed):
    assert authed.get("/api/glossary/nope").status_code == 404


def test_cli(settings, capsys):
    assert main(["glossary", "set", "alpha", "Gateway", "The front door.", "--alias", "GW"], settings) == 0
    assert main(["glossary", "set", "alpha", "Gateway", "Changed."], settings) == 0
    assert main(["glossary", "list", "alpha"], settings) == 0
    out = capsys.readouterr().out
    assert "Added 'Gateway'" in out and "Updated 'Gateway'" in out and "Gateway: Changed." in out
    assert main(["glossary", "remove", "alpha", "Gateway"], settings) == 0
    assert main(["glossary", "remove", "alpha", "Gateway"], settings) == 1
    assert main(["glossary", "list", "nope"], settings) == 1
