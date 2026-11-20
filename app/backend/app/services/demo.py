"""The example project (ADR 0030): a made-up project kept in the committed `demo-example-data/`
folder, for show and tell.

It is read straight from that folder, never copied into the private registry, so it can't mix
with the user's projects. The rule (ADR 0030): nothing about it is written, reaches a database or
reaches Claude. `touches` is the check the feedback service uses to refuse anything about it, and
`read_only` stops every write to its design and glossary.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, Request

DEMO_DIR = "demo-example-data"
DEMO_PROJECT = "example-project"
REGISTRY_SOURCE = "demo-registry"  # the doc source for its registry page, like `registry` for the others


class DemoError(ValueError):
    """Something about the example project was refused."""


def registry_root(repo_root: Path) -> Path:
    """The demo's own registry data (project page, design, glossary), in the registry's layout."""
    return repo_root / DEMO_DIR / "registry"


def root_for(settings, project: str) -> Path:
    """Where a project's registry data (designs, glossary, studies) lives: the demo's own folder
    for the example project, the private registry for everything else."""
    return registry_root(settings.repo_root) if project == DEMO_PROJECT else settings.registry_root


def is_demo_path(raw: str) -> bool:
    """A registry page's `path` that points into the demo folder."""
    return raw.replace("\\", "/").lstrip("./").startswith(f"{DEMO_DIR}/")


def touches(source: str | None = None, anchor: dict | None = None) -> bool:
    """True when a feedback item is about the example project, as its source or its task."""
    if source == DEMO_PROJECT:
        return True
    task = (anchor or {}).get("task") or {}
    return task.get("project") == DEMO_PROJECT


def refuse() -> DemoError:
    return DemoError(
        "This is demo data, so nothing is changed: nothing about the example project is saved, "
        "sent to Claude or stored in the database."
    )


def read_only(request: Request) -> None:
    """A router dependency: any write to a route about the example project is refused."""
    if (
        request.method not in ("GET", "HEAD", "OPTIONS")
        and request.path_params.get("project") == DEMO_PROJECT
    ):
        raise HTTPException(400, str(refuse()))
