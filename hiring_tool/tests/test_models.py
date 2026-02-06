"""Tests for SQLModel table definitions."""

from datetime import datetime

from sqlmodel import Session, select

from hiring_tool.models import (
    Candidate,
    CandidateActivity,
    CandidateScore,
    InterviewFeedback,
    Position,
    ScoringRubric,
)


def test_create_position(db: Session):
    pos = Position(title="Engineer", department="Eng", status="open")
    db.add(pos)
    db.commit()
    db.refresh(pos)

    assert pos.id is not None
    assert pos.title == "Engineer"
    assert pos.status == "open"
    assert isinstance(pos.created_at, datetime)


def test_create_candidate(db: Session):
    c = Candidate(first_name="Jane", last_name="Doe", email="jane@test.com")
    db.add(c)
    db.commit()
    db.refresh(c)

    assert c.id is not None
    assert c.first_name == "Jane"
    assert c.stage == "Applied"
    assert c.status == "active"
    assert c.score is None


def test_candidate_with_position(db: Session):
    pos = Position(title="Designer")
    db.add(pos)
    db.commit()
    db.refresh(pos)

    c = Candidate(first_name="John", last_name="Doe", position_id=pos.id)
    db.add(c)
    db.commit()
    db.refresh(c)

    assert c.position_id == pos.id


def test_interview_feedback(db: Session):
    c = Candidate(first_name="A", last_name="B")
    db.add(c)
    db.commit()
    db.refresh(c)

    fb = InterviewFeedback(
        candidate_id=c.id,
        interviewer_name="Alice",
        interview_type="phone",
        rating=4,
        recommendation="hire",
        strengths="Great communication",
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)

    assert fb.id is not None
    assert fb.rating == 4
    assert fb.recommendation == "hire"


def test_candidate_activity(db: Session):
    c = Candidate(first_name="X", last_name="Y")
    db.add(c)
    db.commit()
    db.refresh(c)

    act = CandidateActivity(
        candidate_id=c.id,
        activity_type="stage_change",
        description="Moved from Applied to Screening",
        created_by="user",
    )
    db.add(act)
    db.commit()
    db.refresh(act)

    assert act.id is not None
    assert act.activity_type == "stage_change"
    assert isinstance(act.created_at, datetime)


def test_scoring_rubric_and_candidate_score(db: Session):
    pos = Position(title="Dev")
    db.add(pos)
    db.commit()
    db.refresh(pos)

    rubric = ScoringRubric(
        position_id=pos.id,
        criteria="Technical Skills",
        weight=2.0,
        max_points=10,
    )
    db.add(rubric)
    db.commit()
    db.refresh(rubric)

    c = Candidate(first_name="Z", last_name="W", position_id=pos.id)
    db.add(c)
    db.commit()
    db.refresh(c)

    score = CandidateScore(
        candidate_id=c.id,
        rubric_id=rubric.id,
        points=8,
        notes="Strong coding skills",
    )
    db.add(score)
    db.commit()
    db.refresh(score)

    assert score.points == 8
    assert score.rubric_id == rubric.id


def test_query_candidates_by_stage(db: Session):
    for i in range(3):
        db.add(Candidate(first_name=f"C{i}", last_name="Test", stage="Applied"))
    db.add(Candidate(first_name="C3", last_name="Test", stage="Screening"))
    db.commit()

    applied = db.exec(select(Candidate).where(Candidate.stage == "Applied")).all()
    assert len(applied) == 3

    screening = db.exec(select(Candidate).where(Candidate.stage == "Screening")).all()
    assert len(screening) == 1


def test_candidate_default_values(db: Session):
    c = Candidate(first_name="Default", last_name="Test")
    db.add(c)
    db.commit()
    db.refresh(c)

    assert c.stage == "Applied"
    assert c.status == "active"
    assert c.ghl_contact_id is None
    assert c.ghl_opportunity_id is None
    assert c.last_synced_at is None
