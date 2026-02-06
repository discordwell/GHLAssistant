"""Tests for FastAPI routes using TestClient."""

from fastapi.testclient import TestClient
from sqlmodel import Session

from hiring_tool.models import Candidate, CandidateActivity, Position, ScoringRubric


def test_root_redirects_to_board(client: TestClient):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"] == "/board"


def test_board_empty(client: TestClient):
    resp = client.get("/board")
    assert resp.status_code == 200
    assert "Hiring Board" in resp.text


def test_board_with_candidates(client: TestClient, db: Session):
    db.add(Candidate(first_name="Alice", last_name="S", stage="Applied"))
    db.add(Candidate(first_name="Bob", last_name="J", stage="Screening"))
    db.commit()

    resp = client.get("/board")
    assert resp.status_code == 200
    assert "Alice" in resp.text
    assert "Bob" in resp.text


def test_board_filter_by_position(client: TestClient, db: Session):
    pos = Position(title="Dev")
    db.add(pos)
    db.commit()
    db.refresh(pos)

    db.add(Candidate(first_name="Alice", last_name="S", position_id=pos.id))
    db.add(Candidate(first_name="Bob", last_name="J"))
    db.commit()

    resp = client.get(f"/board?position_id={pos.id}")
    assert resp.status_code == 200
    assert "Alice" in resp.text


def test_move_candidate(client: TestClient, db: Session):
    c = Candidate(first_name="Alice", last_name="S", stage="Applied")
    db.add(c)
    db.commit()
    db.refresh(c)

    resp = client.post(f"/board/move/{c.id}", data={"stage": "Screening"})
    assert resp.status_code == 200

    db.refresh(c)
    assert c.stage == "Screening"


# --- Candidates ---

def test_list_candidates_empty(client: TestClient):
    resp = client.get("/candidates/")
    assert resp.status_code == 200
    assert "No candidates found" in resp.text


def test_create_candidate(client: TestClient):
    resp = client.post("/candidates/new", data={
        "first_name": "Jane",
        "last_name": "Doe",
        "email": "jane@test.com",
        "stage": "Applied",
    }, follow_redirects=False)
    assert resp.status_code == 303
    assert "/candidates/" in resp.headers["location"]


def test_candidate_detail(client: TestClient, db: Session):
    c = Candidate(first_name="Jane", last_name="Doe", email="jane@test.com")
    db.add(c)
    db.commit()
    db.refresh(c)

    resp = client.get(f"/candidates/{c.id}")
    assert resp.status_code == 200
    assert "Jane" in resp.text
    assert "Doe" in resp.text


def test_edit_candidate(client: TestClient, db: Session):
    c = Candidate(first_name="Jane", last_name="Doe")
    db.add(c)
    db.commit()
    db.refresh(c)

    resp = client.post(f"/candidates/{c.id}/edit", data={
        "first_name": "Janet",
        "last_name": "Doe",
        "stage": "Screening",
    }, follow_redirects=False)
    assert resp.status_code == 303

    db.refresh(c)
    assert c.first_name == "Janet"
    assert c.stage == "Screening"


def test_add_note(client: TestClient, db: Session):
    c = Candidate(first_name="A", last_name="B")
    db.add(c)
    db.commit()
    db.refresh(c)

    resp = client.post(f"/candidates/{c.id}/note", data={"note": "Great candidate"})
    assert resp.status_code == 200


def test_candidate_search(client: TestClient, db: Session):
    db.add(Candidate(first_name="Alice", last_name="Wonder"))
    db.add(Candidate(first_name="Bob", last_name="Builder"))
    db.commit()

    resp = client.get("/candidates/?search=alice")
    assert resp.status_code == 200
    assert "Alice" in resp.text


# --- Positions ---

def test_list_positions_empty(client: TestClient):
    resp = client.get("/positions/")
    assert resp.status_code == 200
    assert "No positions yet" in resp.text


def test_create_position(client: TestClient):
    resp = client.post("/positions/new", data={
        "title": "Software Engineer",
        "department": "Engineering",
        "status": "open",
        "rubric_criteria_0": "Technical Skills",
        "rubric_weight_0": "2.0",
        "rubric_max_0": "10",
    }, follow_redirects=False)
    assert resp.status_code == 303


def test_edit_position(client: TestClient, db: Session):
    pos = Position(title="Dev", status="open")
    db.add(pos)
    db.commit()
    db.refresh(pos)

    resp = client.post(f"/positions/{pos.id}/edit", data={
        "title": "Senior Dev",
        "status": "paused",
    }, follow_redirects=False)
    assert resp.status_code == 303

    db.refresh(pos)
    assert pos.title == "Senior Dev"
    assert pos.status == "paused"


# --- Interviews ---

def test_new_interview_form(client: TestClient, db: Session):
    c = Candidate(first_name="A", last_name="B")
    db.add(c)
    db.commit()
    db.refresh(c)

    resp = client.get(f"/interviews/new/{c.id}")
    assert resp.status_code == 200
    assert "Interview Feedback" in resp.text


def test_create_interview(client: TestClient, db: Session):
    c = Candidate(first_name="A", last_name="B")
    db.add(c)
    db.commit()
    db.refresh(c)

    resp = client.post(f"/interviews/new/{c.id}", data={
        "interviewer_name": "Alice",
        "interview_type": "phone",
        "rating": "4",
        "recommendation": "hire",
    }, follow_redirects=False)
    assert resp.status_code == 303


# --- Analytics ---

def test_analytics_empty(client: TestClient):
    resp = client.get("/analytics/")
    assert resp.status_code == 200
    assert "Hiring Analytics" in resp.text


def test_analytics_with_data(client: TestClient, db: Session):
    pos = Position(title="Dev", status="open")
    db.add(pos)
    db.commit()
    db.refresh(pos)

    db.add(Candidate(first_name="A", last_name="B", status="active", position_id=pos.id))
    db.add(Candidate(first_name="C", last_name="D", status="hired", position_id=pos.id))
    db.commit()

    resp = client.get("/analytics/")
    assert resp.status_code == 200
    assert "2" in resp.text  # total candidates


# --- Sync ---

def test_sync_status(client: TestClient):
    resp = client.get("/sync/")
    assert resp.status_code == 200
    assert "GHL Sync" in resp.text
