"""FastAPI application for the hiring tool."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import settings
from .database import create_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    yield


app = FastAPI(title="Hiring Tool", lifespan=lifespan)

app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")

templates = Jinja2Templates(directory=str(settings.templates_dir))

# Import and register routers
from .routers import board, candidates, positions, interviews, analytics, sync  # noqa: E402

app.include_router(board.router)
app.include_router(candidates.router, prefix="/candidates", tags=["candidates"])
app.include_router(positions.router, prefix="/positions", tags=["positions"])
app.include_router(interviews.router, prefix="/interviews", tags=["interviews"])
app.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
app.include_router(sync.router, prefix="/sync", tags=["sync"])


@app.get("/")
async def root():
    return RedirectResponse("/board")
