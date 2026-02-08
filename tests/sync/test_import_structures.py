"""Regression tests for structural sync mappings (forms/surveys/campaigns/funnels)."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from crm.models.base import Base
from crm.models.campaign import Campaign, CampaignStep
from crm.models.contact import Contact
from crm.models.form import Form, FormField, FormSubmission
from crm.models.funnel import Funnel, FunnelPage
from crm.models.location import Location
from crm.models.survey import Survey, SurveyQuestion, SurveySubmission
from crm.sync.import_campaigns import import_campaigns
from crm.sync.import_forms import import_forms
from crm.sync.import_funnels import import_funnels
from crm.sync.import_surveys import import_surveys


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def location(db: AsyncSession) -> Location:
    loc = Location(
        id=uuid.uuid4(),
        name="Test Location",
        slug="test-location",
        timezone="UTC",
        ghl_location_id="ghl_loc_123",
    )
    db.add(loc)
    await db.commit()
    await db.refresh(loc)
    return loc


@pytest.mark.asyncio
async def test_import_forms_maps_fields_and_submission_contact(db: AsyncSession, location: Location):
    contact = Contact(
        location_id=location.id,
        first_name="Jane",
        email="jane@example.com",
        ghl_id="ghl_contact_1",
    )
    db.add(contact)
    await db.commit()

    forms_data = [{"id": "ghl_form_1", "name": "Lead Form"}]
    details_by_form = {
        "ghl_form_1": {
            "form": {
                "description": "Capture new leads",
                "isActive": True,
                "fields": [
                    {
                        "id": "ghl_field_1",
                        "label": "Email",
                        "type": "email",
                        "required": True,
                    }
                ],
            }
        }
    }
    submissions_by_form = {
        "ghl_form_1": [
            {
                "id": "ghl_sub_1",
                "contactId": "ghl_contact_1",
                "createdAt": "2025-01-01T00:00:00Z",
                "data": {"Email": "jane@example.com"},
            }
        ]
    }

    await import_forms(
        db,
        location,
        forms_data,
        submissions_by_form=submissions_by_form,
        details_by_form=details_by_form,
    )
    await import_forms(
        db,
        location,
        forms_data,
        submissions_by_form=submissions_by_form,
        details_by_form=details_by_form,
    )

    form = (await db.execute(select(Form))).scalar_one()
    field = (await db.execute(select(FormField))).scalar_one()
    submission_rows = list((await db.execute(select(FormSubmission))).scalars().all())

    assert form.description == "Capture new leads"
    assert field.label == "Email"
    assert field.field_type == "email"
    assert field.is_required is True
    assert isinstance(field.options_json, dict)
    assert field.options_json.get("_ghl_field_id") == "ghl_field_1"
    assert len(submission_rows) == 1
    assert submission_rows[0].contact_id == contact.id
    assert isinstance(submission_rows[0].data_json, dict)
    assert submission_rows[0].data_json.get("_ghl_submission_id") == "ghl_sub_1"


@pytest.mark.asyncio
async def test_import_surveys_maps_questions_and_submission_contact(db: AsyncSession, location: Location):
    contact = Contact(
        location_id=location.id,
        first_name="Alex",
        email="alex@example.com",
        ghl_id="ghl_contact_2",
    )
    db.add(contact)
    await db.commit()

    surveys_data = [{"id": "ghl_survey_1", "name": "CSAT"}]
    details_by_survey = {
        "ghl_survey_1": {
            "survey": {
                "description": "Customer satisfaction",
                "isActive": True,
                "questions": [
                    {
                        "id": "ghl_question_1",
                        "questionText": "How satisfied are you?",
                        "type": "rating",
                        "required": True,
                    }
                ],
            }
        }
    }
    submissions_by_survey = {
        "ghl_survey_1": [
            {
                "id": "ghl_s_sub_1",
                "contactId": "ghl_contact_2",
                "createdAt": "2025-01-01T00:01:00Z",
                "data": {"How satisfied are you?": "5"},
            }
        ]
    }

    await import_surveys(
        db,
        location,
        surveys_data,
        submissions_by_survey=submissions_by_survey,
        details_by_survey=details_by_survey,
    )

    survey = (await db.execute(select(Survey))).scalar_one()
    question = (await db.execute(select(SurveyQuestion))).scalar_one()
    submission = (await db.execute(select(SurveySubmission))).scalar_one()

    assert survey.description == "Customer satisfaction"
    assert question.question_type == "rating"
    assert question.is_required is True
    assert isinstance(question.options_json, dict)
    assert question.options_json.get("_ghl_question_id") == "ghl_question_1"
    assert submission.contact_id == contact.id
    assert isinstance(submission.answers_json, dict)
    assert submission.answers_json.get("_ghl_submission_id") == "ghl_s_sub_1"


@pytest.mark.asyncio
async def test_import_campaigns_maps_steps(db: AsyncSession, location: Location):
    campaigns_data = [{"id": "ghl_campaign_1", "name": "Welcome Campaign"}]
    details_by_campaign = {
        "ghl_campaign_1": {
            "campaign": {
                "description": "3-step onboarding",
                "status": "active",
                "steps": [
                    {
                        "type": "email",
                        "subject": "Welcome",
                        "body": "Hello there!",
                        "delayMinutes": 0,
                    },
                    {
                        "type": "sms",
                        "message": "Checking in",
                        "delay": {"value": 2, "unit": "hours"},
                    },
                ],
            }
        }
    }

    await import_campaigns(
        db,
        location,
        campaigns_data,
        details_by_campaign=details_by_campaign,
    )

    campaign = (await db.execute(select(Campaign))).scalar_one()
    steps = list((await db.execute(select(CampaignStep).order_by(CampaignStep.position))).scalars().all())

    assert campaign.description == "3-step onboarding"
    assert campaign.status == "active"
    assert len(steps) == 2
    assert steps[0].step_type == "email"
    assert steps[0].subject == "Welcome"
    assert steps[1].step_type == "sms"
    assert steps[1].delay_minutes == 120


@pytest.mark.asyncio
async def test_import_funnels_maps_details_and_page_details(db: AsyncSession, location: Location):
    funnels_data = [{"id": "ghl_funnel_1", "name": "Main Funnel"}]
    details_by_funnel = {
        "ghl_funnel_1": {
            "funnel": {"description": "Core sales funnel", "isPublished": True}
        }
    }
    pages_by_funnel = {
        "ghl_funnel_1": [
            {"id": "ghl_page_1", "name": "Landing", "path": "landing"},
        ]
    }
    page_details_by_funnel = {
        "ghl_funnel_1": {
            "ghl_page_1": {
                "page": {"html": "<h1>Landing</h1>", "isPublished": True}
            }
        }
    }

    await import_funnels(
        db,
        location,
        funnels_data,
        pages_by_funnel=pages_by_funnel,
        details_by_funnel=details_by_funnel,
        page_details_by_funnel=page_details_by_funnel,
    )

    funnel = (await db.execute(select(Funnel))).scalar_one()
    page = (await db.execute(select(FunnelPage))).scalar_one()

    assert funnel.description == "Core sales funnel"
    assert funnel.is_published is True
    assert page.url_slug == "landing"
    assert page.content_html == "<h1>Landing</h1>"
    assert page.is_published is True
