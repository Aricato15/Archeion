"""Turning a report into a PDF (ADR 0025): headless Edge prints the frontend's print route.

Edge is driven over the DevTools protocol (the `websockets` package, which uvicorn already needs).
It gets a session of its own, created here and deleted when the build ends, set as a cookie through
the protocol, so the print route needs no way in that other pages don't have. The build waits for
the print page to say every diagram is drawn (`document.body.dataset.reportState`), then prints
with page numbers in the footer. The PDF is written only to `registry/reports/<project>/`.
"""

from __future__ import annotations

import base64
import contextlib
import html
import json
import re
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path

from websockets.sync.client import connect as ws_connect

from ..config import Settings
from ..db import Database
from ..security import COOKIE_NAME, create_session, delete_session
from . import reports as rp
from .sources import SourceManager

READY_TIMEOUT = 180  # seconds for every diagram to draw
LAUNCH_TIMEOUT = 20
FILE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,120}\.pdf$")


class RenderError(RuntimeError):
    pass


# --- files ------------------------------------------------------------------------------


def project_dir(registry_root: Path, project: str) -> Path:
    return rp._folder(registry_root, project)


def _next_name(folder: Path, preset: str) -> str:
    base = f"{date.today().isoformat()}-{preset}"
    name, n = f"{base}.pdf", 1
    while (folder / name).exists():
        n += 1
        name = f"{base}-{n}.pdf"
    return name


def report_file(registry_root: Path, project: str, filename: str) -> Path:
    """A built report by file name; the name can't point outside the project's folder."""
    if not FILE_NAME.match(filename):
        raise rp.ReportError("bad file name")
    path = project_dir(registry_root, project) / filename
    if not path.is_file():
        raise rp.PresetNotFound(filename)
    return path


def _sidecar(pdf: Path) -> Path:
    return pdf.with_suffix(".json")


def list_reports(registry_root: Path, project: str) -> list[dict]:
    """Built reports, newest first, with what the build recorded about each."""
    folder = project_dir(registry_root, project)
    if not folder.is_dir():
        return []
    out = []
    for pdf in folder.glob("*.pdf"):
        if not FILE_NAME.match(pdf.name):
            continue
        try:
            info = json.loads(_sidecar(pdf).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            info = {}
        stat = pdf.stat()
        out.append({"file": pdf.name, "bytes": stat.st_size, "_at": stat.st_mtime_ns, **info})
    out.sort(key=lambda r: r["_at"], reverse=True)  # by when the file was written: builds can share a second
    for r in out:
        del r["_at"]
    return out


def delete_report(registry_root: Path, project: str, filename: str) -> None:
    pdf = report_file(registry_root, project, filename)
    pdf.unlink()
    _sidecar(pdf).unlink(missing_ok=True)


def page_count(data: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page(?![a-zA-Z])", data))


def verify(registry_root: Path, project: str, filename: str) -> dict:
    """Checks a built report against what its build recorded. `problems` is empty when it's sound."""
    pdf = report_file(registry_root, project, filename)
    data = pdf.read_bytes()
    problems: list[str] = []
    if not data.startswith(b"%PDF-"):
        problems.append("not a PDF")
    if b"%%EOF" not in data[-2048:]:
        problems.append("the PDF is cut short")
    pages = page_count(data)
    try:
        info = json.loads(_sidecar(pdf).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        info = {}
        problems.append("no build record next to it")
    if info:
        # Cover, contents and every section each start a page.
        options = info.get("options", {})
        least = (
            info.get("sections", 0) + (1 if options.get("cover") else 0) + (1 if options.get("toc") else 0)
        )
        if pages < least:
            problems.append(f"{pages} pages, but at least {least} are expected")
        if info.get("failed"):
            problems.append(f"{info['failed']} diagram(s) failed to draw")
    return {"file": filename, "pages": pages, "bytes": len(data), "problems": problems, "ok": not problems}


# --- the browser ------------------------------------------------------------------------


class _Cdp:
    """Just enough of the DevTools protocol: send a command, wait for its answer."""

    def __init__(self, url: str) -> None:
        self.ws = ws_connect(url, max_size=None, open_timeout=LAUNCH_TIMEOUT)
        self.n = 0

    def call(self, method: str, **params) -> dict:
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv(timeout=LAUNCH_TIMEOUT + READY_TIMEOUT))
            if msg.get("id") == self.n:
                if "error" in msg:
                    raise RenderError(f"{method}: {msg['error'].get('message', msg['error'])}")
                return msg.get("result", {})

    def eval(self, expression: str):
        res = self.call("Runtime.evaluate", expression=expression, returnByValue=True)
        return res.get("result", {}).get("value")

    def close(self) -> None:
        with contextlib.suppress(Exception):  # closing a socket that is already dead
            self.ws.close()


_STATE = (
    "JSON.stringify({s: document.body.dataset.reportState || '',"
    " f: document.body.dataset.reportFailed || '0',"
    " n: document.body.dataset.reportSections || '0', e: document.body.dataset.reportError || ''})"
)


def _footer(title: str) -> str:
    return (
        '<div style="font-size:8px;width:100%;padding:0 14mm;display:flex;justify-content:space-between;'
        f'color:#868e96"><span>{html.escape(title)}</span>'
        '<span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>'
    )


def render_pdf(
    browser: Path,
    url: str,
    out: Path,
    *,
    cookie: tuple[str, str] | None = None,
    footer_title: str = "",
    timeout: float = READY_TIMEOUT,
) -> dict:
    """Opens `url` in headless Edge, waits until the page says it's ready and prints it to `out`.
    Returns what the page reported: sections drawn and diagrams that failed."""
    profile = Path(tempfile.mkdtemp(prefix="archeion-report-"))
    args = [
        str(browser),
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-extensions",
        "--remote-debugging-port=0",
        f"--user-data-dir={profile}",
        "about:blank",
    ]
    proc = subprocess.Popen(
        args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    cdp: _Cdp | None = None
    try:
        port_file = profile / "DevToolsActivePort"
        deadline = time.monotonic() + LAUNCH_TIMEOUT
        while not port_file.is_file() or len(port_file.read_text().split()) < 2:
            if proc.poll() is not None or time.monotonic() > deadline:
                raise RenderError(
                    "Edge didn't start (is another copy using the same profile, or is it blocked?)"
                )
            time.sleep(0.1)
        port = int(port_file.read_text().split()[0])
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=LAUNCH_TIMEOUT) as r:
            pages = [t for t in json.load(r) if t.get("type") == "page"]
        if not pages:
            raise RenderError("Edge opened no page")
        cdp = _Cdp(pages[0]["webSocketDebuggerUrl"])
        cdp.call("Page.enable")
        cdp.call("Network.enable")
        if cookie:
            cdp.call(
                "Network.setCookie",
                name=cookie[0],
                value=cookie[1],
                url=url,
                path="/",
                httpOnly=True,
            )
        cdp.call("Page.navigate", url=url)
        state: dict = {}
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            raw = cdp.eval(_STATE)
            state = json.loads(raw) if raw else {}
            if state.get("s") in ("ready", "error"):
                break
            time.sleep(0.4)
        else:
            raise RenderError(f"the report page wasn't ready after {int(timeout)} seconds")
        if state["s"] == "error":
            raise RenderError(f"the report page couldn't be built: {state.get('e') or 'unknown error'}")
        result = cdp.call(
            "Page.printToPDF",
            preferCSSPageSize=True,
            printBackground=True,
            displayHeaderFooter=True,
            headerTemplate="<span></span>",
            footerTemplate=_footer(footer_title),
        )
        data = base64.b64decode(result["data"])
        tmp = out.with_suffix(".pdf.tmp")
        tmp.write_bytes(data)
        tmp.replace(out)
        return {
            "sections": int(state.get("n") or 0),
            "failed": int(state.get("f") or 0),
            "pages": page_count(data),
        }
    finally:
        if cdp:
            cdp.close()
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(profile, ignore_errors=True)


# --- building ---------------------------------------------------------------------------


def frontend_url(settings: Settings) -> str:
    return f"http://127.0.0.1:{settings.frontend_port}"


def frontend_up(settings: Settings) -> bool:
    try:
        with urllib.request.urlopen(frontend_url(settings) + "/", timeout=3):
            return True
    except (urllib.error.URLError, OSError):
        return False


def build(
    settings: Settings,
    manager: SourceManager,
    project_id: str,
    preset_name: str,
    *,
    renderer: Callable[..., dict] | None = None,
) -> dict:
    """Builds a saved preset into a PDF in the registry and records what the build saw.
    Raises ReportError for anything the user can fix (no Edge, frontend not running, bad preset)."""
    registry_root = settings.registry_root
    preset = rp.get_preset(registry_root, project_id, preset_name)
    resolved = rp.content(manager, registry_root, project_id, preset)  # refuses a preset that's gone stale
    browser = rp.find_browser(settings.report_browser)
    if browser is None:
        raise rp.ReportError("headless Edge wasn't found; set ARCHEION_REPORT_BROWSER in .env")
    if not frontend_up(settings):
        raise rp.ReportError(
            f"the viewer's frontend isn't answering at {frontend_url(settings)}; start it with start.bat"
        )
    folder = project_dir(registry_root, project_id)
    folder.mkdir(parents=True, exist_ok=True)
    name = _next_name(folder, preset_name)
    query = urllib.parse.urlencode({"preset": preset_name})
    url = f"{frontend_url(settings)}/print/report/{urllib.parse.quote(project_id)}?{query}"
    db = Database(settings.db_file)
    with db.conn() as conn:
        raw, _ = create_session(conn, settings.session_idle_hours, 0.05)  # lives about an hour; deleted below
        try:
            seen = (renderer or render_pdf)(
                browser,
                url,
                folder / name,
                cookie=(COOKIE_NAME, raw),
                footer_title=preset.get("title") or resolved["project"]["title"],
            )
        finally:
            delete_session(conn, raw)
    options = resolved["preset"]["options"]
    record = {
        "preset": preset_name,
        "mode": preset["mode"],
        "title": preset.get("title", ""),
        "built": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sections": len(resolved["sections"]),
        "options": options,
        "study": (resolved["study"] or {}).get("id"),
        "pages": seen["pages"],
        "failed": seen["failed"],
    }
    _sidecar(folder / name).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return {"file": name, **record}


# --- background builds (the API) --------------------------------------------------------


class ReportJobs:
    """Builds started from the viewer run in a thread, one at a time (Edge is heavy), and are
    polled by id. Held in memory: a restart forgets them, the PDFs stay."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.jobs: dict[str, dict] = {}

    def running(self) -> bool:
        return any(j["status"] == "running" for j in self.jobs.values())

    def start(self, project: str, preset: str, work: Callable[[], dict]) -> dict:
        with self._lock:
            if self.running():
                raise rp.ReportError("a report is already being built; wait for it to finish")
            job = {"id": uuid.uuid4().hex[:12], "project": project, "preset": preset, "status": "running"}
            self.jobs[job["id"]] = job
            for old in list(self.jobs)[:-20]:
                self.jobs.pop(old, None)

        def run() -> None:
            try:
                job["result"] = work()
                job["status"] = "done"
            except Exception as exc:  # noqa: BLE001 - reported to whoever polls the job
                job["error"] = str(exc)
                job["status"] = "error"

        threading.Thread(target=run, name=f"report-{job['id']}", daemon=True).start()
        return dict(job)

    def get(self, job_id: str) -> dict | None:
        job = self.jobs.get(job_id)
        return dict(job) if job else None
