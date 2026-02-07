"""FastAPI application factory for the Unified Dashboard."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import settings
from .database import multi_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await multi_db.dispose()


app = FastAPI(title=settings.app_title, lifespan=lifespan)

app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="dash_static")

templates = Jinja2Templates(directory=str(settings.templates_dir))

# Import and register routers
from .routers import home, health  # noqa: E402

app.include_router(home.router)
app.include_router(health.router)
