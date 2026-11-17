"""Project glossaries (ADR 0023): the terms and jargon of one project, kept in the private
registry as `registry/glossary/<project>.json`. The viewer's Glossary tab reads and edits them,
and Claude edits them through the CLI. Every write is a validated, atomic replace of that one file."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

MAX_TERMS = 2000
MAX_TERM = 120
MAX_DEFINITION = 4000
MAX_ALIASES = 12


class GlossaryError(ValueError):
    pass


class TermNotFound(KeyError):
    pass


def slug(term: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", term.lower()).strip("-")


def _file(registry_root: Path, project: str) -> Path:
    # The project name was checked against the registry by the caller; this keeps it a bare filename.
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", project):
        raise GlossaryError(f"bad project name '{project}'")
    return registry_root / "glossary" / f"{project}.json"


def _clean(raw: dict) -> dict:
    """A validated entry. Raises GlossaryError with what's wrong."""
    term = str(raw.get("term", "")).strip()
    definition = str(raw.get("definition", "")).strip()
    if not term:
        raise GlossaryError("a term needs a name")
    if len(term) > MAX_TERM:
        raise GlossaryError(f"a term name is at most {MAX_TERM} characters")
    if not slug(term):
        raise GlossaryError("a term needs at least one letter or digit")
    if not definition:
        raise GlossaryError("a term needs a definition")
    if len(definition) > MAX_DEFINITION:
        raise GlossaryError(f"a definition is at most {MAX_DEFINITION} characters")
    aliases_raw = raw.get("aliases") or []
    if not isinstance(aliases_raw, list):
        raise GlossaryError("aliases must be a list")
    aliases: list[str] = []
    for a in aliases_raw:
        a = str(a).strip()
        if a and a.lower() not in {x.lower() for x in aliases} and a.lower() != term.lower():
            aliases.append(a[:MAX_TERM])
    if len(aliases) > MAX_ALIASES:
        raise GlossaryError(f"at most {MAX_ALIASES} aliases")
    return {"id": slug(term), "term": term, "aliases": aliases, "definition": definition}


def load(registry_root: Path, project: str) -> list[dict]:
    """The project's terms, A to Z. A missing or unreadable file is an empty glossary."""
    path = _file(registry_root, project)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data["terms"] if isinstance(data, dict) else data
        out = [_clean(t) for t in items if isinstance(t, dict)]
    except (OSError, ValueError, KeyError, TypeError):
        return []
    return sorted(out, key=lambda t: t["term"].lower())


def _save(registry_root: Path, project: str, terms: list[dict]) -> None:
    path = _file(registry_root, project)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps({"terms": sorted(terms, key=lambda t: t["term"].lower())}, ensure_ascii=False, indent=2)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".glossary-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text + "\n")
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def upsert(registry_root: Path, project: str, raw: dict, replace: str | None = None) -> dict:
    """Add a term, or change the one with id `replace` (which may rename it). A name that
    another term already uses is refused."""
    entry = _clean(raw)
    terms = load(registry_root, project)
    if replace is not None and not any(t["id"] == replace for t in terms):
        raise TermNotFound(replace)
    others = [t for t in terms if t["id"] != replace]
    taken = {n.lower() for t in others for n in [t["term"], *t["aliases"]]}
    clash = next((n for n in [entry["term"], *entry["aliases"]] if n.lower() in taken), None)
    if clash:
        raise GlossaryError(f"'{clash}' is already a term or alias in this glossary")
    if len(others) + 1 > MAX_TERMS:
        raise GlossaryError(f"a glossary holds at most {MAX_TERMS} terms")
    _save(registry_root, project, [*others, entry])
    return entry


def remove(registry_root: Path, project: str, term_id: str) -> None:
    terms = load(registry_root, project)
    kept = [t for t in terms if t["id"] != term_id]
    if len(kept) == len(terms):
        raise TermNotFound(term_id)
    _save(registry_root, project, kept)
