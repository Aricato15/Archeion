"""Server-sent events: doc changes and feedback changes, pushed to the browser."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from ..deps import AppState, get_state, session_from_request
from ..services.events import Event

router = APIRouter(prefix="/api")

PING_SECONDS = 20


@router.get("/events")
async def events(request: Request, state: AppState = Depends(get_state)) -> StreamingResponse:
    queue = state.bus.subscribe()

    async def stream():
        try:
            yield "retry: 3000\n\n"
            yield Event("hello", {"version": state.version}).sse()
            while not state.stop.is_set():
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=PING_SECONDS)
                except TimeoutError:
                    # Also the moment to notice an expired or revoked session.
                    if await asyncio.to_thread(session_from_request, state, request) is None:
                        yield Event("session.expired").sse()
                        return
                    yield Event("ping").sse()
                    continue
                yield event.sse()
        finally:
            state.bus.unsubscribe(queue)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
