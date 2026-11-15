"""Every route except health and login must refuse requests without a session.

This walks the app's real route table (via its OpenAPI schema, which lists every included
route with its full path), so a new endpoint can't be left unprotected by accident.
"""

from __future__ import annotations

import re

from app.routers.auth import PUBLIC_ROUTES


def _routes(app) -> set[tuple[str, str]]:
    schema = app.openapi()
    return {(method.upper(), path) for path, ops in schema["paths"].items() for method in ops}


def test_every_route_requires_a_session(app, client):
    routes = _routes(app)
    assert len(routes) >= 20
    for method, path in sorted(routes - PUBLIC_ROUTES):
        url = re.sub(r"\{[^}]+\}", "1", path)
        r = client.request(method, url, params={"path": "README.md", "rev": "WORKTREE", "q": "xx"}, json={})
        assert r.status_code == 401, f"{method} {path} answered {r.status_code} without a session"


def test_public_routes_exist(app, client):
    assert _routes(app) >= PUBLIC_ROUTES
    assert client.get("/api/health").status_code == 200
