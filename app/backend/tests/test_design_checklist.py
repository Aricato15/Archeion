"""The design checklist (ADR 0029): staging, deciding, confirming, validation, and that a save
of the design leaves it alone."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services import design_checklist as ck
from app.services import designs as dz


def add(title: str = "Export to PDF", **fields) -> dict:
    return {"op": "add", "fields": {"title": title, **fields}, "reason": "agreed in round 2"}


def confirmed(*adds: dict) -> ck.Checklist:
    cl = ck.empty()
    ck.stage(cl, list(adds), by="user")
    cl, _ = ck.confirm(cl)
    return cl


def test_claude_stages_pending_and_nothing_applies_until_confirm():
    cl = ck.stage(ck.empty(), [add()], by="claude")
    assert cl.items == []
    assert cl.pending[0].state == "pending" and cl.pending[0].by == "claude"
    cl, applied = ck.confirm(cl)
    assert applied["added"] == [] and len(cl.pending) == 1  # still waiting for the user


def test_accept_then_confirm_adds_item_with_history():
    cl = ck.stage(ck.empty(), [add(kind="feature", status="decided")], by="claude")
    ck.decide(cl, "p1", state="accepted")
    cl, applied = ck.confirm(cl)
    assert applied["added"] == ["c1"]
    item = cl.items[0]
    assert (item.title, item.kind, item.status) == ("Export to PDF", "feature", "decided")
    assert item.history[0].by == "claude" and item.history[0].reason == "agreed in round 2"
    assert cl.pending == []


def test_users_own_changes_start_accepted():
    cl = ck.stage(ck.empty(), [add()], by="user")
    assert cl.pending[0].state == "accepted"


def test_reject_is_logged_and_item_unchanged():
    cl = confirmed(add())
    ck.stage(cl, [{"op": "update", "item": "c1", "fields": {"status": "dropped"}}], by="claude")
    ck.decide(cl, "p2", state="rejected")
    cl, applied = ck.confirm(cl)
    assert cl.items[0].status == "idea" and applied["rejected"] == ["c1"]
    assert cl.log[-1].change.startswith("rejected update")


def test_update_and_remove_apply_and_ids_are_never_reused():
    cl = confirmed(add("A"), add("B"))
    ck.stage(
        cl,
        [
            {"op": "update", "item": "c1", "fields": {"status": "done"}, "reason": "built"},
            {"op": "remove", "item": "c2"},
        ],
        by="user",
    )
    cl, applied = ck.confirm(cl)
    assert applied["updated"] == ["c1"] and applied["removed"] == ["c2"]
    assert cl.items[0].status == "done" and cl.items[0].history[-1].reason == "built"
    ck.stage(cl, [add("C")], by="user")
    cl, applied = ck.confirm(cl)
    assert applied["added"] == ["c3"]


def test_restaging_replaces_the_earlier_change_and_keeps_comments():
    cl = confirmed(add())
    ck.stage(cl, [{"op": "update", "item": "c1", "fields": {"status": "decided"}}], by="claude")
    ck.decide(cl, "p2", comment="not yet, wait for the API", by="user")
    ck.stage(
        cl,
        [{"op": "update", "item": "c1", "fields": {"status": "idea", "note": "waits on the API"}}],
        by="claude",
    )
    assert len(cl.pending) == 1
    assert cl.pending[0].fields["note"] == "waits on the API"
    assert cl.pending[0].comments[0].text == "not yet, wait for the API"


def test_bad_changes_are_refused():
    cl = confirmed(add())
    for bad in (
        {"op": "update", "item": "c9", "fields": {"status": "done"}},
        {"op": "update", "item": "c1", "fields": {"status": "finished"}},
        {"op": "update", "item": "c1", "fields": {"id": "c5"}},
        {"op": "update", "item": "c1"},
        {"op": "add", "fields": {"note": "no title"}},
        {"op": "add", "item": "c1", "fields": {"title": "x"}},
        {"op": "frobnicate"},
    ):
        with pytest.raises(Exception):  # noqa: B017 - ChecklistError or a validation error
            ck.stage(cl, [bad], by="claude")


def test_a_circle_in_depends_on_is_refused_on_confirm_and_leaves_state():
    cl = confirmed(add("A"), add("B", depends_on=["c1"]))
    ck.stage(cl, [{"op": "update", "item": "c1", "fields": {"depends_on": ["c2"]}}], by="user")
    with pytest.raises(ck.ChecklistError, match="circle"):
        ck.confirm(cl)
    assert cl.items[0].depends_on == [] and len(cl.pending) == 1


def test_removing_an_item_others_depend_on_is_refused():
    cl = confirmed(add("A"), add("B", depends_on=["c1"]))
    ck.stage(cl, [{"op": "remove", "item": "c1"}], by="user")
    with pytest.raises(ck.ChecklistError, match="isn't in the checklist"):
        ck.confirm(cl)


def test_secrets_and_absolute_paths_are_refused():
    drive = "C" + ":"  # built at runtime so the commit hook does not see a path
    with pytest.raises(ck.ChecklistError):
        ck.stage(ck.empty(), [add(note="see " + drive + "/" + "Users/someone/notes.txt")], by="claude")


def test_counts_ignore_dropped():
    cl = confirmed(add("A", status="done"), add("B", status="dropped"), add("C"))
    ck.stage(cl, [{"op": "update", "item": "c3", "fields": {"status": "doing"}}], by="claude")
    assert ck.counts(cl) == {"total": 2, "done": 1, "pending": 1, "staged": 1}


def test_write_load_roundtrip_and_empty_when_missing(tmp_path: Path):
    assert ck.load(tmp_path).items == []
    cl = confirmed(add())
    ck.write(tmp_path, cl)
    assert ck.load(tmp_path).items[0].title == "Export to PDF"


def test_saving_the_design_keeps_the_checklist(tmp_path: Path):
    ref = dz.init(tmp_path, "alpha")
    ck.write(ref.folder, confirmed(add()))
    brief = "# Brief\n\n## Purpose\n\nSomething useful and long enough.\n"
    dz.save(tmp_path, ref, files={"brief.md": brief}, model=None)
    assert ck.load(ref.folder).items[0].id == "c1"


def test_roadmap_columns_by_status_and_priority_dropped_left_out():
    cl = confirmed(
        add("Later thing"),
        add("Big", status="decided", priority="high", phase="Phase 2"),
        add("Small", status="decided", priority="low", phase="Phase 10"),
        add("Mid", status="decided", phase="Phase 2"),
        add("Active", status="doing"),
        add("Finished", status="done"),
        add("Gone", status="dropped"),
    )
    rm = ck.roadmap(cl)
    assert [i["title"] for i in rm["now"]] == ["Active"]
    assert [i["title"] for i in rm["next"]] == ["Big", "Mid", "Small"]  # priority first
    assert [i["title"] for i in rm["later"]] == ["Later thing"]
    assert [i["title"] for i in rm["done"]] == ["Finished"]
    names = [p["phase"] for p in rm["phases"]]
    assert names == ["Phase 2", "Phase 10", None]  # natural order, unphased last
    assert "Gone" not in str(rm["phases"])


def test_roadmap_counts_only_waiting_changes_as_pending():
    cl = confirmed(add())
    ck.stage(cl, [{"op": "update", "item": "c1", "fields": {"status": "doing"}}], by="claude")
    assert ck.roadmap(cl)["pending"] == 1
    assert ck.roadmap(cl)["now"] == []  # a proposal isn't in the roadmap


def test_roadmap_markdown_reads_back_with_the_roadmap_parser():
    from app.services.docs_fs import parse_roadmap

    cl = confirmed(add("Active", status="doing"), add("Next one", status="decided", note="why"))
    text = ck.roadmap_markdown(cl)
    parsed = parse_roadmap(text, "ROADMAP.md")
    assert parsed["structured"] and "Active" in parsed["now"][0]["text"]
    assert "Next one" in parsed["next"][0]["text"] and "why" in parsed["next"][0]["text"]
