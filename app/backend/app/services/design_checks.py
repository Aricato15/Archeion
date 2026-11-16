"""What a design asks of the rest of the system, and how a built project compares with it (ADR 0022
point 10 and phase 4). Read-only: nothing here edits a neighbour; the viewer offers to send it an item."""

from __future__ import annotations

from pathlib import Path

from . import designs as dz
from . import studies as st


def _studied_exposes(registry_root: Path, pid: str) -> list[dict] | None:
    """What the latest valid study of a project says it exposes; None when it hasn't been studied."""
    snaps = st.snapshots(registry_root, pid)
    if not snaps:
        return None
    model, problems = st.load(snaps[0])
    if problems:
        return None
    return list((model.get("interfaces") or {}).get("exposes", []) or [])


def _designed_exposes(registry_root: Path, pid: str) -> list[dict]:
    """What the working copies of a project's designs say it will expose."""
    out: list[dict] = []
    for slug in dz.slugs(registry_root, pid):
        model, _ = dz.load(dz.get(registry_root, pid, slug).folder, pid)
        out += list((model.get("interfaces") or {}).get("exposes", []) or [])
    return out


def _methods(value: str | None) -> set[str]:
    return {m.strip().upper() for m in (value or "").split(",") if m.strip()}


def _matches(call: dict, exposed: dict) -> bool:
    if call.get("kind") != exposed.get("kind"):
        return False
    wanted, have = _methods(call.get("method")), _methods(exposed.get("method"))
    if wanted and have and not wanted & have and "API_ROUTE" not in have:
        return False
    if call.get("kind") != "http":
        return (call.get("name") or call.get("path")) == (exposed.get("name") or exposed.get("path"))
    return st._paths_match(st._norm_path(call.get("path")), st._norm_path(exposed.get("path")))


def _label(item: dict) -> str:
    return " ".join(str(item[k]) for k in ("method", "path", "name") if item.get(k)) or str(item.get("id"))


def impact(registry, registry_root: Path, project: str, model: dict) -> list[dict]:
    """The design's effects on other projects, each with the project to tell (`neighbour`) and what
    to tell it (`suggestion`). Severity: block, warn, info."""
    items: list[dict] = []
    structure = model.get("structure") or {}
    calls = list((model.get("interfaces") or {}).get("calls", []) or [])
    by_port: dict[int, list[str]] = {}
    for p in registry.projects.values():
        for port in p.ports:
            by_port.setdefault(port, []).append(p.id)

    def add(
        kind: str, severity: str, message: str, neighbour: str | None = None, suggestion: str | None = None
    ):
        items.append(
            {
                "kind": kind,
                "severity": severity,
                "message": message,
                "neighbour": neighbour,
                "suggestion": suggestion,
            }
        )

    called: set[str] = set()
    for call in calls:
        target = call.get("target_project")
        if not target and call.get("port"):
            owners = [o for o in by_port.get(int(call["port"]), []) if o != project]
            target = owners[0] if len(owners) == 1 else None
        what = _label(call)
        if not target:
            add(
                "unresolved-call",
                "warn",
                f"The call '{what}' doesn't name a registered project or a known port.",
            )
            continue
        if target not in registry.projects:
            add("unknown-project", "warn", f"The call '{what}' names '{target}', which isn't registered.")
            continue
        called.add(target)
        built = _studied_exposes(registry_root, target)
        if built is not None and any(_matches(call, e) for e in built):
            continue
        if any(_matches(call, e) for e in _designed_exposes(registry_root, target)):
            add("planned-elsewhere", "info", f"{target} plans to expose '{what}' in its own design.", target)
        elif built is None:
            add(
                "unverified",
                "info",
                f"{target} hasn't been studied, so '{what}' can't be checked against what it exposes.",
                target,
            )
        else:
            add(
                "missing-endpoint",
                "warn",
                f"{target} doesn't expose '{what}', which this design calls.",
                target,
                f"The design of {project} will call {what} on {target}, which doesn't expose it today."
                " Please add it, or say what to call instead.",
            )
    declared = set(structure.get("depends_on") or [])
    for target in sorted(called - declared):
        add(
            "depends-on-missing",
            "warn",
            f"The design calls {target}, but structure.depends_on doesn't list it.",
            target,
        )
    for target in sorted(declared - called):
        add(
            "depends-on-unused",
            "info",
            f"structure.depends_on lists {target}, but no call in the model uses it.",
            target,
        )

    # Endpoints the built project exposes today, that other projects call, and the design drops.
    built_own = _studied_exposes(registry_root, project)
    if built_own:
        designed = list((model.get("interfaces") or {}).get("exposes", []) or [])
        models = {}
        for pid, snap in st.latest_by_project(registry_root).items():
            if pid in registry.projects:
                m, problems = st.load(snap)
                if not problems:
                    models[pid] = m
        links = st.system_links(
            {p.id: p.ports for p in registry.projects.values()},
            {p.id: p.depends_on for p in registry.projects.values()},
            {**models},
        )
        callers: dict[str, set[str]] = {}
        for link in links["links"]:
            if link["to"] == project:
                for c in link["calls"]:
                    if c["exposed"]:
                        callers.setdefault(c["exposed"], set()).add(link["from"])
        for e in built_own:
            if any(_matches({**e}, d) for d in designed):
                continue
            for caller in sorted(callers.get(e["id"], ())):
                add(
                    "endpoint-dropped",
                    "warn",
                    f"{caller} calls {_label(e)} on {project}, and the design no longer exposes it.",
                    caller,
                    f"The design of {project} drops {_label(e)}, which {caller} calls. Plan to move to its"
                    " replacement before it goes.",
                )
    for port in structure.get("ports") or []:
        others = [o for o in by_port.get(port, []) if o != project]
        if others:
            add("port-clash", "block", f"Port {port} is already recorded for {', '.join(sorted(others))}.")
    order = {"block": 0, "warn": 1, "info": 2}
    return sorted(items, key=lambda i: order[i["severity"]])


# --- built vs designed ------------------------------------------------------------------


def _key_components(model: dict) -> dict[str, dict]:
    return {str(c.get("name", c["id"])).casefold(): c for c in model.get("components", []) or []}


def _key_exposes(model: dict) -> dict[str, dict]:
    out = {}
    for e in (model.get("interfaces") or {}).get("exposes", []) or []:
        path = "/".join(st._norm_path(e.get("path")) or []) or str(e.get("name") or e["id"])
        out[f"{(e.get('method') or '').upper()} {path}".strip()] = e
    return out


def _key_calls(model: dict) -> dict[str, dict]:
    out = {}
    for c in (model.get("interfaces") or {}).get("calls", []) or []:
        path = "/".join(st._norm_path(c.get("path")) or []) or str(c.get("name") or c["id"])
        target = c.get("target_project") or c.get("port") or "?"
        out[f"{target} {(c.get('method') or '').upper()} {path}".strip()] = c
    return out


def _key_entities(model: dict) -> dict[str, dict]:
    return {str(e["name"]).casefold(): e for e in model.get("entities", []) or []}


def built_vs_designed(designed: dict, built: dict | None, snapshot: str | None) -> dict:
    """Compare the design's model with the latest study's, section by section, by name (ids
    differ between a design and a study). `designed_only` is still to build, `built_only` isn't in
    the design (yet)."""
    if built is None:
        return {"studied": None, "sections": {}}
    sections = {}
    for name, keyer in (
        ("components", _key_components),
        ("exposes", _key_exposes),
        ("calls", _key_calls),
        ("entities", _key_entities),
    ):
        a, b = keyer(designed), keyer(built)
        sections[name] = {
            "designed_only": sorted(a[k].get("name") or _label(a[k]) for k in a.keys() - b.keys()),
            "built_only": sorted(b[k].get("name") or _label(b[k]) for k in b.keys() - a.keys()),
            "both": len(a.keys() & b.keys()),
        }
    return {"studied": snapshot, "sections": sections}
