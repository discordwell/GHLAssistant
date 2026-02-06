"""Candidate scoring, dedup, and search logic."""

from __future__ import annotations

from sqlmodel import Session, select

from ..models import Candidate, CandidateScore, ScoringRubric


def compute_candidate_score(db: Session, candidate_id: int) -> float:
    """Compute weighted composite score (0-100) for a candidate."""
    scores = db.exec(
        select(CandidateScore).where(CandidateScore.candidate_id == candidate_id)
    ).all()

    if not scores:
        return 0.0

    total_weighted = 0.0
    total_weight = 0.0

    for cs in scores:
        rubric = db.get(ScoringRubric, cs.rubric_id)
        if not rubric or rubric.max_points == 0:
            continue
        normalized = (cs.points / rubric.max_points) * 100
        total_weighted += normalized * rubric.weight
        total_weight += rubric.weight

    if total_weight == 0:
        return 0.0

    return round(total_weighted / total_weight, 1)


def find_duplicate(db: Session, email: str | None) -> Candidate | None:
    """Find existing candidate by email for dedup."""
    if not email:
        return None
    return db.exec(
        select(Candidate).where(Candidate.email == email)
    ).first()


def search_candidates(
    db: Session,
    query: str,
    status: str | None = None,
) -> list[Candidate]:
    """Search candidates by name or email."""
    q = query.lower()
    stmt = select(Candidate)
    if status:
        stmt = stmt.where(Candidate.status == status)
    candidates = db.exec(stmt).all()

    return [
        c for c in candidates
        if q in (c.first_name or "").lower()
        or q in (c.last_name or "").lower()
        or q in (c.email or "").lower()
    ]
