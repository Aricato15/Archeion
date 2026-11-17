"""Building reports into PDFs (ADR 0025): files, verification, the build and the API, with a fake renderer."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from app.__main__ import main
from app.db import Database
from app.security import COOKIE_NAME
from app.services import report_render as rr
from app.services import reports as rp
from app.services import studies as st
from app.services.sources import SourceManager

from .test_studies import model

ORIGIN = {"Origin": "http://testserver:20301"}


def fake_pdf(pages: int) -> bytes:
    body = b"".join(b"%d 0 obj\n<< /Type /Page /Parent 1 0 R >>\nendobj\n" % (i + 3) for i in range(pages))
    return b"%PDF-1.4\n1 0 obj\n<< /Type /Pages >>\nendobj\n" + body + b"trailer\n%%EOF\n"


class FakeRenderer:
    """Stands in for Edge: writes a PDF with a page per section plus a cover and contents."""

    def __init__(self, failed: int = 0, extra_pages: int = 2) -> None:
        self.calls: list[dict] = []
        self.failed = failed
        self.extra_pages = extra_pages

    def __call__(self, browser, url, out, *, cookie=None, footer_title="", timeout=0):
        self.calls.append({"browser": browser, "url": url, "cookie": cookie, "footer": footer_title})
        sections = int(url.split("sections=")[-1]) if "sections=" in url else 3
        pages = sections + self.extra_pages
        out.write_bytes(fake_pdf(pages))
        return {"sections": sections, "failed": self.failed, "pages": pages}


@pytest.fixture
def manager(settings) -> SourceManager:
    return SourceManager(
        settings.docs_root,
        settings.registry_root,
        settings.repo_root,
        settings.workspace_dir,
        settings.project_roots,
    )


@pytest.fixture
def ready(settings, tmp_path, monkeypatch):
    """A saved preset, an Edge that 'exists', a frontend that 'answers' and a database."""
    Database(settings.db_file).init()
    exe = tmp_path / "edge.exe"
    exe.write_text("", encoding="utf-8")
    monkeypatch.setattr(rp, "find_browser", lambda override="": exe)
    monkeypatch.setattr(rr, "frontend_up", lambda s: True)
    return exe


def save_preset(
    manager, settings, name="full", sections=("overview.facts", "overview.notes", "system.dependencies")
):
    entries = rp.catalog(manager, settings.registry_root, "alpha")
    raw = {"name": name, "mode": "standard", "sections": [{"id": s} for s in sections]}
    return rp.save_preset(settings.registry_root, "alpha", raw, entries)


def sessions(settings) -> int:
    with Database(settings.db_file).conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]


def test_build_writes_the_pdf_and_a_record_and_cleans_up_its_session(settings, manager, ready):
    save_preset(manager, settings)
    renderer = FakeRenderer()
    before = sessions(settings)
    info = rr.build(settings, manager, "alpha", "full", renderer=renderer)
    assert sessions(settings) == before  # the renderer's own session is gone
    assert info["file"].endswith("-full.pdf") and info["sections"] == 3 and info["mode"] == "standard"
    call = renderer.calls[0]
    assert call["url"].startswith("http://127.0.0.1:20301/print/report/alpha?preset=full")
    assert call["cookie"][0] == COOKIE_NAME and len(call["cookie"][1]) > 20  # a session cookie is handed over
    pdf = settings.registry_root / "reports" / "alpha" / info["file"]
    assert pdf.read_bytes().startswith(b"%PDF-")
    assert json.loads(pdf.with_suffix(".json").read_text(encoding="utf-8"))["preset"] == "full"
    assert rr.verify(settings.registry_root, "alpha", info["file"])["ok"]


def test_a_second_build_does_not_overwrite_the_first(settings, manager, ready):
    save_preset(manager, settings)
    first = rr.build(settings, manager, "alpha", "full", renderer=FakeRenderer())
    second = rr.build(settings, manager, "alpha", "full", renderer=FakeRenderer())
    assert first["file"] != second["file"]
    assert [r["file"] for r in rr.list_reports(settings.registry_root, "alpha")] == [
        second["file"],
        first["file"],
    ]


def test_build_says_what_is_missing(settings, manager, ready, monkeypatch):
    save_preset(manager, settings)
    monkeypatch.setattr(rr, "frontend_up", lambda s: False)
    with pytest.raises(rp.ReportError, match="frontend"):
        rr.build(settings, manager, "alpha", "full", renderer=FakeRenderer())
    monkeypatch.setattr(rr, "frontend_up", lambda s: True)
    monkeypatch.setattr(rp, "find_browser", lambda override="": None)
    with pytest.raises(rp.ReportError, match="Edge"):
        rr.build(settings, manager, "alpha", "full", renderer=FakeRenderer())
    with pytest.raises(rp.PresetNotFound):
        rr.build(settings, manager, "alpha", "nope", renderer=FakeRenderer())


def test_a_failed_render_still_removes_the_session(settings, manager, ready):
    save_preset(manager, settings)
    before = sessions(settings)

    def boom(*a, **k):
        raise rr.RenderError("Edge didn't start")

    with pytest.raises(rr.RenderError):
        rr.build(settings, manager, "alpha", "full", renderer=boom)
    assert sessions(settings) == before
    assert rr.list_reports(settings.registry_root, "alpha") == []


def test_verify_finds_a_short_pdf_and_failed_diagrams(settings, manager, ready):
    save_preset(manager, settings)
    folder = settings.registry_root / "reports" / "alpha"
    short = rr.build(
        settings, manager, "alpha", "full", renderer=FakeRenderer(extra_pages=-2)
    )  # fewer pages than sections
    result = rr.verify(settings.registry_root, "alpha", short["file"])
    assert not result["ok"] and "pages" in result["problems"][0]
    bad = rr.build(settings, manager, "alpha", "full", renderer=FakeRenderer(failed=2))
    assert "2 diagram(s) failed" in rr.verify(settings.registry_root, "alpha", bad["file"])["problems"][0]
    (folder / "plain.pdf").write_bytes(b"not a pdf")
    assert "not a PDF" in rr.verify(settings.registry_root, "alpha", "plain.pdf")["problems"]


def test_file_names_cannot_leave_the_folder(settings):
    for name in ("../x.pdf", "a/b.pdf", "x.txt", "..\\x.pdf", ".hidden.pdf"):
        with pytest.raises(rp.ReportError):
            rr.report_file(settings.registry_root, "alpha", name)
    with pytest.raises(rp.PresetNotFound):
        rr.report_file(settings.registry_root, "alpha", "missing.pdf")


def test_delete_removes_the_pdf_and_its_record(settings, manager, ready):
    save_preset(manager, settings)
    info = rr.build(settings, manager, "alpha", "full", renderer=FakeRenderer())
    rr.delete_report(settings.registry_root, "alpha", info["file"])
    assert rr.list_reports(settings.registry_root, "alpha") == []
    assert not list((settings.registry_root / "reports" / "alpha").glob("*.json.bak"))


def test_page_count_ignores_the_pages_tree():
    assert rr.page_count(fake_pdf(5)) == 5


def test_only_one_job_runs_at_a_time():
    jobs = rr.ReportJobs()
    gate = []

    def slow():
        while not gate:
            time.sleep(0.01)
        return {"file": "x.pdf"}

    first = jobs.start("alpha", "full", slow)
    with pytest.raises(rp.ReportError, match="already"):
        jobs.start("alpha", "full", slow)
    gate.append(1)
    for _ in range(200):
        if jobs.get(first["id"])["status"] != "running":
            break
        time.sleep(0.01)
    assert jobs.get(first["id"])["status"] == "done"
    assert jobs.start("alpha", "full", lambda: {})["id"] != first["id"]  # free again: no refusal


def test_a_failing_job_reports_its_error():
    jobs = rr.ReportJobs()

    def boom():
        raise rp.ReportError("no way")

    job = jobs.start("alpha", "full", boom)
    for _ in range(200):
        if jobs.get(job["id"])["status"] != "running":
            break
        time.sleep(0.01)
    assert jobs.get(job["id"])["status"] == "error" and jobs.get(job["id"])["error"] == "no way"


def wait_for(authed, project, job):
    for _ in range(300):
        found = authed.get(f"/api/reports/{project}/builds/{job}").json()
        if found["status"] != "running":
            return found
        time.sleep(0.02)
    raise AssertionError("the build never finished")


def test_api_build_download_verify_delete(authed, settings, manager, ready, monkeypatch):
    save_preset(manager, settings)
    monkeypatch.setattr(rr, "render_pdf", FakeRenderer())
    r = authed.post("/api/reports/alpha/presets/full/build", headers=ORIGIN)
    assert r.status_code == 202
    done = wait_for(authed, "alpha", r.json()["id"])
    assert done["status"] == "done", done
    name = done["result"]["file"]
    assert [f["file"] for f in authed.get("/api/reports/alpha/files").json()] == [name]
    pdf = authed.get(f"/api/reports/alpha/files/{name}")
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    assert "attachment" in pdf.headers["content-disposition"]
    inline = authed.get(f"/api/reports/alpha/files/{name}", params={"inline": "true"})
    assert "inline" in inline.headers["content-disposition"]
    # Only the inline PDF may be framed (by the viewer itself); everything else keeps DENY.
    assert inline.headers["x-frame-options"] == "SAMEORIGIN"
    assert pdf.headers["x-frame-options"] == "DENY"
    assert authed.get("/api/reports/alpha/files").headers["x-frame-options"] == "DENY"
    assert authed.get(f"/api/reports/alpha/files/{name}/verify").json()["ok"]
    assert authed.delete(f"/api/reports/alpha/files/{name}", headers=ORIGIN).status_code == 204
    assert authed.get(f"/api/reports/alpha/files/{name}").status_code == 404


def test_api_build_errors(authed, settings, manager, ready, monkeypatch):
    assert authed.post("/api/reports/alpha/presets/nope/build", headers=ORIGIN).status_code == 404
    save_preset(manager, settings)
    monkeypatch.setattr(rr, "frontend_up", lambda s: False)
    r = authed.post("/api/reports/alpha/presets/full/build", headers=ORIGIN)
    assert r.status_code == 202  # accepted; the job then fails with the reason
    done = wait_for(authed, "alpha", r.json()["id"])
    assert done["status"] == "error" and "frontend" in done["error"]
    assert authed.get("/api/reports/alpha/builds/000000000000").status_code == 404
    assert authed.get("/api/reports/alpha/files/..%2Fx.pdf").status_code in (404, 422)
    assert authed.get("/api/reports/alpha/files/x.txt").status_code == 422


def test_api_needs_login_for_files(client):
    assert client.get("/api/reports/alpha/files").status_code == 401
    assert client.post("/api/reports/alpha/presets/full/build").status_code == 401


def test_cli_build_list_verify(settings, manager, ready, monkeypatch, capsys):
    save_preset(manager, settings)
    monkeypatch.setattr(rr, "render_pdf", FakeRenderer())
    assert main(["report", "build", "alpha", "--preset", "full"], settings) == 0
    assert "Built " in capsys.readouterr().out
    assert main(["report", "list", "alpha", "--json"], settings) == 0
    rows = json.loads(capsys.readouterr().out)
    assert len(rows) == 1 and rows[0]["pages"] == 5
    assert main(["report", "verify", "alpha", rows[0]["file"]], settings) == 0
    assert "OK" in capsys.readouterr().out
    assert main(["report", "verify", "alpha", "missing.pdf"], settings) == 1


def test_study_sections_survive_a_build(settings, manager, ready):
    st.save(settings.registry_root, st.parse(model()))
    save_preset(manager, settings, "study", ("study.map", "study.sub:api", "study.flow:read"))
    info = rr.build(settings, manager, "alpha", "study", renderer=FakeRenderer())
    assert info["sections"] == 3 and info["study"]
    assert isinstance(Path(settings.registry_root / "reports" / "alpha" / info["file"]), Path)
