"""Health and readiness routes for hiring service."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlmodel import Session

from ..database import get_db

router = APIRouter()


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    db.exec(text("SELECT 1"))
    return {"status": "healthy", "service": "hiring"}


@router.get("/ready")
def readiness_check(db: Session = Depends(get_db)):
    db.exec(text("SELECT 1"))
    return {"status": "ready", "service": "hiring"}
