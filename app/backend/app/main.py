"""FastAPI app factory: middleware, error mapping, routers and background tasks."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .config import Settings, read_version
from .db import Database
from .deps import AppState, require_session
from .paths import DocNotFound, DocPathError
from .routers import auth, docs, events, feedback
from .security import LoginLimiter
from .services import git
from .services.events import EventBus, poll_feedback, watch_sources
from .services.feedback import FeedbackConflict, FeedbackNotFound
from .services.sources import SourceManager, SourceNotFound

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
SECURITY_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"no-referrer"),
    (b"x-frame-options", b"DENY"),
]


class OriginGuard:
    """Rejects state-changing requests whose Origin isn't the app's own, and adds security headers.

    The SameSite=Strict cookie already keeps cross-site requests unauthenticated; this is the
    second layer (and covers the public login endpoint against login CSRF).
    """

    def __init__(self, app: ASGIApp, allowed_origins: set[str]) -> None:
        self.app = app
        self.allowed = allowed_origins

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if scope["method"] in UNSAFE_METHODS:
            headers = dict(scope["headers"])
            origin = headers.get(b"origin", b"").decode("latin-1")
            if origin not in self.allowed:
                response = JSONResponse({"detail": "origin not allowed"}, status_code=403)
                await response(scope, receive, send)
                return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                message.setdefault("headers", [])
                message["headers"] = [*message["headers"], *SECURITY_HEADERS]
            await send(message)

        await self.app(scope, receive, send_with_headers)


def _error(status_code: int, detail: str) -> JSONResponse:
    return JSONResponse({"detail": detail}, status_code=status_code)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    db = Database(settings.db_file)
    db.init()
    version = read_version(settings.repo_root)
    state = AppState(
        settings=settings,
        db=db,
        bus=EventBus(),
        limiter=LoginLimiter(settings.login_max_failures, settings.login_window_seconds),
        version=version,
        sources=SourceManager(
            settings.docs_root, settings.registry_root, settings.repo_root, settings.workspace_dir
        ),
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        state.stop = asyncio.Event()
        if settings.watch_docs:
            state.tasks.append(asyncio.create_task(watch_sources(state.sources, state.bus, state.stop)))
        state.tasks.append(
            asyncio.create_task(poll_feedback(db, state.bus, state.stop, settings.feedback_poll_seconds))
        )
        try:
            yield
        finally:
            state.stop.set()
            for task in state.tasks:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
            state.tasks.clear()

    app = FastAPI(
        title="Archeion", version=version, lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None
    )
    app.state.archeion = state

    app.add_middleware(OriginGuard, allowed_origins=settings.allowed_origins)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

    @app.exception_handler(DocPathError)
    async def _bad_path(_: Request, exc: DocPathError) -> JSONResponse:
        return _error(400, str(exc) or "invalid path")

    @app.exception_handler(DocNotFound)
    async def _no_doc(_: Request, exc: DocNotFound) -> JSONResponse:
        return _error(404, "doc not found")

    @app.exception_handler(SourceNotFound)
    async def _no_source(_: Request, exc: SourceNotFound) -> JSONResponse:
        return _error(404, f"no project or source named '{exc.args[0]}'")

    @app.exception_handler(FeedbackNotFound)
    async def _no_item(_: Request, exc: FeedbackNotFound) -> JSONResponse:
        return _error(404, "feedback item not found")

    @app.exception_handler(FeedbackConflict)
    async def _conflict(_: Request, exc: FeedbackConflict) -> JSONResponse:
        return _error(409, str(exc))

    @app.exception_handler(ValueError)
    async def _value(_: Request, exc: ValueError) -> JSONResponse:
        return _error(400, str(exc))

    @app.exception_handler(git.GitError)
    async def _git(_: Request, exc: git.GitError) -> JSONResponse:
        return _error(502, "git failed")

    app.include_router(auth.public)

    # Everything below needs a logged-in session.
    protected = APIRouter(dependencies=[Depends(require_session)])
    protected.include_router(auth.protected)
    protected.include_router(docs.router)
    protected.include_router(docs.extra)
    protected.include_router(events.router)
    protected.include_router(feedback.router)
    app.include_router(protected)

    return app
