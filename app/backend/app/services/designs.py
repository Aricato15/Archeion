"""Designs (ADR 0022): what a registered project should become, worked out in Archeion and kept
in the private registry at registry/designs/<project>/<slug>/.

A design is a living working copy (prose in markdown plus `model.json`, the intended system in
the study schema), with a stage the user moves it through. Approving freezes an immutable
revision under `revisions/`. Handing off delivers a package of a revision to the project, which
its own skill consumes. This module is the only writer of the designs folder: `save` validates,
refuses secrets and absolute paths, and replaces the working copy atomically.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from datetime import date as Date
from pathlib import Path
from typing import Annotated

from pydantic import Field, ValidationError, field_validator

from . import studies as st

DESIGNS_DIR = "designs"
MODEL_FILE = "model.json"
INFO_FILE = "info.json"
INDEX_FILE = "design.md"
PROSE_FILES = ("brief.md", "architecture.md", "plan.md", "questions.md")
DECISIONS_DIR = "decisions"
REVISIONS_DIR = "revisions"
DEFAULT_SLUG = "main"
# The folder in a project that a handoff delivers to, and where a project's skill looks.
PACKAGE_DIR = ".archeion/designs"
HANDOFF_FILE = "handoff.json"

# Stages the user moves a design through. `approved` and `handed off` are set by approve and
# by the project's skill, never moved to directly.
STAGES = ("brief", "architecture", "plan", "approved", "handed off")
MOVABLE = ("brief", "architecture", "plan")

MAX_PROSE_BYTES = 200_000
MAX_DECISION_FILES = 100

# The workspace's server port ranges (the root CLAUDE.md). A designed port must fall in one.
PORT_RANGES = (
    (20060, 20099, "API Gateway"),
    (20100, 20149, "Core APIs"),
    (20230, 20299, "Business APIs"),
    (20300, 20399, "AI / Agent APIs"),
    (20400, 20479, "Background services"),
    (20500, 20599, "Infrastructure utilities"),
    (20700, 20799, "Future expansion"),
)

_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
_REVISION = re.compile(r"^\d{4}-\d{2}-\d{2}-r\d+$")
_DECISION = re.compile(r"^\d{4}-[a-z0-9][a-z0-9-]{0,80}\.md$")
_ABS_PATH = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/][^\s]|/(?:Users|home)/[A-Za-z0-9._-]+/")
Id = Annotated[str, Field(pattern=st._ID)]


class DesignError(ValueError):
    """A design that doesn't validate, or an action its stage doesn't allow."""


class DesignNotFound(LookupError):
    pass


# --- the model --------------------------------------------------------------------------


class DesignMeta(st._Strict):
    project: Id
    date: Date
    summary: str = Field("", max_length=4000)
    stack: list[str] = []


class Structure(st._Strict):
    """The structural facts that go into the project's registry page on approval."""

    ports: list[int] = []
    depends_on: list[Id] = []
    group: Id | None = None
    kind: str | None = Field(None, max_length=100)
    status: str | None = Field(None, pattern=r"^(active|planned|paused|archived)$")

    @field_validator("ports")
    @classmethod
    def _ports(cls, v: list[int]) -> list[int]:
        for port in v:
            if not any(lo <= port <= hi for lo, hi, _ in PORT_RANGES):
                raise ValueError(f"port {port} isn't in one of the workspace's port ranges")
        if len(set(v)) != len(v):
            raise ValueError("a port is listed twice")
        return v


class Design(st.Study):
    """The intended system: a study's sections, without a commit, plus the structural facts."""

    meta: DesignMeta  # type: ignore[assignment]
    structure: Structure = Structure()


def _problems_for(
    design: Design, *, project: str, registry=None, ports_taken: dict[int, list[str]] | None = None
):
    problems = st.reference_problems(design)
    if design.meta.project != project:
        problems.append(f"meta.project is '{design.meta.project}', not '{project}'")
    s = design.structure
    if project in s.depends_on:
        problems.append("structure.depends_on can't name the project itself")
    if registry is not None:
        for dep in s.depends_on:
            if dep not in registry.projects:
                problems.append(f"structure.depends_on: '{dep}' isn't a registered project")
        if s.group and s.group not in registry.groups:
            problems.append(f"structure.group: '{s.group}' isn't a group page in the registry")
    for port in s.ports:
        others = [p for p in (ports_taken or {}).get(port, []) if p != project]
        if others:
            problems.append(f"structure.ports: {port} is already recorded for {', '.join(sorted(others))}")
    return problems


def parse(
    data: object, *, project: str, registry=None, ports_taken: dict[int, list[str]] | None = None
) -> Design:
    try:
        design = Design.model_validate(data)
    except ValidationError as exc:
        raise DesignError("; ".join(st._format_errors(exc)[:50])) from exc
    problems = _problems_for(design, project=project, registry=registry, ports_taken=ports_taken)
    if problems:
        raise DesignError("; ".join(problems[:50]))
    return design


def dump(design: Design) -> dict:
    return design.model_dump(mode="json", by_alias=True, exclude_none=True)


def empty_model(project: str, summary: str = "") -> dict:
    return {"schema": 1, "meta": {"project": project, "date": Date.today().isoformat(), "summary": summary}}


# --- prose checks -----------------------------------------------------------------------


def prose_problems(name: str, text: str) -> list[str]:
    out: list[str] = []
    if len(text.encode("utf-8")) > MAX_PROSE_BYTES:
        out.append(f"{name} is larger than {MAX_PROSE_BYTES // 1000} KB")
    if _ABS_PATH.search(text):
        out.append(f"{name} has an absolute path; write paths relative to the project")
    for pat in st._SECRET_PATTERNS:
        if pat.search(text):
            out.append(f"{name} looks like it holds a secret")
            break
    return out


# --- layout -----------------------------------------------------------------------------


def designs_root(registry_root: Path) -> Path:
    return registry_root / DESIGNS_DIR


def check_slug(slug: str) -> str:
    if not _SLUG.match(slug):
        raise DesignError("a design's slug is lowercase letters, digits and dashes (at most 40)")
    return slug


def design_dir(registry_root: Path, project: str, slug: str) -> Path:
    if not re.match(st._ID, project):
        raise DesignNotFound(project)
    return designs_root(registry_root) / project / check_slug(slug)


def slugs(registry_root: Path, project: str) -> list[str]:
    base = designs_root(registry_root) / project
    if not re.match(st._ID, project) or not base.is_dir():
        return []
    return sorted(
        d.name
        for d in base.iterdir()
        if d.is_dir() and not d.is_symlink() and _SLUG.match(d.name) and (d / INFO_FILE).is_file()
    )


def projects_with_designs(registry_root: Path) -> list[str]:
    root = designs_root(registry_root)
    if not root.is_dir():
        return []
    return sorted(d.name for d in root.iterdir() if d.is_dir() and slugs(registry_root, d.name))


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class DesignRef:
    project: str
    slug: str
    folder: Path

    def info(self) -> dict:
        return _read_json(self.folder / INFO_FILE)

    @property
    def stage(self) -> str:
        return self.info().get("stage", "brief")


def get(registry_root: Path, project: str, slug: str = DEFAULT_SLUG) -> DesignRef:
    folder = design_dir(registry_root, project, slug)
    if not (folder / INFO_FILE).is_file() or folder.is_symlink():
        raise DesignNotFound(f"{project}/{slug}")
    return DesignRef(project, slug, folder)


def _decision_names(folder: Path) -> list[str]:
    d = folder / DECISIONS_DIR
    if not d.is_dir():
        return []
    return sorted(f.name for f in d.iterdir() if f.is_file() and _DECISION.match(f.name))


def read_files(folder: Path) -> dict[str, str]:
    """Every prose file of a design (or revision) by relative name: the four documents and
    the decisions."""
    out: dict[str, str] = {}
    for name in PROSE_FILES:
        f = folder / name
        out[name] = f.read_text(encoding="utf-8", errors="replace") if f.is_file() else ""
    for name in _decision_names(folder):
        out[f"{DECISIONS_DIR}/{name}"] = (folder / DECISIONS_DIR / name).read_text(
            encoding="utf-8", errors="replace"
        )
    return out


def load(folder: Path, project: str) -> tuple[dict, list[str]]:
    """The model as JSON and its problems. A model that no longer validates is returned raw."""
    path = folder / MODEL_FILE
    if not path.is_file():
        return {}, ["model.json is missing"]
    if path.stat().st_size > st.MAX_MODEL_BYTES:
        return {}, ["model.json is too large"]
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        return {}, [f"model.json isn't valid JSON: {exc}"]
    try:
        return dump(parse(raw, project=project)), []
    except DesignError as exc:
        return raw if isinstance(raw, dict) else {}, [str(exc)]


def revisions(ref: DesignRef) -> list[dict]:
    """Frozen revisions, newest first."""
    base = ref.folder / REVISIONS_DIR
    if not base.is_dir():
        return []
    out = []
    for d in base.iterdir():
        if d.is_dir() and not d.is_symlink() and _REVISION.match(d.name):
            info = _read_json(d / INFO_FILE)
            out.append(
                {
                    "id": d.name,
                    "number": int(d.name.rsplit("-r", 1)[1]),
                    "date": d.name[:10],
                    "handoff": info.get("handoff"),
                }
            )
    return sorted(out, key=lambda r: r["number"], reverse=True)


def revision_folder(ref: DesignRef, which: str | int | None = None) -> tuple[dict, Path]:
    """A revision by number or id; None or 'latest' is the newest."""
    found = revisions(ref)
    if not found:
        raise DesignNotFound(f"{ref.project}/{ref.slug} has no approved revision yet")
    if which in (None, "latest"):
        rev = found[0]
    else:
        wanted = str(which).lstrip("r")
        rev = next((r for r in found if str(r["number"]) == wanted or r["id"] == str(which)), None)
        if rev is None:
            raise DesignNotFound(f"{ref.project}/{ref.slug} has no revision '{which}'")
    return rev, ref.folder / REVISIONS_DIR / rev["id"]


def summary(ref: DesignRef) -> dict:
    info = ref.info()
    model, problems = load(ref.folder, ref.project)
    files = read_files(ref.folder)
    meta = model.get("meta", {}) if isinstance(model, dict) else {}
    revs = revisions(ref)
    return {
        "project": ref.project,
        "slug": ref.slug,
        "stage": info.get("stage", "brief"),
        "updated": info.get("updated"),
        "thread": info.get("thread"),
        "revision": revs[0]["number"] if revs else None,
        "revisions": revs,
        "changed_since_revision": bool(info.get("changed_since_revision")),
        "summary": meta.get("summary", ""),
        "valid": not problems,
        "problems": problems,
        "files": {k: bool(v.strip()) for k, v in files.items()},
        "counts": {
            "components": len(model.get("components", []) or []),
            "exposes": len((model.get("interfaces") or {}).get("exposes", []) or []),
            "calls": len((model.get("interfaces") or {}).get("calls", []) or []),
            "entities": len(model.get("entities", []) or []),
            "flows": len(model.get("flows", []) or []),
        },
        "structure": model.get("structure", {}) if isinstance(model, dict) else {},
    }


# --- writing ----------------------------------------------------------------------------


def _write_tree(target: Path, files: dict[str, str], model: dict, info: dict, keep: list[str]) -> None:
    """Replace `target` with the files, model and info, keeping the listed subfolders of the
    old copy. Written beside it and swapped in, so a reader never sees half a design."""
    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True)
    tmp = parent / f".{target.name}.tmp"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()
    for name, text in files.items():
        if name.startswith(f"{DECISIONS_DIR}/") and not text.strip():
            continue
        dest = tmp / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text.rstrip() + "\n" if text.strip() else "", encoding="utf-8")
    (tmp / MODEL_FILE).write_text(json.dumps(model, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (tmp / INFO_FILE).write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for sub in keep:
        if (target / sub).is_dir():
            shutil.copytree(target / sub, tmp / sub)
    (tmp / INDEX_FILE).write_text(
        render_index(target.parent.name, target.name, info, model), encoding="utf-8"
    )
    old = parent / f".{target.name}.old"
    if old.exists():
        shutil.rmtree(old)
    if target.exists():
        target.rename(old)
    tmp.rename(target)
    if old.exists():
        shutil.rmtree(old)


def render_index(project: str, slug: str, info: dict, model: dict) -> str:
    """design.md: the page the viewer opens first, generated from the state. Never edited."""
    stage = info.get("stage", "brief")
    meta = model.get("meta", {}) if isinstance(model, dict) else {}
    lines = [
        "---",
        f"project: {project}",
        f"slug: {slug}",
        f"stage: {stage}",
        f"revision: {info.get('revision', 0)}",
        f"updated: {info.get('updated', '')}",
        "---",
        f"# Design: {project}" + ("" if slug == DEFAULT_SLUG else f" ({slug})"),
        "",
        f"Stage: **{stage}**." + (f" {meta['summary']}" if meta.get("summary") else ""),
        "",
        "- [Brief](brief.md)",
        "- [Architecture](architecture.md)",
        "- [Plan](plan.md)",
        "- [Open questions](questions.md)",
        "",
        "_Generated by Archeion; edit the design through its skill or the viewer._",
        "",
    ]
    return "\n".join(lines)


def _clean_files(files: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for name, text in files.items():
        if name in PROSE_FILES or (
            name.startswith(f"{DECISIONS_DIR}/") and _DECISION.match(name.split("/", 1)[1])
        ):
            out[name] = text
        else:
            raise DesignError(
                f"'{name}' isn't a design file (brief.md, architecture.md, plan.md, questions.md,"
                f" decisions/NNNN-title.md, model.json)"
            )
    return out


def read_workdir(work: Path) -> tuple[dict[str, str], dict | None]:
    """The files a skill wrote into a work folder: whichever prose files and decisions it has,
    and model.json if present."""
    if not work.is_dir():
        raise DesignError(f"{work} isn't a folder")
    files: dict[str, str] = {}
    for name in PROSE_FILES:
        if (work / name).is_file():
            files[name] = (work / name).read_text(encoding="utf-8")
    d = work / DECISIONS_DIR
    if d.is_dir():
        for f in sorted(d.iterdir()):
            if f.is_file():
                files[f"{DECISIONS_DIR}/{f.name}"] = f.read_text(encoding="utf-8")
    model = None
    if (work / MODEL_FILE).is_file():
        try:
            model = json.loads((work / MODEL_FILE).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise DesignError(f"model.json isn't valid JSON: {exc}") from exc
    return files, model


def init(
    registry_root: Path,
    project: str,
    slug: str = DEFAULT_SLUG,
    *,
    thread: int | None = None,
    summary: str = "",
) -> DesignRef:
    folder = design_dir(registry_root, project, slug)
    if (folder / INFO_FILE).is_file():
        raise DesignError(f"a design '{slug}' already exists for {project}")
    info = {"stage": "brief", "revision": 0, "updated": _now(), "thread": thread}
    files = {
        "brief.md": "# Brief\n\n## Purpose\n\n## Users\n\n## Scope\n\n## Non-goals\n",
        "architecture.md": "# Architecture\n",
        "plan.md": "# Plan\n",
        "questions.md": "# Open questions\n",
    }
    _write_tree(folder, files, empty_model(project, summary), info, keep=[])
    return DesignRef(project, slug, folder)


def save(
    registry_root: Path,
    ref: DesignRef,
    *,
    files: dict[str, str],
    model: dict | None,
    registry=None,
    ports_taken: dict[int, list[str]] | None = None,
    thread: int | None = None,
) -> DesignRef:
    """Replace the working copy with `files` (only the ones given; the rest stay) and `model`
    (when given). Validated first. A design that was approved goes back to `plan`, since it
    now differs from its revision (the revision itself is untouched)."""
    files = _clean_files(files)
    problems: list[str] = []
    for name, text in files.items():
        problems += prose_problems(name, text)
    count = len(set(_decision_names(ref.folder)) | {n.split("/", 1)[1] for n in files if "/" in n})
    if count > MAX_DECISION_FILES:
        problems.append(f"at most {MAX_DECISION_FILES} decision files")
    if model is not None:
        try:
            design = parse(model, project=ref.project, registry=registry, ports_taken=ports_taken)
        except DesignError as exc:
            problems.append(str(exc))
        else:
            model = dump(design)
    if problems:
        raise DesignError("; ".join(problems[:50]))
    current, _ = load(ref.folder, ref.project)
    keep_model = model if model is not None else (current or empty_model(ref.project))
    merged = read_files(ref.folder)
    merged.update(files)
    info = ref.info()
    info["updated"] = _now()
    if thread is not None:
        info["thread"] = thread
    if info.get("stage") in ("approved", "handed off"):
        info["stage"] = "plan"
        info["changed_since_revision"] = True
    _write_tree(ref.folder, merged, keep_model, info, keep=[REVISIONS_DIR])
    return ref


def set_stage(ref: DesignRef, stage: str) -> dict:
    if stage not in MOVABLE:
        raise DesignError(
            f"a design moves between {', '.join(MOVABLE)}; it becomes approved with approve, and handed off"
            " when the project consumes it"
        )
    info = ref.info()
    info["stage"] = stage
    info["updated"] = _now()
    model, _ = load(ref.folder, ref.project)
    (ref.folder / INFO_FILE).write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    (ref.folder / INDEX_FILE).write_text(render_index(ref.project, ref.slug, info, model), encoding="utf-8")
    return info


def approval_problems(ref: DesignRef, registry=None, ports_taken=None) -> list[str]:
    """What stops an approval: a model that doesn't validate, or an empty brief."""
    out: list[str] = []
    files = read_files(ref.folder)
    brief = files.get("brief.md", "")
    if len(re.sub(r"#.*|\s", "", brief)) < 20:
        out.append("the brief is empty; write the purpose before approving")
    try:
        raw = json.loads((ref.folder / MODEL_FILE).read_text(encoding="utf-8"))
        parse(raw, project=ref.project, registry=registry, ports_taken=ports_taken)
    except (DesignError, OSError, json.JSONDecodeError) as exc:
        out.append(f"the model doesn't validate: {exc}")
    return out


def approve(ref: DesignRef, registry=None, ports_taken=None) -> dict:
    """Freeze the working copy as the next revision and mark the design approved."""
    problems = approval_problems(ref, registry, ports_taken)
    if problems:
        raise DesignError("; ".join(problems))
    info = ref.info()
    n = (revisions(ref)[0]["number"] if revisions(ref) else 0) + 1
    rid = f"{Date.today().isoformat()}-r{n}"
    target = ref.folder / REVISIONS_DIR / rid
    target.parent.mkdir(exist_ok=True)
    tmp = target.parent / f".{rid}.tmp"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()
    for name, text in read_files(ref.folder).items():
        dest = tmp / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
    shutil.copy2(ref.folder / MODEL_FILE, tmp / MODEL_FILE)
    (tmp / INFO_FILE).write_text(json.dumps({"approved": _now()}) + "\n", encoding="utf-8")
    tmp.rename(target)
    info.update(stage="approved", revision=n, updated=_now(), changed_since_revision=False)
    model, _ = load(ref.folder, ref.project)
    (ref.folder / INFO_FILE).write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    (ref.folder / INDEX_FILE).write_text(render_index(ref.project, ref.slug, info, model), encoding="utf-8")
    return {"id": rid, "number": n, "model": model}


def delete(ref: DesignRef) -> None:
    shutil.rmtree(ref.folder)


# --- handoff ----------------------------------------------------------------------------


def package_files(ref: DesignRef, which: str | int | None = None) -> tuple[dict, dict[str, str]]:
    """What a handoff delivers: the revision's prose, decisions and model, plus handoff.json.
    Only this project's own design (ADR 0022 point 8): nothing from the registry beyond it."""
    rev, folder = revision_folder(ref, which)
    files = read_files(folder)
    files[MODEL_FILE] = (folder / MODEL_FILE).read_text(encoding="utf-8")
    handoff = {
        "project": ref.project,
        "slug": ref.slug,
        "revision": rev["number"],
        "date": Date.today().isoformat(),
        "thread": ref.info().get("thread"),
    }
    files[HANDOFF_FILE] = json.dumps(handoff, indent=2) + "\n"
    return rev, files


def record_handoff(ref: DesignRef, revision: int, thread: int | None) -> None:
    rev, folder = revision_folder(ref, revision)
    info = _read_json(folder / INFO_FILE)
    info["handoff"] = {"thread": thread, "requested": _now(), "consumed": None}
    (folder / INFO_FILE).write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")


def mark_consumed(ref: DesignRef, revision: int) -> None:
    """The project consumed revision N: the revision records it, and the design is handed off
    (unless it has moved on since, in which case it stays where the user put it)."""
    rev, folder = revision_folder(ref, revision)
    info = _read_json(folder / INFO_FILE)
    handoff = info.get("handoff") or {}
    handoff["consumed"] = _now()
    info["handoff"] = handoff
    (folder / INFO_FILE).write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    design_info = ref.info()
    if design_info.get("stage") == "approved" and design_info.get("revision") == revision:
        design_info["stage"] = "handed off"
        design_info["updated"] = _now()
        model, _ = load(ref.folder, ref.project)
        (ref.folder / INFO_FILE).write_text(json.dumps(design_info, indent=2) + "\n", encoding="utf-8")
        (ref.folder / INDEX_FILE).write_text(
            render_index(ref.project, ref.slug, design_info, model), encoding="utf-8"
        )


# --- checks a skill runs first (ADR 0022 point 11) ---------------------------------------

_NOT_CODE = {
    ".git",
    ".gitignore",
    ".gitattributes",
    "claude.md",
    "readme.md",
    ".claude",
    ".archeion",
    "license",
}


def has_code(folder: Path | None) -> bool:
    """Whether the project's folder holds more than a CLAUDE.md, README and repo housekeeping."""
    if folder is None or not folder.is_dir():
        return False
    return any(e.name.lower() not in _NOT_CODE for e in folder.iterdir())


def preflight(
    registry,
    *,
    project: str,
    unregistered: list[str],
    purpose: str,
    slug: str,
    registry_root: Path,
    has_study: bool,
) -> list[dict]:
    """Problems that stop (or should be known before) a design step, each with how to fix it.
    `purpose` is `design` or `handoff`. Severity: block (stop), warn (ask first), info."""
    out: list[dict] = []

    def add(severity: str, code: str, message: str, fix: str | None = None) -> None:
        out.append({"severity": severity, "code": code, "message": message, "fix": fix})

    p = registry.projects.get(project)
    if p is None:
        if project in unregistered:
            add(
                "block",
                "not-registered",
                f"'{project}' is in a granted root but isn't registered.",
                f"projects scan --write --only {project}",
            )
        else:
            add(
                "block",
                "unknown-project",
                f"'{project}' isn't registered and isn't in a granted root.",
                "Add its folder as a root on the viewer's Settings page (ARCHEION_ROOTS), then register it.",
            )
        return out
    if p.dir is None:
        add(
            "block",
            "no-folder",
            f"{project}'s folder isn't reachable on this machine.",
            "Grant its root on the viewer's Settings page (ARCHEION_ROOTS), or check its page's path.",
        )
    elif not (p.dir / "CLAUDE.md").is_file():
        add("info", "no-claude-md", "The project has no CLAUDE.md; the design will ask for its tech stack.")
    if p.dir is not None and has_code(p.dir) and not has_study:
        add(
            "warn",
            "no-study",
            f"{project} already has code and no study; design from what's built.",
            f"/study {project}",
        )
    if purpose == "handoff":
        try:
            ref = get(registry_root, project, slug)
        except DesignNotFound:
            add(
                "block",
                "no-design",
                f"{project} has no design '{slug}'.",
                f"design init {project} --slug {slug}",
            )
            return out
        if not revisions(ref):
            add("block", "not-approved", "The design has no approved revision yet; approve it first.")
        elif ref.stage not in ("approved", "handed off"):
            add(
                "warn",
                "changed-since-approval",
                "The working copy changed after the latest revision; the handoff delivers the revision.",
            )
        if not p.inbox_edits:
            add(
                "block",
                "inbox-edits-off",
                f"Archeion's /inbox may not edit {project}, so it can't deliver the package.",
                f"projects inbox-edits {project} on",
            )
    return out
