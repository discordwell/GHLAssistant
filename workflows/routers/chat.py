"""Chat router — AI assistant with SSE streaming."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from starlette.responses import StreamingResponse

from ..app import templates
from ..security import require_chat_api_key
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
    require_chat_api_key(request)
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Invalid chat payload") from exc

    messages = body.get("messages", [])
    if not isinstance(messages, list):
        raise HTTPException(status_code=422, detail="'messages' must be a list")

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
