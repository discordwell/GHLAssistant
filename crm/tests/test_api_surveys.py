"""Test survey API routes."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from crm.models.survey import Survey, SurveyQuestion
from crm.models.location import Location


@pytest.mark.asyncio
async def test_surveys_list_page(client: AsyncClient, location: Location):
    response = await client.get(f"/loc/{location.slug}/surveys/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_surveys_new_page(client: AsyncClient, location: Location):
    response = await client.get(f"/loc/{location.slug}/surveys/new")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_surveys_create(client: AsyncClient, location: Location):
    response = await client.post(
        f"/loc/{location.slug}/surveys/",
        data={"name": "Customer Feedback"},
        follow_redirects=False,
    )
    assert response.status_code == 303


@pytest.mark.asyncio
async def test_surveys_detail(
    client: AsyncClient, db: AsyncSession, location: Location
):
    survey = Survey(
        location_id=location.id,
        name="Detail Survey",
    )
    db.add(survey)
    await db.commit()
    await db.refresh(survey)

    response = await client.get(f"/loc/{location.slug}/surveys/{survey.id}")
    assert response.status_code == 200
    assert "Detail Survey" in response.text


@pytest.mark.asyncio
async def test_surveys_add_question(
    client: AsyncClient, db: AsyncSession, location: Location
):
    survey = Survey(
        location_id=location.id,
        name="Question Survey",
    )
    db.add(survey)
    await db.commit()
    await db.refresh(survey)

    response = await client.post(
        f"/loc/{location.slug}/surveys/{survey.id}/questions",
        data={"question_text": "How was your experience?", "question_type": "text"},
        follow_redirects=False,
    )
    assert response.status_code == 303


@pytest.mark.asyncio
async def test_surveys_delete_question(
    client: AsyncClient, db: AsyncSession, location: Location
):
    survey = Survey(
        location_id=location.id,
        name="Del Question Survey",
    )
    db.add(survey)
    await db.commit()
    await db.refresh(survey)

    question = SurveyQuestion(
        survey_id=survey.id,
        question_text="To delete?",
        question_type="text",
        position=0,
    )
    db.add(question)
    await db.commit()
    await db.refresh(question)

    response = await client.post(
        f"/loc/{location.slug}/surveys/{survey.id}/questions/{question.id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 303


@pytest.mark.asyncio
async def test_surveys_delete(
    client: AsyncClient, db: AsyncSession, location: Location
):
    survey = Survey(
        location_id=location.id,
        name="To Delete Survey",
    )
    db.add(survey)
    await db.commit()
    await db.refresh(survey)

    response = await client.post(
        f"/loc/{location.slug}/surveys/{survey.id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 303


@pytest.mark.asyncio
async def test_surveys_public_get(
    client: AsyncClient, db: AsyncSession, location: Location
):
    survey = Survey(
        location_id=location.id,
        name="Public Test Survey",
        is_active=True,
    )
    db.add(survey)
    await db.commit()
    await db.refresh(survey)

    response = await client.get(f"/s/{survey.id}")
    assert response.status_code == 200
    assert "Public Test Survey" in response.text


@pytest.mark.asyncio
async def test_surveys_public_submit(
    client: AsyncClient, db: AsyncSession, location: Location
):
    survey = Survey(
        location_id=location.id,
        name="Submit Survey",
        is_active=True,
    )
    db.add(survey)
    await db.commit()
    await db.refresh(survey)

    question = SurveyQuestion(
        survey_id=survey.id,
        question_text="Rate us",
        question_type="rating",
        position=0,
    )
    db.add(question)
    await db.commit()
    await db.refresh(question)

    response = await client.post(
        f"/s/{survey.id}",
        data={str(question.id): "5"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_surveys_list_empty(client: AsyncClient, location: Location):
    response = await client.get(f"/loc/{location.slug}/surveys/")
    assert response.status_code == 200
