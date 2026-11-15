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
    # an answered item never goes back to open: reopening adds a message instead
    assert authed.patch(f"/api/feedback/{item['id']}", json={"status": "open"}).status_code == 409
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


def _answer(authed, item_id: int, text: str = "Done.") -> dict:
    assert authed.post(f"/api/feedback/{item_id}/claim").status_code == 200
    r = authed.post(f"/api/feedback/{item_id}/reply", json={"reply": text})
    assert r.status_code == 200, r.text
    return r.json()


def _follow_up(authed, parent_id: int, body: str = "And also this."):
    return authed.post("/api/feedback", json={"body": body, "parent_id": parent_id})


def test_thread(authed):
    root = _comment(authed)
    _answer(authed, root["id"])
    child = _follow_up(authed, root["id"]).json()
    # a follow-up takes the thread's kind, project and doc, and joins its thread
    assert (child["kind"], child["source"], child["doc_path"]) == (
        "comment",
        "archeion",
        "system/overview.md",
    )
    assert child["thread_id"] == root["id"] and child["parent_id"] == root["id"]
    _answer(authed, child["id"])
    # replying to an older message still goes after the thread's latest one
    grandchild = _follow_up(authed, root["id"], "Last one.").json()
    assert grandchild["parent_id"] == child["id"] and grandchild["thread_id"] == root["id"]
    data = authed.get(f"/api/feedback/{child['id']}").json()
    assert data["item"]["id"] == child["id"]
    assert [t["id"] for t in data["thread"]] == [root["id"], child["id"], grandchild["id"]]
    assert _follow_up(authed, 999).status_code == 404
    # a new thread still needs a kind
    assert authed.post("/api/feedback", json={"body": "x"}).status_code == 422


def test_one_waiting_item_per_thread(authed):
    root = _comment(authed)
    assert _follow_up(authed, root["id"]).status_code == 409  # still open: edit it instead
    authed.post(f"/api/feedback/{root['id']}/claim")
    assert _follow_up(authed, root["id"]).status_code == 409  # Claude is on it
    authed.post(f"/api/feedback/{root['id']}/reply", json={"reply": "Done."})
    child = _follow_up(authed, root["id"])
    assert child.status_code == 201
    assert _follow_up(authed, root["id"]).status_code == 409


def test_the_list_shows_threads(authed):
    root = _comment(authed)
    _answer(authed, root["id"], "First answer.")
    child = _follow_up(authed, root["id"], "Not quite.").json()
    other = authed.post("/api/feedback", json={"kind": "prompt", "body": "Plan it."}).json()

    rows = authed.get("/api/feedback").json()
    assert [r["id"] for r in rows] == [other["id"], root["id"]]
    thread = rows[1]
    assert thread["status"] == "open"  # its latest message waits for Claude
    assert thread["messages"] == 2 and thread["latest_id"] == child["id"]
    assert thread["body"] == "Tighten this section." and thread["reply"] == "First answer."
    assert [r["id"] for r in authed.get("/api/feedback", params={"status": "open"}).json()] == [
        other["id"],
        root["id"],
    ]
    assert authed.get("/api/feedback", params={"status": "answered"}).json() == []
    summary = authed.get("/api/feedback/summary").json()
    assert (summary["open"], summary["answered"]) == (2, 0)
    assert summary["waiting_by_source"] == {"archeion": 2}


def test_resolving_resolves_the_thread(authed):
    root = _comment(authed)
    _answer(authed, root["id"])
    child = _follow_up(authed, root["id"]).json()
    _answer(authed, child["id"])
    # resolving from any message closes every message in the thread
    assert authed.patch(f"/api/feedback/{root['id']}", json={"status": "resolved"}).status_code == 200
    thread = authed.get(f"/api/feedback/{root['id']}").json()["thread"]
    assert {t["status"] for t in thread} == {"resolved"}
    assert authed.get("/api/feedback/summary").json()["resolved"] == 1
    # only the latest message can be reopened
    assert authed.patch(f"/api/feedback/{root['id']}", json={"status": "open"}).status_code == 409
    # a reply to a resolved thread reopens it
    again = _follow_up(authed, root["id"], "One more thing.").json()
    assert again["status"] == "open"
    assert authed.get("/api/feedback").json()[0]["status"] == "open"
    # can't resolve while Claude works on it
    authed.post(f"/api/feedback/{again['id']}/claim")
    assert authed.patch(f"/api/feedback/{root['id']}", json={"status": "resolved"}).status_code == 409
    authed.patch(f"/api/feedback/{again['id']}", json={"status": "open"})  # release
    # dismissing the waiting message resolves the thread too
    assert authed.patch(f"/api/feedback/{again['id']}", json={"status": "resolved"}).status_code == 200
    assert {t["status"] for t in authed.get(f"/api/feedback/{root['id']}").json()["thread"]} == {"resolved"}


def test_reopen_adds_a_message(authed):
    root = _comment(authed)
    _answer(authed, root["id"], "First answer.")
    authed.patch(f"/api/feedback/{root['id']}", json={"status": "resolved"})
    r = authed.post(f"/api/feedback/{root['id']}/reopen")
    assert r.status_code == 201, r.text
    again = r.json()
    assert again["body"] == fb.REOPENED and again["status"] == "open"
    assert (again["thread_id"], again["parent_id"], again["kind"]) == (root["id"], root["id"], "comment")
    thread = authed.get(f"/api/feedback/{root['id']}").json()["thread"]
    assert [t["reply"] for t in thread] == ["First answer.", None]  # the answer is kept
    assert authed.get("/api/feedback").json()[0]["status"] == "open"
    assert authed.post(f"/api/feedback/{root['id']}/reopen").status_code == 409  # one waits already
    _answer(authed, again["id"])
    with_text = authed.post(f"/api/feedback/{again['id']}/reopen", json={"body": "Still too long."}).json()
    assert with_text["body"] == "Still too long."
    assert authed.post("/api/feedback/999/reopen").status_code == 404


def test_migration_turns_old_reopens_into_messages(tmp_path):
    from app.db import MIGRATIONS, connect, migrate

    conn = connect(tmp_path / "old.db")
    conn.execute("BEGIN IMMEDIATE")
    for m in MIGRATIONS[:6]:
        m(conn)
    conn.execute("PRAGMA user_version = 6")
    conn.execute("COMMIT")
    rows = (
        (1, None, 1, "open", "Old answer."),  # reopened the old way
        (2, None, 2, "answered", "Fine."),
        (3, None, 3, "open", None),  # a new request
        (4, None, 4, "open", "Earlier answer."),  # reopened, but a message came after it
        (5, 4, 4, "answered", "Later answer."),
    )
    for i, parent, thread, status, reply in rows:
        conn.execute(
            "INSERT INTO feedback (id, kind, source, body, parent_id, thread_id, status, reply,"
            " created_at, updated_at) VALUES (?, 'prompt', 'alpha', 'x', ?, ?, ?, ?, 'c', 'u')",
            (i, parent, thread, status, reply),
        )
    migrate(conn)
    got = [
        tuple(r)
        for r in conn.execute("SELECT id, thread_id, parent_id, status, source FROM feedback ORDER BY id")
    ]
    assert got == [
        (1, 1, None, "answered", "alpha"),
        (2, 2, None, "answered", "alpha"),
        (3, 3, None, "open", "alpha"),
        (4, 4, None, "answered", "alpha"),
        (5, 4, 4, "answered", "alpha"),
        (6, 1, 1, "open", "alpha"),
    ]
    assert conn.execute("SELECT reply FROM feedback WHERE id = 1").fetchone()[0] == "Old answer."
    assert conn.execute("SELECT created_at FROM feedback WHERE id = 6").fetchone()[0] == "u"
    conn.close()


def test_delete_only_the_waiting_end_of_a_thread(authed, db):
    root = _comment(authed)
    _answer(authed, root["id"])
    child = _follow_up(authed, root["id"]).json()
    assert authed.delete(f"/api/feedback/{root['id']}").status_code == 409
    assert authed.delete(f"/api/feedback/{child['id']}").status_code == 204
    assert [t["id"] for t in authed.get(f"/api/feedback/{root['id']}").json()["thread"]] == [root["id"]]
    with db.conn() as conn:
        # an open root with replies (only from data older than threads) still can't be deleted
        conn.execute("UPDATE feedback SET status = 'open' WHERE id = ?", (root["id"],))
        conn.execute(
            "INSERT INTO feedback (kind, body, parent_id, thread_id, created_at, updated_at)"
            " VALUES ('comment', 'old reply', ?, ?, 'x', 'x')",
            (root["id"], root["id"]),
        )
    assert authed.delete(f"/api/feedback/{root['id']}").status_code == 409


def test_migration_backfills_threads(tmp_path):
    from app.db import MIGRATIONS, connect, migrate

    conn = connect(tmp_path / "old.db")
    conn.execute("BEGIN IMMEDIATE")
    for m in MIGRATIONS[:5]:
        m(conn)
    conn.execute("PRAGMA user_version = 5")
    conn.execute("COMMIT")
    for i, parent in ((1, None), (2, 1), (3, 2), (4, None), (5, None)):
        conn.execute(
            "INSERT INTO feedback (id, kind, body, parent_id, created_at, updated_at)"
            " VALUES (?, 'prompt', 'x', ?, 'x', 'x')",
            (i, parent),
        )
    conn.execute("DELETE FROM feedback WHERE id = 4")
    migrate(conn)
    rows = conn.execute("SELECT id, thread_id FROM feedback ORDER BY id").fetchall()
    assert [tuple(r) for r in rows] == [(1, 1), (2, 1), (3, 1), (5, 5)]
    conn.close()


def test_cli_show_gives_the_whole_conversation(settings, authed, capsys):
    root = _comment(authed)
    long_answer = "I tightened it. " + "Detail. " * 60
    _answer(authed, root["id"], long_answer)
    child = _follow_up(authed, root["id"], "Shorter still, please.").json()

    assert main(["inbox", "list"], settings) == 0
    assert f"follow-up in thread #{root['id']}" in capsys.readouterr().out
    assert main(["inbox", "show", str(child["id"])], settings) == 0
    out = capsys.readouterr().out
    assert "Conversation so far (2 messages" in out
    assert long_answer.strip() in out  # in full, not cut short
    assert out.index("Tighten this section.") < out.index(f"Your request now (#{child['id']}")
    assert out.index(f"Your request now (#{child['id']}") < out.rindex("Shorter still, please.")
    assert "> Needle" in out and "Needle in here." in out  # the root's quote and excerpt

    assert main(["inbox", "show", str(child["id"]), "--json"], settings) == 0
    data = json.loads(capsys.readouterr().out)
    assert "Shorter still, please." in data["conversation"] and len(data["thread"]) == 2
    assert data["excerpt"]


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
    second = authed.post(
        "/api/feedback", json={"kind": "prompt", "body": "And the errors.", "source": "alpha"}
    ).json()
    _answer(authed, item["id"])
    child = authed.post(
        "/api/feedback", json={"body": "And the retries.", "parent_id": item["id"], "source": "archeion"}
    )
    assert child.json()["source"] == "alpha"  # a thread stays with its project
    assert [i["id"] for i in authed.get("/api/feedback", params={"source": "alpha"}).json()] == [
        item["id"],
        second["id"],
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
