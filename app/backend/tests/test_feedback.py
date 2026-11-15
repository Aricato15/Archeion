from __future__ import annotations

import json
import threading

import pytest

from app.__main__ import main
from app.services import docs_fs
from app.services import feedback as fb


def _comment(authed, **extra):
    body = {
        "kind": "comment",
        "body": "Tighten this section.",
        "doc_path": "system/overview.md",
        "anchor": {"heading": "Details", "lines": [13, 14], "quote": "Needle"},
        **extra,
    }
    r = authed.post("/api/feedback", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_lifecycle(authed):
    item = _comment(authed)
    assert item["status"] == "open"
    assert item["anchor"] == {"heading": "Details", "lines": [13, 14], "quote": "Needle"}
    assert len(item["doc_rev"]) == 40

    assert authed.get("/api/feedback/summary").json()["open"] == 1
    assert authed.post(f"/api/feedback/{item['id']}/reply", json={"reply": "x"}).status_code == 409
    assert authed.post(f"/api/feedback/{item['id']}/claim").json()["status"] == "in_progress"
    assert authed.post(f"/api/feedback/{item['id']}/claim").status_code == 409
    answered = authed.post(f"/api/feedback/{item['id']}/reply", json={"reply": "Done, see diff."}).json()
    assert answered["status"] == "answered" and answered["reply"] == "Done, see diff."
    resolved = authed.patch(f"/api/feedback/{item['id']}", json={"status": "resolved"}).json()
    assert resolved["status"] == "resolved"
    assert authed.patch(f"/api/feedback/{item['id']}", json={"status": "open"}).json()["status"] == "open"
    assert authed.patch(f"/api/feedback/{item['id']}", json={"status": "answered"}).status_code == 409


def test_filters(authed):
    _comment(authed)
    authed.post("/api/feedback", json={"kind": "prompt", "body": "Plan the next phase."})
    assert len(authed.get("/api/feedback").json()) == 2
    assert len(authed.get("/api/feedback", params={"kind": "prompt"}).json()) == 1
    assert len(authed.get("/api/feedback", params={"doc_path": "system/overview.md"}).json()) == 1
    assert authed.get("/api/feedback", params={"status": "answered"}).json() == []


@pytest.mark.parametrize(
    "payload",
    [
        {"kind": "nope", "body": "x"},
        {"kind": "comment", "body": ""},
        {"kind": "comment", "body": "x", "anchor": {"heading": "H"}},  # anchor without doc
        {"kind": "comment", "body": "x", "doc_path": "system/overview.md", "anchor": {"lines": [5, 2]}},
    ],
)
def test_validation(authed, payload):
    assert authed.post("/api/feedback", json=payload).status_code == 422


@pytest.mark.parametrize("doc", ["../outside.md", "missing.md", "img/pic.svg"])
def test_doc_path_must_be_a_doc(authed, doc):
    r = authed.post("/api/feedback", json={"kind": "comment", "body": "x", "doc_path": doc})
    assert r.status_code in (400, 404)


def test_edit_and_delete_only_while_open(authed):
    item = _comment(authed)
    edited = authed.patch(f"/api/feedback/{item['id']}", json={"body": "Rewritten."}).json()
    assert edited["body"] == "Rewritten."
    authed.post(f"/api/feedback/{item['id']}/claim")
    assert authed.patch(f"/api/feedback/{item['id']}", json={"body": "Again"}).status_code == 409
    assert authed.delete(f"/api/feedback/{item['id']}").status_code == 409
    authed.patch(f"/api/feedback/{item['id']}", json={"status": "open"})  # release
    assert authed.delete(f"/api/feedback/{item['id']}").status_code == 204
    assert authed.get(f"/api/feedback/{item['id']}").status_code == 404


def test_thread(authed):
    root = _comment(authed)
    child = authed.post(
        "/api/feedback",
        json={
            "kind": "comment",
            "body": "And also this.",
            "doc_path": "system/overview.md",
            "parent_id": root["id"],
        },
    ).json()
    grandchild = authed.post(
        "/api/feedback", json={"kind": "prompt", "body": "Last one.", "parent_id": child["id"]}
    ).json()
    data = authed.get(f"/api/feedback/{child['id']}").json()
    assert data["item"]["id"] == child["id"]
    assert [t["id"] for t in data["thread"]] == [root["id"], child["id"], grandchild["id"]]
    assert (
        authed.post("/api/feedback", json={"kind": "prompt", "body": "x", "parent_id": 999}).status_code
        == 404
    )


def test_racing_claims(db):
    with db.conn() as conn:
        item = fb.create(conn, kind="prompt", body="Race me.")
    results: list[str] = []

    def worker():
        with db.conn() as conn:
            try:
                fb.claim(conn, item["id"])
                results.append("won")
            except fb.FeedbackConflict:
                results.append("lost")

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == ["lost"] * 7 + ["won"]


def test_cli_round_trip(settings, db, authed, capsys, tmp_path):
    item = _comment(authed)
    assert main(["inbox", "count"], settings) == 0
    assert capsys.readouterr().out.strip() == "1"

    assert main(["inbox", "list", "--json"], settings) == 0
    listed = json.loads(capsys.readouterr().out)
    assert [i["id"] for i in listed] == [item["id"]]

    assert main(["inbox", "show", str(item["id"])], settings) == 0
    shown = capsys.readouterr().out
    assert "Tighten this section." in shown and "Needle in here." in shown and "> Needle" in shown

    reply_file = tmp_path / "reply.md"
    reply_file.write_text("Tightened it. ✓\n", encoding="utf-8")
    assert main(["inbox", "reply", str(item["id"]), "--file", str(reply_file)], settings) == 1  # not claimed
    capsys.readouterr()
    assert main(["inbox", "claim", str(item["id"])], settings) == 0
    assert main(["inbox", "reply", str(item["id"]), "--file", str(reply_file)], settings) == 0
    got = authed.get(f"/api/feedback/{item['id']}").json()["item"]
    assert got["status"] == "answered" and got["reply"] == "Tightened it. ✓"

    assert main(["inbox", "claim", "999"], settings) == 1
    assert "No feedback item #999" in capsys.readouterr().err


def test_cli_release(settings, db):
    with db.conn() as conn:
        item = fb.create(conn, kind="prompt", body="x")
    assert main(["inbox", "claim", str(item["id"])], settings) == 0
    assert main(["inbox", "release", str(item["id"])], settings) == 0
    with db.conn() as conn:
        assert fb.get(conn, item["id"])["status"] == "open"


def test_excerpt():
    content = "# A\none\n## B\ntwo\nthree\n## C\nfour\n"
    assert docs_fs.excerpt(content, heading="B") == "3 | ## B\n4 | two\n5 | three"
    assert docs_fs.excerpt(content, lines=(4, 4), context=1) == "3 | ## B\n4 | two\n5 | three"
    assert docs_fs.excerpt(content, heading="Missing") == ""


# --- per-project feedback (ADR 0006) ------------------------------------------------------


def test_feedback_for_a_project(authed):
    r = authed.post(
        "/api/feedback",
        json={
            "kind": "comment",
            "body": "Document the auth flow.",
            "source": "alpha",
            "doc_path": "docs/api.md",
            "anchor": {"lines": [1, 1]},
        },
    )
    assert r.status_code == 201, r.text
    item = r.json()
    assert item["source"] == "alpha" and len(item["doc_rev"]) == 40  # alpha's own HEAD
    child = authed.post(
        "/api/feedback", json={"kind": "prompt", "body": "And the errors.", "parent_id": item["id"]}
    )
    assert child.json()["source"] == "alpha"  # follow-ups stay with their project
    assert [i["id"] for i in authed.get("/api/feedback", params={"source": "alpha"}).json()] == [
        child.json()["id"],
        item["id"],
    ]
    assert authed.get("/api/feedback", params={"source": "archeion"}).json() == []
    summary = authed.get("/api/feedback/summary").json()
    assert summary["open"] == 2 and summary["waiting_by_source"] == {"alpha": 2}
    assert authed.get("/api/feedback/summary", params={"source": "archeion"}).json()["open"] == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"kind": "prompt", "body": "x", "source": "nope"},
        {"kind": "comment", "body": "x", "source": "alpha", "doc_path": "src/code.md"},
        {"kind": "comment", "body": "x", "source": "alpha", "doc_path": "docs/../src/code.md"},
    ],
)
def test_project_feedback_validation(authed, payload):
    assert authed.post("/api/feedback", json=payload).status_code in (400, 404)


def test_cli_targets_projects(settings, authed, capsys, monkeypatch):
    authed.post("/api/feedback", json={"kind": "prompt", "body": "Archeion task."})
    authed.post("/api/feedback", json={"kind": "prompt", "body": "Alpha task.", "source": "alpha"})
    authed.post("/api/feedback", json={"kind": "prompt", "body": "Sub task.", "source": "sub1"})

    assert main(["inbox", "list", "--json", "--project", "alpha"], settings) == 0
    assert [i["body"] for i in json.loads(capsys.readouterr().out)] == ["Alpha task."]
    assert main(["inbox", "count", "--project", "archeion"], settings) == 0
    assert capsys.readouterr().out.strip() == "1"

    ws = settings.repo_root.parent
    monkeypatch.setenv("ARCHEION_CALLER_DIR", str(ws / "beta" / "collectors" / "sub1"))
    assert main(["inbox", "list", "--json", "--here"], settings) == 0
    assert [i["body"] for i in json.loads(capsys.readouterr().out)] == ["Sub task."]
    monkeypatch.setenv("ARCHEION_CALLER_DIR", str(settings.repo_root / "docs"))
    assert main(["inbox", "list", "--json", "--here"], settings) == 0
    assert [i["body"] for i in json.loads(capsys.readouterr().out)] == ["Archeion task."]
    monkeypatch.setenv("ARCHEION_CALLER_DIR", str(ws / "beta"))
    assert main(["inbox", "list", "--here"], settings) == 0
    out = capsys.readouterr().out
    # beta's session also gets the items for its module sub1 (ADR 0016), and only those
    assert "[sub1]" in out and "Sub task." in out and "Alpha task." not in out
    assert main(["inbox", "list", "--json", "--project", "beta"], settings) == 0
    assert [i["body"] for i in json.loads(capsys.readouterr().out)] == ["Sub task."]
    assert main(["inbox", "list", "--json", "--project", "sub1"], settings) == 0
    assert [i["body"] for i in json.loads(capsys.readouterr().out)] == ["Sub task."]
    monkeypatch.setenv("ARCHEION_CALLER_DIR", str(ws / "gamma"))
    assert main(["inbox", "list", "--here"], settings) == 1
    assert "isn't inside a registered project" in capsys.readouterr().err
    assert main(["inbox", "list", "--project", "ghost"], settings) == 1


def test_cli_show_project_excerpt(settings, authed, capsys):
    item = authed.post(
        "/api/feedback",
        json={
            "kind": "comment",
            "body": "Check this.",
            "source": "alpha",
            "doc_path": "docs/api.md",
            "anchor": {"lines": [7, 7]},
        },
    ).json()
    assert main(["inbox", "show", str(item["id"])], settings) == 0
    out = capsys.readouterr().out
    assert "[alpha] docs/api.md" in out and "docs/api.md in alpha" in out and "Alpha haystack." in out
