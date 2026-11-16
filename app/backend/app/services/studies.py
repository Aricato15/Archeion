"""Code studies (ADR 0019): dated, immutable snapshots of what Claude learned about a project's
code, kept in the private registry at registry/studies/<project>/<YYYY-MM-DD>-<commit7>/.

Each snapshot holds `study.json` (the structured model below, validated here) and an optional
`notes.md`. The viewer generates its diagrams from the model. This module is the only writer
of that folder: `save` validates, refuses snippets that look like secrets, allocates the
snapshot folder and prunes the oldest beyond the configured number.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import date as Date
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

SCHEMA_VERSION = 1
STUDIES_DIR = "studies"
MODEL_FILE = "study.json"
NOTES_FILE = "notes.md"
INFO_FILE = "info.json"  # the thread a snapshot or draft belongs to (ADR 0020)
DRAFT = "draft"
MAX_MODEL_BYTES = 4 * 1024 * 1024
MAX_SNIPPET_LINES = 30
MAX_SNIPPET_CHARS = 3000

_ID = r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,119}$"
_SNAPSHOT = re.compile(r"^\d{4}-\d{2}-\d{2}-[0-9a-f]{7}(-\d+)?$")
_DRIVE = re.compile(r"^[A-Za-z]:")
_COMMIT = re.compile(r"^[0-9a-f]{7,40}$")

# What a snippet must not contain. A cited line is shown in the viewer, so a credential in it
# would be too. Built from parts so this file doesn't match the commit hook's own patterns.
_KEY_HEADER = "-----BEGIN " + "[A-Z ]*PRIVATE KEY-----"
_SECRET_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}"),
    re.compile(r"\bsk-[A-Za-z0-9]{32,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(_KEY_HEADER),
    re.compile(
        r"(?i)\b(api[_-]?key|secret|token|passw(or)?d)[\"']?\s*[:=]\s*[\"'][A-Za-z0-9/+_.=-]{8,}[\"']"
    ),
]

Id = Annotated[str, Field(pattern=_ID)]


class StudyError(ValueError):
    """A study model that doesn't validate, or a snapshot that can't be saved."""


class StudyNotFound(LookupError):
    pass


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Cite(_Strict):
    path: str = Field(min_length=1, max_length=512)
    line: int | None = Field(None, ge=1)
    end: int | None = Field(None, ge=1)
    snippet: str | None = Field(None, max_length=MAX_SNIPPET_CHARS)

    @field_validator("path")
    @classmethod
    def _rel(cls, v: str) -> str:
        if "\\" in v or v.startswith("/") or _DRIVE.match(v) or "\0" in v:
            raise ValueError("a cited path is relative to the project, with forward slashes")
        if any(part in ("", ".", "..") for part in v.split("/")):
            raise ValueError("a cited path can't have empty, '.' or '..' segments")
        name = v.rsplit("/", 1)[-1]
        if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
            raise ValueError("a study never cites .env files")
        return v

    @field_validator("snippet")
    @classmethod
    def _snippet(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if len(v.splitlines()) > MAX_SNIPPET_LINES:
            raise ValueError(f"a snippet has at most {MAX_SNIPPET_LINES} lines")
        for pat in _SECRET_PATTERNS:
            if pat.search(v):
                raise ValueError("this snippet looks like it holds a secret; cite the line without it")
        return v

    @model_validator(mode="after")
    def _range(self) -> Cite:
        if self.end is not None and (self.line is None or self.end < self.line):
            raise ValueError("end needs a line and can't come before it")
        return self


class _Element(_Strict):
    id: Id
    cites: list[Cite] = []


class Coverage(_Strict):
    files_total: int | None = Field(None, ge=0)
    files_read: int | None = Field(None, ge=0)
    note: str | None = Field(None, max_length=2000)


class Meta(_Strict):
    project: Id
    date: Date
    commit: str
    dirty: bool = False
    summary: str = Field("", max_length=4000)
    stack: list[str] = []
    coverage: Coverage = Coverage()
    refreshed_from: str | None = None

    @field_validator("commit")
    @classmethod
    def _commit(cls, v: str) -> str:
        if not _COMMIT.match(v):
            raise ValueError("commit is a git hash (7 to 40 hex characters)")
        return v


ComponentKind = Literal[
    "service", "package", "module", "class", "function", "library", "database", "external",
    "ui", "cli", "job", "store",
]  # fmt: skip


class Component(_Element):
    name: str = Field(min_length=1, max_length=200)
    kind: ComponentKind
    parent: Id | None = None
    summary: str = Field("", max_length=4000)
    paths: list[str] = []
    tech: str | None = Field(None, max_length=200)


class Relation(_Element):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    from_: Id = Field(alias="from")
    to: Id
    kind: Literal["imports", "calls", "http", "sql", "event", "reads", "writes"]
    label: str | None = Field(None, max_length=300)


class Exposed(_Element):
    kind: Literal["http", "cli", "event", "file", "library"]
    method: str | None = Field(None, max_length=20)
    path: str | None = Field(None, max_length=500)
    name: str | None = Field(None, max_length=200)
    handler: Id | None = None
    summary: str = Field("", max_length=2000)


class Outgoing(_Element):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    kind: Literal["http", "event", "file", "library"]
    target_project: Id | None = None
    target_url: str | None = Field(None, max_length=500)
    port: int | None = Field(None, ge=1, le=65535)
    method: str | None = Field(None, max_length=20)
    path: str | None = Field(None, max_length=500)
    from_: Id | None = Field(None, alias="from")
    summary: str = Field("", max_length=2000)


class Interfaces(_Strict):
    exposes: list[Exposed] = []
    calls: list[Outgoing] = []


class Field_(_Strict):
    name: str = Field(min_length=1, max_length=200)
    type: str = Field("", max_length=100)
    pk: bool = False
    fk: str | None = Field(None, max_length=300)  # "<entity id>.<field>"
    nullable: bool = False


class Entity(_Element):
    name: str = Field(min_length=1, max_length=200)
    store: Id | None = None
    summary: str = Field("", max_length=2000)
    fields: list[Field_] = []


class Message(_Strict):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    from_: Id = Field(alias="from")
    to: Id
    label: str = Field("", max_length=300)
    reply: bool = False
    is_async: bool = Field(False, alias="async")


class Note(_Strict):
    note: str = Field(min_length=1, max_length=500)
    over: list[Id] = Field(min_length=1, max_length=2)


class Branch(_Strict):
    label: str = Field("", max_length=200)
    steps: list[Step] = []


class Block(_Strict):
    block: Literal["alt", "opt", "loop", "par"]
    label: str = Field("", max_length=200)
    steps: list[Step] = []
    # alt: the "else" branches; par: the "and" branches.
    others: list[Branch] = []


Step = Message | Note | Block


class Flow(_Element):
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field("", max_length=2000)
    trigger: str | None = Field(None, max_length=300)
    participants: list[Id] = Field(min_length=1)
    steps: list[Step] = Field(min_length=1)


class ActivityNode(_Strict):
    id: Id
    label: str = Field("", max_length=300)
    kind: Literal["start", "end", "action", "decision"] = "action"


class Edge(_Strict):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    from_: Id = Field(alias="from")
    to: Id
    label: str | None = Field(None, max_length=200)


class Activity(_Element):
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field("", max_length=2000)
    nodes: list[ActivityNode] = Field(min_length=1)
    edges: list[Edge] = []


class StateNode(_Strict):
    id: Id
    label: str | None = Field(None, max_length=200)


class StateMachine(_Element):
    title: str = Field(min_length=1, max_length=200)
    entity: Id | None = None
    summary: str = Field("", max_length=2000)
    states: list[StateNode] = Field(min_length=1)
    initial: Id | None = None
    final: list[Id] = []
    transitions: list[Edge] = []


class Finding(_Element):
    severity: Literal["info", "warn", "risk"]
    title: str = Field(min_length=1, max_length=300)
    detail: str = Field("", max_length=4000)
    rule: str | None = Field(None, max_length=200)


class Study(_Strict):
    schema_: Literal[1] = Field(alias="schema")
    meta: Meta
    components: list[Component] = []
    relations: list[Relation] = []
    interfaces: Interfaces = Interfaces()
    entities: list[Entity] = []
    flows: list[Flow] = []
    activities: list[Activity] = []
    states: list[StateMachine] = []
    findings: list[Finding] = []
    questions: list[str] = []

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


Branch.model_rebuild()
Block.model_rebuild()
Flow.model_rebuild()


# --- validation -------------------------------------------------------------------------


def _walk_steps(steps: list) -> list:
    out: list = []
    for s in steps:
        out.append(s)
        if isinstance(s, Block):
            out.extend(_walk_steps(s.steps))
            for b in s.others:
                out.extend(_walk_steps(b.steps))
    return out


def reference_problems(study: Study) -> list[str]:
    """Every reference must name an element that exists, and ids must be unique per section."""
    problems: list[str] = []
    comps = {c.id: c for c in study.components}
    entities = {e.id: e for e in study.entities}

    def unique(section: str, ids: list[str]) -> None:
        seen: set[str] = set()
        for i in ids:
            if i in seen:
                problems.append(f"{section}: duplicate id '{i}'")
            seen.add(i)

    unique("components", [c.id for c in study.components])
    unique("relations", [r.id for r in study.relations])
    unique("interfaces", [x.id for x in [*study.interfaces.exposes, *study.interfaces.calls]])
    unique("entities", [e.id for e in study.entities])
    unique("flows", [f.id for f in study.flows])
    unique("activities", [a.id for a in study.activities])
    unique("states", [s.id for s in study.states])
    unique("findings", [f.id for f in study.findings])

    def need(where: str, ref: str | None) -> None:
        if ref is not None and ref not in comps:
            problems.append(f"{where}: '{ref}' isn't a component")

    for c in study.components:
        need(f"component {c.id} parent", c.parent)
        if c.parent == c.id:
            problems.append(f"component {c.id}: can't be its own parent")
    # Parent cycles would make the nested map loop forever.
    for c in study.components:
        seen: set[str] = set()
        cur = c
        while cur.parent and cur.parent in comps:
            if cur.id in seen:
                problems.append(f"component {c.id}: its parents make a cycle")
                break
            seen.add(cur.id)
            cur = comps[cur.parent]
    for r in study.relations:
        need(f"relation {r.id} from", r.from_)
        need(f"relation {r.id} to", r.to)
    for x in study.interfaces.exposes:
        need(f"exposed {x.id} handler", x.handler)
    for x in study.interfaces.calls:
        need(f"call {x.id} from", x.from_)
        if x.kind == "http" and not (x.target_project or x.target_url or x.port):
            problems.append(f"call {x.id}: an http call needs target_project, target_url or port")
    for e in study.entities:
        need(f"entity {e.id} store", e.store)
        for f in e.fields:
            if f.fk:
                target, _, field = f.fk.partition(".")
                if target not in entities or not field:
                    problems.append(f"entity {e.id} field {f.name}: fk '{f.fk}' isn't <entity id>.<field>")
    for fl in study.flows:
        parts = set(fl.participants)
        for p in fl.participants:
            need(f"flow {fl.id} participant", p)
        for s in _walk_steps(fl.steps):
            if isinstance(s, Message):
                for ref in (s.from_, s.to):
                    if ref not in parts:
                        problems.append(f"flow {fl.id}: '{ref}' isn't one of its participants")
            elif isinstance(s, Note):
                for ref in s.over:
                    if ref not in parts:
                        problems.append(f"flow {fl.id}: note over '{ref}', which isn't a participant")
    for a in study.activities:
        ids = {n.id for n in a.nodes}
        for e in a.edges:
            for ref in (e.from_, e.to):
                if ref not in ids:
                    problems.append(f"activity {a.id}: edge names '{ref}', which isn't one of its nodes")
    for m in study.states:
        ids = {s.id for s in m.states}
        if m.entity is not None and m.entity not in entities:
            problems.append(f"states {m.id}: entity '{m.entity}' isn't an entity")
        for ref in [*([m.initial] if m.initial else []), *m.final]:
            if ref not in ids:
                problems.append(f"states {m.id}: '{ref}' isn't one of its states")
        for t in m.transitions:
            for ref in (t.from_, t.to):
                if ref not in ids:
                    problems.append(f"states {m.id}: transition names '{ref}', which isn't one of its states")
    return problems


def _format_errors(exc: ValidationError) -> list[str]:
    out = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"])
        out.append(f"{loc}: {err['msg']}")
    return out


def parse(data: object) -> Study:
    """Validate a model, raising StudyError with every problem found."""
    try:
        study = Study.model_validate(data)
    except ValidationError as exc:
        raise StudyError("; ".join(_format_errors(exc)[:50])) from exc
    problems = reference_problems(study)
    if problems:
        raise StudyError("; ".join(problems[:50]))
    return study


def parse_text(text: str) -> Study:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise StudyError(f"not valid JSON: {exc}") from exc
    return parse(data)


def dump(study: Study) -> dict:
    return study.model_dump(mode="json", by_alias=True, exclude_none=True)


# --- storage ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Snapshot:
    project: str
    id: str
    folder: Path

    @property
    def date(self) -> str:
        return self.id[:10]

    @property
    def is_draft(self) -> bool:
        return self.id == DRAFT

    def info(self) -> dict:
        path = self.folder / INFO_FILE
        try:
            data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        except (OSError, json.JSONDecodeError):
            data = {}
        return data if isinstance(data, dict) else {}


def studies_root(registry_root: Path) -> Path:
    return registry_root / STUDIES_DIR


def _project_dir(registry_root: Path, project: str) -> Path:
    if not re.match(_ID, project):
        raise StudyNotFound(project)
    return studies_root(registry_root) / project


def snapshots(registry_root: Path, project: str) -> list[Snapshot]:
    """A project's snapshots, newest first. Folders that don't look like snapshots are ignored."""
    folder = _project_dir(registry_root, project)
    if not folder.is_dir():
        return []
    found = [
        Snapshot(project, d.name, d)
        for d in folder.iterdir()
        if d.is_dir() and not d.is_symlink() and _SNAPSHOT.match(d.name) and (d / MODEL_FILE).is_file()
    ]
    return sorted(found, key=_sort_key, reverse=True)


def _sort_key(s: Snapshot) -> tuple[str, float, int]:
    """By date, then by when it was written (snapshots are never edited), then by the "-N"
    suffix a second study of the same commit on the same day gets."""
    suffix = s.id[19:]
    return (s.date, (s.folder / MODEL_FILE).stat().st_mtime, int(suffix) if suffix else 1)


def get_snapshot(registry_root: Path, project: str, snapshot_id: str) -> Snapshot:
    if snapshot_id == DRAFT:
        draft = get_draft(registry_root, project)
        if draft is None:
            raise StudyNotFound(f"{project}/{DRAFT}")
        return draft
    snaps = snapshots(registry_root, project)
    if snapshot_id == "latest":
        if not snaps:
            raise StudyNotFound(f"{project}/latest")
        return snaps[0]
    for s in snaps:
        if s.id == snapshot_id:
            return s
    raise StudyNotFound(f"{project}/{snapshot_id}")


def load(snapshot: Snapshot) -> tuple[dict, list[str]]:
    """The snapshot's model as JSON and any problems with it. A model that no longer
    validates (written by an older schema, or edited by hand) is still returned raw."""
    path = snapshot.folder / MODEL_FILE
    if path.stat().st_size > MAX_MODEL_BYTES:
        return {}, ["study.json is too large"]
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        return {}, [f"study.json isn't valid JSON: {exc}"]
    try:
        return dump(parse(raw)), []
    except StudyError as exc:
        return raw if isinstance(raw, dict) else {}, [str(exc)]


def load_notes(snapshot: Snapshot) -> str:
    path = snapshot.folder / NOTES_FILE
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def summary(snapshot: Snapshot) -> dict:
    """What a list shows: the snapshot's id, date, commit, summary and size of each section."""
    model, problems = load(snapshot)
    meta = model.get("meta", {}) if isinstance(model, dict) else {}
    counts = {}
    for key in ("components", "relations", "entities", "flows", "activities", "states", "findings"):
        value = model.get(key) if isinstance(model, dict) else None
        counts[key] = len(value) if isinstance(value, list) else 0
    interfaces = model.get("interfaces", {}) if isinstance(model, dict) else {}
    counts["exposes"] = len(interfaces.get("exposes", []) or [])
    counts["calls"] = len(interfaces.get("calls", []) or [])
    return {
        "id": snapshot.id,
        "project": snapshot.project,
        "date": str(meta.get("date") or snapshot.date),
        "draft": snapshot.is_draft,
        "thread": snapshot.info().get("thread"),
        "commit": meta.get("commit"),
        "dirty": bool(meta.get("dirty")),
        "summary": meta.get("summary", ""),
        "counts": counts,
        "valid": not problems,
        "problems": problems,
        "notes": (snapshot.folder / NOTES_FILE).is_file(),
    }


def save(
    registry_root: Path,
    study: Study,
    *,
    notes: str | None = None,
    keep: int = 10,
    thread: int | None = None,
) -> tuple[Snapshot, list[str]]:
    """Write a new snapshot and prune the oldest beyond `keep`. Returns it and the pruned ids."""
    project = study.meta.project
    base = f"{study.meta.date.isoformat()}-{study.meta.commit[:7]}"
    folder = _project_dir(registry_root, project)
    folder.mkdir(parents=True, exist_ok=True)
    name, n = base, 1
    while (folder / name).exists():
        n += 1
        name = f"{base}-{n}"
    target = folder / name
    tmp = folder / f".{name}.tmp"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()
    (tmp / MODEL_FILE).write_text(
        json.dumps(dump(study), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if notes and notes.strip():
        (tmp / NOTES_FILE).write_text(notes.strip() + "\n", encoding="utf-8")
    if thread is not None:
        (tmp / INFO_FILE).write_text(json.dumps({"thread": thread}) + "\n", encoding="utf-8")
    tmp.rename(target)
    pruned: list[str] = []
    for old in snapshots(registry_root, project)[max(keep, 1) :]:
        shutil.rmtree(old.folder)
        pruned.append(old.id)
    return Snapshot(project, name, target), pruned


def latest_by_project(registry_root: Path) -> dict[str, Snapshot]:
    root = studies_root(registry_root)
    if not root.is_dir():
        return {}
    out: dict[str, Snapshot] = {}
    for d in sorted(root.iterdir()):
        if d.is_dir() and re.match(_ID, d.name):
            snaps = snapshots(registry_root, d.name)
            if snaps:
                out[d.name] = snaps[0]
    return out


# --- diff -------------------------------------------------------------------------------

DIFF_SECTIONS = (
    "components", "relations", "exposes", "calls", "entities", "flows", "activities", "states", "findings",
)  # fmt: skip


def _section(model: dict, name: str) -> list[dict]:
    value = (model.get("interfaces") or {}).get(name) if name in ("exposes", "calls") else model.get(name)
    return [x for x in value if isinstance(x, dict) and "id" in x] if isinstance(value, list) else []


def _label(item: dict) -> str:
    for key in ("name", "title"):
        if item.get(key):
            return str(item[key])
    if item.get("from") and item.get("to"):
        return f"{item['from']} -> {item['to']}"
    if item.get("path") or item.get("method"):
        return " ".join(str(item[k]) for k in ("method", "path") if item.get(k))
    return str(item["id"])


def diff(old: dict, new: dict) -> dict[str, dict]:
    """Added, removed and changed elements per section, matched by id. Citations are left out
    of the comparison: line numbers move with every edit and aren't a change of substance."""
    out: dict[str, dict] = {}
    for name in DIFF_SECTIONS:
        a = {x["id"]: x for x in _section(old, name)}
        b = {x["id"]: x for x in _section(new, name)}
        changed = []
        for i in sorted(a.keys() & b.keys()):
            fa = {k: v for k, v in a[i].items() if k != "cites"}
            fb_ = {k: v for k, v in b[i].items() if k != "cites"}
            if fa != fb_:
                fields = sorted(k for k in fa.keys() | fb_.keys() if fa.get(k) != fb_.get(k))
                changed.append({"id": i, "label": _label(b[i]), "fields": fields})
        out[name] = {
            "added": [{"id": i, "label": _label(b[i])} for i in sorted(b.keys() - a.keys())],
            "removed": [{"id": i, "label": _label(a[i])} for i in sorted(a.keys() - b.keys())],
            "changed": changed,
        }
    return out


# --- across projects --------------------------------------------------------------------

_PARAM = re.compile(r"^(\{[^}]*\}|:[A-Za-z_]\w*|\$\{[^}]*\}|\{…\}|<[^>]*>|\*)$")
_URL_PORT = re.compile(r"^[a-z]+://[^/:]+:(\d{2,5})")


def _norm_path(path: str | None) -> list[str] | None:
    if not path:
        return None
    path = re.sub(r"^[a-z]+://[^/]+", "", path).split("?", 1)[0]
    return ["*" if _PARAM.match(seg) else seg for seg in path.strip("/").split("/") if seg]


def _paths_match(a: list[str] | None, b: list[str] | None) -> bool:
    if a is None or b is None or len(a) != len(b):
        return False
    return all(x == y or "*" in (x, y) for x, y in zip(a, b, strict=True))


def _port_of(call: dict) -> int | None:
    if call.get("port"):
        return int(call["port"])
    m = _URL_PORT.match(call.get("target_url") or "")
    return int(m.group(1)) if m else None


def system_links(
    ports: dict[str, list[int]], depends_on: dict[str, list[str]], models: dict[str, dict]
) -> dict:
    """Cross-project links from the latest studies' outgoing calls (ADR 0019).

    `ports` and `depends_on` come from the registry, `models` are the latest snapshot per
    project. A call names its target project, or is matched to one by port. Its method and
    path are then matched to an endpoint the target's own study says it exposes. Drift lists
    targets the code calls that `depends_on` doesn't have, and `depends_on` entries the code
    never calls (only for studied projects, since an unstudied one has no evidence).
    """
    by_port: dict[int, list[str]] = {}
    for pid, plist in ports.items():
        for port in plist:
            by_port.setdefault(port, []).append(pid)
    links: dict[tuple[str, str], list[dict]] = {}
    unresolved: list[dict] = []
    for pid, model in sorted(models.items()):
        for call in _section(model, "calls"):
            target = call.get("target_project")
            how = "named"
            if not target or target not in ports:
                port = _port_of(call)
                owners = [o for o in by_port.get(port, []) if o != pid] if port else []
                target = owners[0] if len(owners) == 1 else None
                how = "port"
            if not target or target == pid:
                if call.get("kind") == "http":
                    unresolved.append(
                        {
                            "from": pid,
                            "call": call["id"],
                            "target": call.get("target_url")
                            or call.get("target_project")
                            or call.get("port"),
                        }
                    )
                continue
            matched = None
            want = _norm_path(call.get("path") or call.get("target_url"))
            method = (call.get("method") or "").upper()
            for ex in _section(models.get(target, {}), "exposes"):
                if ex.get("kind") != call.get("kind"):
                    continue
                ex_methods = {m.strip().upper() for m in (ex.get("method") or "").split(",") if m.strip()}
                if method and ex_methods and method not in ex_methods and "API_ROUTE" not in ex_methods:
                    continue
                if call.get("kind") != "http" or _paths_match(want, _norm_path(ex.get("path"))):
                    matched = ex["id"]
                    break
            links.setdefault((pid, target), []).append(
                {
                    "id": call["id"],
                    "kind": call.get("kind"),
                    "method": call.get("method"),
                    "path": call.get("path"),
                    "resolved_by": how,
                    "exposed": matched,
                    "target_studied": target in models,
                }
            )
    called: dict[str, set[str]] = {}
    for a, b in links:
        called.setdefault(a, set()).add(b)
    drift = []
    for pid in sorted(models):
        listed = set(depends_on.get(pid, []))
        seen = called.get(pid, set())
        code_only, registry_only = sorted(seen - listed), sorted(listed - seen)
        if code_only or registry_only:
            drift.append({"project": pid, "code_only": code_only, "registry_only": registry_only})
    return {
        "links": [{"from": a, "to": b, "calls": calls} for (a, b), calls in sorted(links.items())],
        "unresolved": unresolved,
        "drift": drift,
        "studied": sorted(models),
    }


# --- search -------------------------------------------------------------------------------

_SEARCH_SECTIONS = (
    ("components", "component", ("name", "summary", "tech", "paths")),
    ("flows", "flow", ("title", "summary", "trigger")),
    ("activities", "activity", ("title", "summary")),
    ("states", "state machine", ("title", "summary")),
    ("entities", "entity", ("name", "summary", "fields")),
    ("exposes", "interface", ("method", "path", "name", "summary")),
    ("calls", "interface", ("method", "path", "target_url", "target_project", "summary")),
    ("findings", "finding", ("title", "detail", "rule")),
)


def _text_of(value: object) -> str:
    if isinstance(value, list):
        return " ".join(_text_of(v) for v in value)
    if isinstance(value, dict):
        return " ".join(_text_of(v) for v in value.values())
    return "" if value is None else str(value)


def search(latest: dict[str, tuple[str, dict]], q: str, limit: int = 100) -> list[dict]:
    """Elements of the latest studies whose text contains `q` (case-insensitive): components,
    flows, activities, state machines, entities, endpoints and findings (ADR 0019)."""
    needle = q.casefold()
    out: list[dict] = []
    for project, (snapshot, model) in sorted(latest.items()):
        for section, kind, fields in _SEARCH_SECTIONS:
            for item in _section(model, section):
                text = " ".join(_text_of(item.get(f)) for f in fields)
                if needle in text.casefold() or needle in str(item["id"]).casefold():
                    out.append(
                        {
                            "project": project,
                            "snapshot": snapshot,
                            "kind": kind,
                            "element": item["id"],
                            "label": _label(item),
                            "summary": str(item.get("summary") or item.get("detail") or "")[:200],
                        }
                    )
                    if len(out) >= limit:
                        return out
    return out


# --- drafts (ADR 0020) --------------------------------------------------------------------


def get_draft(registry_root: Path, project: str) -> Snapshot | None:
    """The study in progress, carried between the rounds of its conversation."""
    folder = _project_dir(registry_root, project) / DRAFT
    if folder.is_dir() and not folder.is_symlink() and (folder / MODEL_FILE).is_file():
        return Snapshot(project, DRAFT, folder)
    return None


def save_draft(
    registry_root: Path, study: Study, *, notes: str | None = None, thread: int | None = None
) -> Snapshot:
    """Write (or replace) the project's draft. It's validated like a snapshot, so the viewer
    can draw it. The thread is kept from the previous draft when it isn't given."""
    project = study.meta.project
    previous = get_draft(registry_root, project)
    if thread is None and previous is not None:
        thread = previous.info().get("thread")
    folder = _project_dir(registry_root, project)
    folder.mkdir(parents=True, exist_ok=True)
    tmp = folder / f".{DRAFT}.tmp"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()
    (tmp / MODEL_FILE).write_text(
        json.dumps(dump(study), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if notes and notes.strip():
        (tmp / NOTES_FILE).write_text(notes.strip() + "\n", encoding="utf-8")
    elif previous is not None and (previous.folder / NOTES_FILE).is_file():
        shutil.copy2(previous.folder / NOTES_FILE, tmp / NOTES_FILE)
    (tmp / INFO_FILE).write_text(json.dumps({"thread": thread}) + "\n", encoding="utf-8")
    if previous is not None:
        shutil.rmtree(previous.folder)
    tmp.rename(folder / DRAFT)
    return Snapshot(project, DRAFT, folder / DRAFT)


def discard_draft(registry_root: Path, project: str) -> bool:
    draft = get_draft(registry_root, project)
    if draft is None:
        return False
    shutil.rmtree(draft.folder)
    return True


def promote_draft(registry_root: Path, project: str, *, keep: int = 10) -> tuple[Snapshot, list[str]]:
    """Save the draft as a dated snapshot (it must still validate) and remove it."""
    draft = get_draft(registry_root, project)
    if draft is None:
        raise StudyNotFound(f"{project}/{DRAFT}")
    study = parse_text((draft.folder / MODEL_FILE).read_text(encoding="utf-8"))
    snap, pruned = save(
        registry_root, study, notes=load_notes(draft), keep=keep, thread=draft.info().get("thread")
    )
    shutil.rmtree(draft.folder)
    return snap, pruned
