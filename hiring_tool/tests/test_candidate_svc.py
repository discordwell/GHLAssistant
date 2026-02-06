"""Tests for candidate service logic."""

from sqlmodel import Session

from hiring_tool.models import Candidate, CandidateScore, Position, ScoringRubric
from hiring_tool.services.candidate_svc import (
    compute_candidate_score,
    find_duplicate,
    search_candidates,
)


def _setup_rubrics(db: Session):
    """Create a position with scoring rubrics and return (position, rubrics)."""
    pos = Position(title="Dev")
    db.add(pos)
    db.commit()
    db.refresh(pos)

    r1 = ScoringRubric(position_id=pos.id, criteria="Technical", weight=2.0, max_points=10)
    r2 = ScoringRubric(position_id=pos.id, criteria="Communication", weight=1.0, max_points=10)
    db.add(r1)
    db.add(r2)
    db.commit()
    db.refresh(r1)
    db.refresh(r2)

    return pos, [r1, r2]


def test_compute_score_no_scores(db: Session):
    c = Candidate(first_name="A", last_name="B")
    db.add(c)
    db.commit()
    db.refresh(c)

    assert compute_candidate_score(db, c.id) == 0.0


def test_compute_score_single_criterion(db: Session):
    pos, rubrics = _setup_rubrics(db)
    c = Candidate(first_name="A", last_name="B", position_id=pos.id)
    db.add(c)
    db.commit()
    db.refresh(c)

    # Score 8/10 on Technical (weight 2.0) -> 80 * 2.0 / 2.0 = 80
    db.add(CandidateScore(candidate_id=c.id, rubric_id=rubrics[0].id, points=8))
    db.commit()

    score = compute_candidate_score(db, c.id)
    assert score == 80.0


def test_compute_score_weighted_average(db: Session):
    pos, rubrics = _setup_rubrics(db)
    c = Candidate(first_name="A", last_name="B", position_id=pos.id)
    db.add(c)
    db.commit()
    db.refresh(c)

    # Technical: 8/10 (weight 2.0) = 80 * 2.0 = 160
    # Communication: 6/10 (weight 1.0) = 60 * 1.0 = 60
    # Total = 220 / 3.0 = 73.3
    db.add(CandidateScore(candidate_id=c.id, rubric_id=rubrics[0].id, points=8))
    db.add(CandidateScore(candidate_id=c.id, rubric_id=rubrics[1].id, points=6))
    db.commit()

    score = compute_candidate_score(db, c.id)
    assert abs(score - 73.3) < 0.1


def test_compute_score_perfect(db: Session):
    pos, rubrics = _setup_rubrics(db)
    c = Candidate(first_name="A", last_name="B", position_id=pos.id)
    db.add(c)
    db.commit()
    db.refresh(c)

    db.add(CandidateScore(candidate_id=c.id, rubric_id=rubrics[0].id, points=10))
    db.add(CandidateScore(candidate_id=c.id, rubric_id=rubrics[1].id, points=10))
    db.commit()

    assert compute_candidate_score(db, c.id) == 100.0


def test_find_duplicate_by_email(db: Session):
    c = Candidate(first_name="Jane", last_name="Doe", email="jane@test.com")
    db.add(c)
    db.commit()

    dup = find_duplicate(db, "jane@test.com")
    assert dup is not None
    assert dup.first_name == "Jane"


def test_find_duplicate_no_match(db: Session):
    c = Candidate(first_name="Jane", last_name="Doe", email="jane@test.com")
    db.add(c)
    db.commit()

    assert find_duplicate(db, "other@test.com") is None


def test_find_duplicate_none_email(db: Session):
    assert find_duplicate(db, None) is None


def test_search_by_first_name(db: Session):
    db.add(Candidate(first_name="Alice", last_name="Smith"))
    db.add(Candidate(first_name="Bob", last_name="Jones"))
    db.commit()

    results = search_candidates(db, "alice")
    assert len(results) == 1
    assert results[0].first_name == "Alice"


def test_search_by_email(db: Session):
    db.add(Candidate(first_name="A", last_name="B", email="test@example.com"))
    db.add(Candidate(first_name="C", last_name="D", email="other@example.com"))
    db.commit()

    results = search_candidates(db, "test@")
    assert len(results) == 1


def test_search_with_status_filter(db: Session):
    db.add(Candidate(first_name="Alice", last_name="S", status="active"))
    db.add(Candidate(first_name="Alice", last_name="J", status="rejected"))
    db.commit()

    results = search_candidates(db, "alice", status="active")
    assert len(results) == 1
    assert results[0].last_name == "S"
