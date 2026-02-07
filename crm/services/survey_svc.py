"""Survey service - CRUD surveys, questions, submissions."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.survey import Survey, SurveyQuestion, SurveySubmission


async def list_surveys(
    db: AsyncSession, location_id: uuid.UUID
) -> list[Survey]:
    stmt = (
        select(Survey)
        .where(Survey.location_id == location_id)
        .options(selectinload(Survey.questions))
        .order_by(Survey.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_survey(db: AsyncSession, survey_id: uuid.UUID) -> Survey | None:
    stmt = (
        select(Survey)
        .where(Survey.id == survey_id)
        .options(
            selectinload(Survey.questions),
            selectinload(Survey.submissions),
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_survey(
    db: AsyncSession, location_id: uuid.UUID, **kwargs
) -> Survey:
    survey = Survey(location_id=location_id, **kwargs)
    db.add(survey)
    await db.commit()
    await db.refresh(survey)
    return survey


async def update_survey(
    db: AsyncSession, survey_id: uuid.UUID, **kwargs
) -> Survey | None:
    stmt = select(Survey).where(Survey.id == survey_id)
    survey = (await db.execute(stmt)).scalar_one_or_none()
    if not survey:
        return None
    for k, v in kwargs.items():
        setattr(survey, k, v)
    await db.commit()
    await db.refresh(survey)
    return survey


async def delete_survey(db: AsyncSession, survey_id: uuid.UUID) -> bool:
    stmt = select(Survey).where(Survey.id == survey_id)
    survey = (await db.execute(stmt)).scalar_one_or_none()
    if not survey:
        return False
    await db.delete(survey)
    await db.commit()
    return True


async def add_question(
    db: AsyncSession, survey_id: uuid.UUID, **kwargs
) -> SurveyQuestion:
    stmt = select(func.max(SurveyQuestion.position)).where(
        SurveyQuestion.survey_id == survey_id
    )
    result = (await db.execute(stmt)).scalar()
    max_pos = result if result is not None else -1
    question = SurveyQuestion(survey_id=survey_id, position=max_pos + 1, **kwargs)
    db.add(question)
    await db.commit()
    await db.refresh(question)
    return question


async def update_question(
    db: AsyncSession, question_id: uuid.UUID, **kwargs
) -> SurveyQuestion | None:
    stmt = select(SurveyQuestion).where(SurveyQuestion.id == question_id)
    question = (await db.execute(stmt)).scalar_one_or_none()
    if not question:
        return None
    for k, v in kwargs.items():
        setattr(question, k, v)
    await db.commit()
    await db.refresh(question)
    return question


async def delete_question(db: AsyncSession, question_id: uuid.UUID) -> bool:
    stmt = select(SurveyQuestion).where(SurveyQuestion.id == question_id)
    q = (await db.execute(stmt)).scalar_one_or_none()
    if not q:
        return False
    await db.delete(q)
    await db.commit()
    return True


async def reorder_questions(
    db: AsyncSession, survey_id: uuid.UUID, question_ids: list[str]
) -> None:
    for i, qid in enumerate(question_ids):
        stmt = select(SurveyQuestion).where(
            SurveyQuestion.id == uuid.UUID(qid), SurveyQuestion.survey_id == survey_id
        )
        q = (await db.execute(stmt)).scalar_one_or_none()
        if q:
            q.position = i
    await db.commit()


async def create_submission(
    db: AsyncSession, location_id: uuid.UUID, survey_id: uuid.UUID,
    answers_json: dict, contact_id: uuid.UUID | None = None,
) -> SurveySubmission:
    sub = SurveySubmission(
        location_id=location_id,
        survey_id=survey_id,
        contact_id=contact_id,
        answers_json=answers_json,
    )
    db.add(sub)
    await db.commit()
    await db.refresh(sub)
    return sub


async def list_submissions(
    db: AsyncSession, survey_id: uuid.UUID, offset: int = 0, limit: int = 50,
) -> tuple[list[SurveySubmission], int]:
    stmt = select(SurveySubmission).where(SurveySubmission.survey_id == survey_id)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0
    stmt = stmt.order_by(SurveySubmission.submitted_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all()), total
