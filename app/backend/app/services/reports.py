"""Project PDF reports (ADR 0025): the section catalog, the presets and the browser check.

A report is built from a **preset**: an ordered list of sections, each either *sourced* (an entry of
the project's catalog, shown as it is) or *authored* (text Claude wrote for a guided report, every
claim citing catalog sections). Presets live in the private registry as
`registry/reports/<project>/presets.json`, and every write is a validated, atomic replace of that
one file. Nothing here reads a project's files except through its read-only source.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from datetime import date
from pathlib import Path

from . import designs as dz
from . import glossary as gl
from . import studies as st
from .registry import split_frontmatter
from .sources import REGISTRY_ID, SourceManager

REPORTS_DIR = "reports"
PRESETS_FILE = "presets.json"

MODES = ("standard", "guided")
PAGE_SIZES = ("A4", "Letter")
ORIENTATIONS = ("portrait", "landscape")

MAX_SECTIONS = 300
MAX_TITLE = 200
MAX_PROMPT = 4000
MAX_BODY = 20000
MAX_PRESETS = 50

_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
_PROJECT = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")
AUTHORED_PREFIX = "authored:"

# What a catalog entry's `group` can be, in the order the default report lists them.
GROUPS = ("overview", "docs", "study", "design", "glossary", "system")
GROUP_TITLES = {
    "overview": "Overview",
    "docs": "Project docs",
    "study": "Code study",
    "design": "Design",
    "glossary": "Glossary",
    "system": "In the system",
}


class ReportError(ValueError):
    pass


class PresetNotFound(KeyError):
    pass


# --- the catalog ------------------------------------------------------------------------


def _entry(
    id_: str,
    group: str,
    title: str,
    kind: str,
    available: bool = True,
    reason: str | None = None,
    parent: str | None = None,
) -> dict:
    return {
        "id": id_,
        "group": group,
        "title": title,
        "kind": kind,  # "text" | "diagram"
        "available": available,
        "reason": None if available else reason,
        "parent": parent,
    }


def _children_of(components: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for c in components:
        if c.get("parent"):
            out.setdefault(c["parent"], []).append(c)
    return out


def _study_entries(model: dict, notes: str | None) -> list[dict]:
    components = [c for c in model.get("components", []) or [] if isinstance(c, dict) and c.get("id")]
    entries = [
        _entry(
            "study.map", "study", "Component map (top level)", "diagram", bool(components), "no components"
        )
    ]
    kids = _children_of(components)
    for c in components:
        if c["id"] in kids:
            entries.append(
                _entry(
                    f"study.sub:{c['id']}",
                    "study",
                    f"Sub-system: {c.get('name') or c['id']}",
                    "diagram",
                    parent="study.map",
                )
            )
    for f in model.get("flows", []) or []:
        entries.append(
            _entry(f"study.flow:{f['id']}", "study", f"Flow: {f.get('title', f['id'])}", "diagram")
        )
    for a in model.get("activities", []) or []:
        entries.append(
            _entry(f"study.activity:{a['id']}", "study", f"Logic: {a.get('title', a['id'])}", "diagram")
        )
    for s in model.get("states", []) or []:
        entries.append(
            _entry(f"study.state:{s['id']}", "study", f"States: {s.get('title', s['id'])}", "diagram")
        )
    entries.append(
        _entry("study.schema", "study", "Data schema", "diagram", bool(model.get("entities")), "no entities")
    )
    interfaces = model.get("interfaces") or {}
    has_interfaces = bool(interfaces.get("exposes") or interfaces.get("calls"))
    entries.append(_entry("study.interfaces", "study", "Interfaces", "text", has_interfaces, "none recorded"))
    entries.append(
        _entry("study.findings", "study", "Findings", "text", bool(model.get("findings")), "none recorded")
    )
    entries.append(
        _entry("study.notes", "study", "Study notes", "text", bool((notes or "").strip()), "no notes")
    )
    return entries


def _unavailable_study(reason: str) -> list[dict]:
    ids = [
        ("study.map", "Component map (top level)", "diagram"),
        ("study.schema", "Data schema", "diagram"),
        ("study.interfaces", "Interfaces", "text"),
        ("study.findings", "Findings", "text"),
        ("study.notes", "Study notes", "text"),
    ]
    return [_entry(i, "study", t, k, False, reason) for i, t, k in ids]


_DESIGN_DOCS = (
    ("design.brief", "Brief", "brief.md"),
    ("design.architecture", "Architecture", "architecture.md"),
    ("design.plan", "Plan", "plan.md"),
    ("design.decisions", "Decisions", None),
)


def design_folder(registry_root: Path, project: str) -> tuple[Path | None, str]:
    """The folder a report reads the design from: the newest approved revision of the first
    design that has one, else the first design's working copy. Second value says which."""
    for slug in dz.slugs(registry_root, project):
        ref = dz.get(registry_root, project, slug)
        try:
            _, folder = dz.revision_folder(ref)
            return folder, "approved"
        except dz.DesignNotFound:
            continue
    for slug in dz.slugs(registry_root, project):
        return dz.get(registry_root, project, slug).folder, "draft"
    return None, ""


def _design_entries(registry_root: Path, project: str) -> list[dict]:
    folder, which = design_folder(registry_root, project)
    if folder is None:
        return [_entry(i, "design", t, "text", False, "no design yet") for i, t, _ in _DESIGN_DOCS]
    files = dz.read_files(folder)
    suffix = "" if which == "approved" else " (draft)"
    out = []
    for id_, title, name in _DESIGN_DOCS:
        if name:
            has = bool(files.get(name, "").strip())
        else:
            has = any(k.startswith(f"{dz.DECISIONS_DIR}/") and v.strip() for k, v in files.items())
        out.append(_entry(id_, "design", title + suffix, "text", has, "empty"))
    return out


def _notes(manager: SourceManager, page: str) -> str:
    """The body of a project's registry page, without its title line."""
    try:
        text = (manager.get(REGISTRY_ID).root / page).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    _, body, _ = split_frontmatter(text)
    return re.sub(r"^\s*#[^\n]*\n", "", body, count=1).strip()


def catalog(manager: SourceManager, registry_root: Path, project_id: str) -> list[dict]:
    """Every section a report of this project can hold. A section with no source is listed with
    `available: false` and the reason, never left out."""
    project = manager.registry.projects.get(project_id)
    if project is None:
        raise KeyError(project_id)
    out: list[dict] = [_entry("overview.facts", "overview", "Summary and facts", "text")]

    notes = _notes(manager, project.page)
    out.append(
        _entry("overview.notes", "overview", "Cross-project notes", "text", bool(notes), "no notes written")
    )

    source = manager.sources.get(project_id)
    if source is None or not project.available:
        out.append(
            _entry("docs.none", "docs", "Project docs", "text", False, "the project's folder isn't available")
        )
    else:
        for rel, _ in source.files({".md"}):
            out.append(_entry(f"docs:{rel}", "docs", rel, "text"))

    snaps = st.snapshots(registry_root, project_id)
    if not snaps:
        out += _unavailable_study("no study yet")
    else:
        model, problems = st.load(snaps[0])
        out += (
            _study_entries(model, st.load_notes(snaps[0]))
            if model
            else _unavailable_study("study unreadable")
        )

    out += _design_entries(registry_root, project_id)

    terms = gl.load(registry_root, project_id)
    out.append(_entry("glossary.terms", "glossary", "Glossary", "text", bool(terms), "no terms yet"))

    group = project.group
    out.append(_entry("system.group", "system", "The group's map", "diagram", bool(group), "not in a group"))
    linked = bool(project.depends_on or project.used_by)
    out.append(
        _entry("system.dependencies", "system", "Dependencies", "text", linked, "no dependencies recorded")
    )
    return out


def default_sections(entries: list[dict]) -> list[str]:
    """What a new standard report holds: every available section, in catalog order."""
    return [e["id"] for e in entries if e["available"]]


# --- presets ----------------------------------------------------------------------------

DEFAULT_OPTIONS = {"page_size": "A4", "orientation": "portrait", "cover": True, "toc": True}


def validate_preset(raw: object, entries: list[dict]) -> dict:
    """A cleaned preset. Raises ReportError naming everything that's wrong."""
    if not isinstance(raw, dict):
        raise ReportError("a preset is an object")
    problems: list[str] = []
    name = str(raw.get("name", "")).strip()
    if not _NAME.match(name):
        problems.append("name: lowercase letters, digits and dashes, at most 40")
    mode = raw.get("mode", "standard")
    if mode not in MODES:
        problems.append(f"mode: one of {', '.join(MODES)}")
    title = str(raw.get("title", "")).strip()
    if len(title) > MAX_TITLE:
        problems.append(f"title: at most {MAX_TITLE} characters")

    prompt = str(raw.get("prompt", "") or "").strip()
    outline = str(raw.get("outline", "") or "").strip()
    if mode == "standard" and (prompt or outline):
        problems.append("a standard report has no prompt or outline (that is a guided report)")
    if len(prompt) > MAX_PROMPT or len(outline) > MAX_PROMPT:
        problems.append(f"prompt and outline: at most {MAX_PROMPT} characters each")

    opts_raw = raw.get("options") or {}
    if not isinstance(opts_raw, dict):
        problems.append("options must be an object")
        opts_raw = {}
    options = {**DEFAULT_OPTIONS, **{k: v for k, v in opts_raw.items() if k in DEFAULT_OPTIONS}}
    if options["page_size"] not in PAGE_SIZES:
        problems.append(f"options.page_size: one of {', '.join(PAGE_SIZES)}")
    if options["orientation"] not in ORIENTATIONS:
        problems.append(f"options.orientation: one of {', '.join(ORIENTATIONS)}")
    for flag in ("cover", "toc"):
        if not isinstance(options[flag], bool):
            problems.append(f"options.{flag}: true or false")
    extra = set(opts_raw) - set(DEFAULT_OPTIONS)
    if extra:
        problems.append(f"options: unknown {', '.join(sorted(extra))}")

    by_id = {e["id"]: e for e in entries}
    sections_raw = raw.get("sections")
    sections: list[dict] = []
    if not isinstance(sections_raw, list) or not sections_raw:
        problems.append("sections: a list with at least one section")
        sections_raw = []
    if len(sections_raw) > MAX_SECTIONS:
        problems.append(f"sections: at most {MAX_SECTIONS}")
    seen: set[str] = set()
    for i, s in enumerate(sections_raw[:MAX_SECTIONS]):
        where = f"sections[{i}]"
        if not isinstance(s, dict) or not isinstance(s.get("id"), str):
            problems.append(f"{where}: needs an id")
            continue
        sid = s["id"]
        if sid in seen:
            problems.append(f"{where}: '{sid}' appears twice")
            continue
        seen.add(sid)
        if sid.startswith(AUTHORED_PREFIX):
            sections.append(_authored(s, where, mode, by_id, problems))
        elif sid not in by_id:
            problems.append(f"{where}: no section '{sid}' in this project's catalog")
        elif not by_id[sid]["available"]:
            problems.append(f"{where}: '{sid}' is unavailable ({by_id[sid]['reason']})")
        else:
            sections.append({"id": sid})
    if problems:
        raise ReportError("; ".join(problems))
    cleaned = {"name": name, "mode": mode, "title": title, "options": options, "sections": sections}
    if mode == "guided":
        cleaned["prompt"] = prompt
        cleaned["outline"] = outline
    return cleaned


def _authored(s: dict, where: str, mode: str, by_id: dict[str, dict], problems: list[str]) -> dict:
    sid = s["id"]
    if mode != "guided":
        problems.append(f"{where}: only a guided report has authored sections")
    if not _NAME.match(sid[len(AUTHORED_PREFIX) :]):
        problems.append(f"{where}: '{sid}' needs a slug after 'authored:'")
    title = str(s.get("title", "")).strip()
    body = str(s.get("body", "")).strip()
    if not title or len(title) > MAX_TITLE:
        problems.append(f"{where}: needs a title of at most {MAX_TITLE} characters")
    if not body or len(body) > MAX_BODY:
        problems.append(f"{where}: needs a body of at most {MAX_BODY} characters")
    cites = s.get("cites")
    if not isinstance(cites, list) or not cites or not all(isinstance(c, str) for c in cites):
        problems.append(f"{where}: an authored section cites at least one catalog section")
        cites = []
    for c in cites:
        if c not in by_id:
            problems.append(f"{where}: cites '{c}', which isn't in the catalog")
        elif not by_id[c]["available"]:
            problems.append(f"{where}: cites '{c}', which is unavailable")
    return {"id": sid, "title": title, "body": body, "cites": list(dict.fromkeys(cites))}


def _folder(registry_root: Path, project: str) -> Path:
    if not _PROJECT.match(project):
        raise ReportError(f"bad project name '{project}'")
    return registry_root / REPORTS_DIR / project


def _read(registry_root: Path, project: str) -> dict[str, dict]:
    path = _folder(registry_root, project) / PRESETS_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        presets = data["presets"]
    except (OSError, ValueError, KeyError, TypeError):
        return {}
    return presets if isinstance(presets, dict) else {}


def _write(registry_root: Path, project: str, presets: dict[str, dict]) -> None:
    folder = _folder(registry_root, project)
    folder.mkdir(parents=True, exist_ok=True)
    text = json.dumps({"presets": dict(sorted(presets.items()))}, ensure_ascii=False, indent=2)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".presets-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text + "\n")
        os.replace(tmp, folder / PRESETS_FILE)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def list_presets(registry_root: Path, project: str) -> list[dict]:
    return list(_read(registry_root, project).values())


def get_preset(registry_root: Path, project: str, name: str) -> dict:
    found = _read(registry_root, project).get(name)
    if found is None:
        raise PresetNotFound(name)
    return found


def save_preset(registry_root: Path, project: str, raw: object, entries: list[dict]) -> dict:
    """Validate against the catalog and store, replacing a preset of the same name."""
    preset = validate_preset(raw, entries)
    presets = _read(registry_root, project)
    if preset["name"] not in presets and len(presets) >= MAX_PRESETS:
        raise ReportError(f"a project holds at most {MAX_PRESETS} presets")
    presets[preset["name"]] = preset
    _write(registry_root, project, presets)
    return preset


def delete_preset(registry_root: Path, project: str, name: str) -> None:
    presets = _read(registry_root, project)
    if name not in presets:
        raise PresetNotFound(name)
    del presets[name]
    _write(registry_root, project, presets)


# --- the renderer -----------------------------------------------------------------------

_BROWSER_NAMES = ("msedge", "msedge.exe", "microsoft-edge")
_BROWSER_PATHS = (
    r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
    r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
)


def find_browser(override: str = "") -> Path | None:
    """Headless Edge (ADR 0025), from `ARCHEION_REPORT_BROWSER` if set, else the usual places."""
    if override.strip():
        p = Path(override.strip())
        return p if p.is_file() else None
    for name in _BROWSER_NAMES:
        found = shutil.which(name)
        if found:
            return Path(found)
    for raw in _BROWSER_PATHS:
        p = Path(os.path.expandvars(raw))
        if p.is_file():
            return p
    return None


def preflight(
    manager: SourceManager, registry_root: Path, project_id: str, browser_override: str = ""
) -> dict:
    """What a report of this project can use right now, and what can't be built."""
    entries = catalog(manager, registry_root, project_id)
    snaps = st.snapshots(registry_root, project_id)
    browser = find_browser(browser_override)
    available = [e for e in entries if e["available"]]
    problems = []
    if browser is None:
        problems.append(
            "headless Edge wasn't found; set ARCHEION_REPORT_BROWSER or use the browser's Save as PDF"
        )
    if not available:
        problems.append("no section has a source")
    return {
        "project": project_id,
        "browser": browser is not None,
        "study": snaps[0].id if snaps else None,
        "sections": len(entries),
        "available": len(available),
        "unavailable": [{"id": e["id"], "reason": e["reason"]} for e in entries if not e["available"]],
        "problems": problems,
        "ok": not problems,
    }


# --- content ----------------------------------------------------------------------------


def _design_markdown(registry_root: Path, project: str, section: str) -> str:
    folder, _ = design_folder(registry_root, project)
    if folder is None:
        return ""
    files = dz.read_files(folder)
    if section == "design.decisions":
        prefix = f"{dz.DECISIONS_DIR}/"
        parts = [v.strip() for k, v in sorted(files.items()) if k.startswith(prefix) and v.strip()]
        return "\n\n---\n\n".join(parts)
    names = {"design.brief": "brief.md", "design.architecture": "architecture.md", "design.plan": "plan.md"}
    return files.get(names[section], "").strip()


def _sourced(manager: SourceManager, registry_root: Path, project, sid: str, notes: str, model: dict) -> dict:
    """One catalog section resolved to the data the print route draws it from."""
    if sid == "overview.facts":
        return {"type": "facts"}
    if sid == "overview.notes":
        return {"type": "markdown", "markdown": _notes(manager, project.page)}
    if sid.startswith("docs:"):
        rel = sid[len("docs:") :]
        path = manager.get(project.id).resolve(rel, allowed={".md"})
        return {
            "type": "markdown",
            "markdown": path.read_text(encoding="utf-8", errors="replace"),
            "path": rel,
        }
    if sid == "study.map" or sid.startswith("study.sub:"):
        return {"type": "diagram", "diagram": "map", "focus": sid.partition(":")[2] or None}
    for prefix, kind in (("study.flow:", "flow"), ("study.activity:", "activity"), ("study.state:", "state")):
        if sid.startswith(prefix):
            return {"type": "diagram", "diagram": kind, "ref": sid[len(prefix) :]}
    if sid == "study.schema":
        return {"type": "diagram", "diagram": "schema"}
    if sid == "study.interfaces":
        interfaces = model.get("interfaces") or {}
        return {
            "type": "interfaces",
            "exposes": interfaces.get("exposes", []),
            "calls": interfaces.get("calls", []),
        }
    if sid == "study.findings":
        return {"type": "findings", "items": model.get("findings", [])}
    if sid == "study.notes":
        return {"type": "markdown", "markdown": notes}
    if sid.startswith("design."):
        return {"type": "markdown", "markdown": _design_markdown(registry_root, project.id, sid)}
    if sid == "glossary.terms":
        return {"type": "glossary", "terms": gl.load(registry_root, project.id)}
    if sid == "system.group":
        return {"type": "diagram", "diagram": "group", "group": project.group}
    if sid == "system.dependencies":
        return {"type": "dependencies", "depends_on": project.depends_on, "used_by": project.used_by}
    raise ReportError(f"no way to build the section '{sid}'")


def content(manager: SourceManager, registry_root: Path, project_id: str, preset: dict) -> dict:
    """Everything the print route needs to draw a preset: the project, the study model its
    diagrams come from, and each section resolved to its data, in the preset's order. The preset
    is checked against the catalog again, so a source that went away since it was saved is refused."""
    entries = catalog(manager, registry_root, project_id)
    preset = validate_preset(preset, entries)
    project = manager.registry.projects[project_id]
    by_id = {e["id"]: e for e in entries}
    snaps = st.snapshots(registry_root, project_id)
    study = None
    model: dict = {}
    notes = ""
    if snaps and any(s["id"].startswith("study.") for s in preset["sections"]):
        model, _ = st.load(snaps[0])
        notes = st.load_notes(snaps[0])
        meta = model.get("meta", {})
        study = {"id": snaps[0].id, "date": meta.get("date"), "commit": meta.get("commit"), "model": model}
    sections = []
    for s in preset["sections"]:
        sid = s["id"]
        if sid.startswith(AUTHORED_PREFIX):
            cites = [{"id": c, "title": by_id[c]["title"]} for c in s["cites"]]
            sections.append(
                {"id": sid, "title": s["title"], "type": "authored", "markdown": s["body"], "cites": cites}
            )
            continue
        body = _sourced(manager, registry_root, project, sid, notes, model)
        sections.append({"id": sid, "title": by_id[sid]["title"], **body})
    return {
        "project": project.public(),
        "preset": preset,
        "generated": date.today().isoformat(),
        "study": study,
        "sections": sections,
    }
