"""Test survey service."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from crm.models.location import Location
from crm.models.survey import SurveyQuestion
from crm.services import survey_svc


@pytest.mark.asyncio
async def test_create_and_list_surveys(db: AsyncSession, location: Location):
    await survey_svc.create_survey(db, location.id, name="NPS Survey")
    await survey_svc.create_survey(db, location.id, name="Feedback Survey")

    surveys = await survey_svc.list_surveys(db, location.id)
    assert len(surveys) == 2
    names = [s.name for s in surveys]
    assert "NPS Survey" in names
    assert "Feedback Survey" in names


@pytest.mark.asyncio
async def test_get_survey(db: AsyncSession, location: Location):
    survey = await survey_svc.create_survey(
        db, location.id, name="My Survey", description="A test survey"
    )
    fetched = await survey_svc.get_survey(db, survey.id)
    assert fetched is not None
    assert fetched.name == "My Survey"
    assert fetched.description == "A test survey"
    assert fetched.is_active is True


@pytest.mark.asyncio
async def test_update_survey(db: AsyncSession, location: Location):
    survey = await survey_svc.create_survey(db, location.id, name="Old Survey")
    updated = await survey_svc.update_survey(
        db, survey.id, name="Updated Survey", is_active=False
    )
    assert updated is not None
    assert updated.name == "Updated Survey"
    assert updated.is_active is False


@pytest.mark.asyncio
async def test_delete_survey(db: AsyncSession, location: Location):
    survey = await survey_svc.create_survey(db, location.id, name="Delete Me")
    result = await survey_svc.delete_survey(db, survey.id)
    assert result is True

    fetched = await survey_svc.get_survey(db, survey.id)
    assert fetched is None


@pytest.mark.asyncio
async def test_add_question(db: AsyncSession, location: Location):
    survey = await survey_svc.create_survey(db, location.id, name="Q Survey")
    q1 = await survey_svc.add_question(
        db, survey.id, question_text="How satisfied?", question_type="rating"
    )
    q2 = await survey_svc.add_question(
        db, survey.id, question_text="Any comments?", question_type="long_text"
    )

    # Auto-position: first question is 0, second is 1
    assert q1.position == 0
    assert q2.position == 1
    assert q1.question_text == "How satisfied?"
    assert q2.question_type == "long_text"


@pytest.mark.asyncio
async def test_delete_question(db: AsyncSession, location: Location):
    survey = await survey_svc.create_survey(db, location.id, name="Del Q Survey")
    q = await survey_svc.add_question(
        db, survey.id, question_text="Remove me", question_type="text"
    )
    result = await survey_svc.delete_question(db, q.id)
    assert result is True

    # Verify question is gone
    fetched = await survey_svc.get_survey(db, survey.id)
    assert fetched is not None
    assert len(fetched.questions) == 0


@pytest.mark.asyncio
async def test_reorder_questions(db: AsyncSession, location: Location):
    survey = await survey_svc.create_survey(db, location.id, name="Reorder Survey")
    q1 = await survey_svc.add_question(
        db, survey.id, question_text="Q1", question_type="text"
    )
    q2 = await survey_svc.add_question(
        db, survey.id, question_text="Q2", question_type="text"
    )
    q3 = await survey_svc.add_question(
        db, survey.id, question_text="Q3", question_type="text"
    )

    # Reverse the order: Q3, Q2, Q1
    await survey_svc.reorder_questions(
        db, survey.id, [str(q3.id), str(q2.id), str(q1.id)]
    )

    fetched = await survey_svc.get_survey(db, survey.id)
    assert fetched is not None
    questions = sorted(fetched.questions, key=lambda q: q.position)
    assert questions[0].question_text == "Q3"
    assert questions[1].question_text == "Q2"
    assert questions[2].question_text == "Q1"


@pytest.mark.asyncio
async def test_create_submission(db: AsyncSession, location: Location):
    survey = await survey_svc.create_survey(db, location.id, name="Submit Survey")
    sub = await survey_svc.create_submission(
        db, location.id, survey.id,
        answers_json={"q1": 5, "q2": "Great service"},
    )
    assert sub.answers_json == {"q1": 5, "q2": "Great service"}
    assert sub.survey_id == survey.id


@pytest.mark.asyncio
async def test_list_submissions(db: AsyncSession, location: Location):
    survey = await survey_svc.create_survey(db, location.id, name="List Sub Survey")
    for i in range(3):
        await survey_svc.create_submission(
            db, location.id, survey.id, answers_json={"index": i}
        )

    subs, total = await survey_svc.list_submissions(db, survey.id)
    assert total == 3
    assert len(subs) == 3


@pytest.mark.asyncio
async def test_delete_survey_cascades(db: AsyncSession, location: Location):
    survey = await survey_svc.create_survey(db, location.id, name="Cascade Survey")
    q1 = await survey_svc.add_question(
        db, survey.id, question_text="Q1", question_type="text"
    )
    q2 = await survey_svc.add_question(
        db, survey.id, question_text="Q2", question_type="rating"
    )

    question_ids = [q1.id, q2.id]
    await survey_svc.delete_survey(db, survey.id)

    # Verify questions are gone
    for qid in question_ids:
        stmt = select(SurveyQuestion).where(SurveyQuestion.id == qid)
        result = (await db.execute(stmt)).scalar_one_or_none()
        assert result is None
