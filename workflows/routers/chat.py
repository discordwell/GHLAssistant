"""Chat router — AI assistant with SSE streaming."""

from __future__ import annotations

import json

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from starlette.responses import StreamingResponse

from ..app import templates
from ..services import chat_svc

router = APIRouter(tags=["chat"])


@router.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    return templates.TemplateResponse(
        "chat/index.html",
        {"request": request, "active_nav": "chat"},
    )


@router.post("/chat/send")
async def chat_send(request: Request):
    """Stream a chat response via SSE."""
    body = await request.json()
    messages = body.get("messages", [])

    async def event_stream():
        async for chunk in chat_svc.stream_chat(messages):
            data = json.dumps(chunk)
            yield f"data: {data}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
