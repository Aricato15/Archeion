"""The composed study of a group (ADR 0027): its own top-level study plus the latest study
of each member, read as they are and never redone.

A group's own study covers its top level. Each member that has a study is read from it, and
the flattened view puts them together: every member becomes a container, its components sit
inside it under namespaced ids, and links found in the members' code become relations between
the containers. Where the group's own study has a component named like a member, the member's
study wins and the difference is reported, so the user can start a thread about it.

Read-only: nothing here writes to the registry.
"""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

from . import studies as st
from .registry import Project, Registry

# What a composed view leaves out: the sections whose ids cross-refer in ways that don't survive
# namespacing, and that read better in the member's own study.
OMITTED = ["flows", "activities", "states", "findings"]


def top_members(reg: Registry, home: Project) -> list[Project]:
    """The group's members that sit directly in it: not nested under another member."""
    found = [reg.projects[m] for m in home.members if m in reg.projects]
    return sorted((m for m in found if m.parent in (None, home.id)), key=lambda m: m.id)


def _ns(member: str, ident: str) -> str:
    # Not a dot: a foreign key reads "<entity id>.<field>", so an id can't hold one.
    out = f"{member}__{ident}"
    if len(out) <= 120:
        return out
    return f"{member}__{hashlib.sha1(ident.encode()).hexdigest()[:10]}"


def _container_kind(member: Project) -> str:
    return "package" if member.type == "module" else "service"


def compose(registry_root: Path, reg: Registry, group_id: str) -> dict:
    """The group's members' studies, a flattened model of them, and where they differ from the
    group's own. `model` is None when there's nothing to compose or it doesn't validate."""
    home = reg.projects[group_id]
    own_snap = next(iter(st.snapshots(registry_root, group_id)), None)
    own = st.load(own_snap)[0] if own_snap else {}
    members = top_members(reg, home)
    snaps = {m.id: next(iter(st.snapshots(registry_root, m.id)), None) for m in members}
    loaded: dict[str, dict] = {}
    for mid, snap in snaps.items():
        if snap is not None:
            model, problems = st.load(snap)
            if not problems:
                loaded[mid] = model

    rows = [
        {
            "project": m.id,
            "title": m.title,
            "type": m.type,
            "kind": m.kind,
            "snapshot": snaps[m.id].id if snaps[m.id] else None,
            "date": (loaded.get(m.id, {}).get("meta") or {}).get("date") if m.id in loaded else None,
            "commit": (loaded.get(m.id, {}).get("meta") or {}).get("commit") if m.id in loaded else None,
            "has_study": snaps[m.id] is not None,
            "valid": m.id in loaded or snaps[m.id] is None,
        }
        for m in members
    ]

    # Where the group's own study names a member, the member's study wins.
    overridden: list[dict] = []
    own_by_id = {c["id"]: c for c in own.get("components", []) if isinstance(c, dict) and "id" in c}
    for m in members:
        mine = own_by_id.get(m.id)
        if mine is None or m.id not in loaded:
            continue
        theirs = (loaded[m.id].get("meta") or {}).get("summary", "")
        ours = mine.get("summary", "")
        overridden.append(
            {
                "component": m.id,
                "name": mine.get("name", m.id),
                "group_summary": ours,
                "member_summary": theirs,
                "differs": bool(ours and theirs and ours.strip() != theirs.strip()),
            }
        )
    won = {o["component"] for o in overridden}

    member_ids = {m.id for m in members}
    links = st.system_links(
        {m.id: m.ports for m in members},
        {m.id: [d for d in m.depends_on if d in member_ids] for m in members},
        loaded,
    ).get("links", [])
    model = None
    problems: list[str] = []
    if own or loaded:
        raw = _flatten(own, members, loaded, won, group_id, links)
        try:
            model = st.dump(st.parse(raw))
        except st.StudyError as exc:
            problems = [str(exc)]
    return {
        "group": group_id,
        "own": own_snap.id if own_snap else None,
        "needs_restudy": home.needs_restudy,
        "members": rows,
        "overridden": overridden,
        "omitted": OMITTED,
        "model": model,
        "problems": problems,
    }


def _flatten(
    own: dict,
    members: list[Project],
    loaded: dict[str, dict],
    won: set[str],
    group_id: str,
    links: list[dict],
) -> dict:
    own_meta = own.get("meta") or {}
    commit = own_meta.get("commit") or next(
        ((m.get("meta") or {}).get("commit") for m in loaded.values() if (m.get("meta") or {}).get("commit")),
        None,
    )
    components: list[dict] = [
        c for c in own.get("components", []) if isinstance(c, dict) and c.get("id") not in won
    ]
    relations: list[dict] = list(own.get("relations", []))
    exposes: list[dict] = list((own.get("interfaces") or {}).get("exposes", []))
    calls: list[dict] = list((own.get("interfaces") or {}).get("calls", []))
    entities: list[dict] = list(own.get("entities", []))
    taken = {c["id"] for c in components}

    for m in members:
        mine = loaded.get(m.id)
        meta = (mine or {}).get("meta") or {}
        summary = meta.get("summary") or ("" if mine else "No study of this member yet.")
        if m.id not in taken:
            components.append(
                {"id": m.id, "name": m.title, "kind": _container_kind(m), "summary": summary[:4000]}
            )
            taken.add(m.id)
        if not mine:
            continue
        ids = {c["id"] for c in mine.get("components", []) if isinstance(c, dict) and "id" in c}
        for c in mine.get("components", []):
            if not isinstance(c, dict) or "id" not in c:
                continue
            copy = {
                **c,
                "id": _ns(m.id, c["id"]),
                "parent": _ns(m.id, c["parent"]) if c.get("parent") in ids else m.id,
            }
            components.append(copy)
        for r in mine.get("relations", []):
            relations.append(
                {**r, "id": _ns(m.id, r["id"]), "from": _ns(m.id, r["from"]), "to": _ns(m.id, r["to"])}
            )
        for e in (mine.get("interfaces") or {}).get("exposes", []):
            exposes.append(
                {
                    **e,
                    "id": _ns(m.id, e["id"]),
                    **({"handler": _ns(m.id, e["handler"])} if e.get("handler") else {}),
                }
            )
        for c in (mine.get("interfaces") or {}).get("calls", []):
            calls.append(
                {**c, "id": _ns(m.id, c["id"]), **({"from": _ns(m.id, c["from"])} if c.get("from") else {})}
            )
        for ent in mine.get("entities", []):
            fields = [
                {
                    **f,
                    **(
                        {"fk": _ns(m.id, f["fk"].split(".", 1)[0]) + "." + f["fk"].split(".", 1)[1]}
                        if f.get("fk") and "." in f["fk"]
                        else {}
                    ),
                }
                for f in ent.get("fields", [])
            ]
            entities.append(
                {
                    **ent,
                    "id": _ns(m.id, ent["id"]),
                    "fields": fields,
                    **({"store": _ns(m.id, ent["store"])} if ent.get("store") else {}),
                }
            )

    # What the members' code says about each other: an arrow between their containers.
    for link in links:
        if link.get("from") in taken and link.get("to") in taken:
            paths = [
                " ".join(x for x in (c.get("method"), c.get("path")) if x) for c in link.get("calls", [])
            ]
            relations.append(
                {
                    "id": _ns("link", f"{link['from']}__{link['to']}"),
                    "from": link["from"],
                    "to": link["to"],
                    "kind": "http",
                    "label": ", ".join(p for p in paths[:2] if p) or None,
                }
            )
    return {
        "schema": 1,
        "meta": {
            "project": group_id,
            "date": date.today().isoformat(),
            "commit": commit,
            "summary": f"Composed from the studies of {len(loaded)} of {len(members)} member(s).",
            "coverage": {
                "note": "; ".join(
                    f"{m.id}: {(loaded[m.id].get('meta') or {}).get('date', '?')}"
                    for m in members
                    if m.id in loaded
                )[:2000]
            },
        },
        "components": components,
        "relations": relations,
        "interfaces": {"exposes": exposes, "calls": calls},
        "entities": entities,
    }
