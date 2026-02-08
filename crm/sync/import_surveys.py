"""Import surveys and submissions from GHL."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.survey import Survey, SurveyQuestion, SurveySubmission
from ..models.contact import Contact
from ..models.location import Location
from ..schemas.sync import SyncResult


def _to_dict(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    return {}


def _extract_survey_payload(detail: dict) -> dict:
    if not detail:
        return {}
    if isinstance(detail.get("survey"), dict):
        return detail["survey"]
    return detail


def _extract_questions(survey_payload: dict, list_payload: dict) -> list[dict]:
    for source in (survey_payload, list_payload):
        src = _to_dict(source)
        for key in ("questions", "surveyQuestions", "fields"):
            value = src.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _build_options_json(question_data: dict) -> dict | None:
    options: dict = {}

    raw_options = question_data.get("options", question_data.get("choices"))
    if isinstance(raw_options, dict):
        options.update(raw_options)
    elif isinstance(raw_options, list):
        options["options"] = raw_options

    ghl_question_id = question_data.get("id", question_data.get("_id"))
    if isinstance(ghl_question_id, str) and ghl_question_id:
        options["_ghl_question_id"] = ghl_question_id

    options["_ghl_raw"] = question_data
    return options if options else None


async def import_surveys(
    db: AsyncSession, location: Location, surveys_data: list[dict],
    submissions_by_survey: dict[str, list[dict]] | None = None,
    details_by_survey: dict[str, dict] | None = None,
) -> SyncResult:
    """Import surveys and submissions from GHL."""
    result = SyncResult()
    submissions_by_survey = submissions_by_survey or {}
    details_by_survey = details_by_survey or {}

    for s_data in surveys_data:
        ghl_id = s_data.get("id", s_data.get("_id", ""))
        name = s_data.get("name", "")
        if not name:
            continue

        detail_payload = _extract_survey_payload(_to_dict(details_by_survey.get(ghl_id)))
        description = detail_payload.get("description", s_data.get("description"))
        is_active = detail_payload.get("isActive", detail_payload.get("active", True))
        if not isinstance(is_active, bool):
            is_active = bool(is_active)

        stmt = select(Survey).where(
            Survey.location_id == location.id, Survey.ghl_id == ghl_id
        )
        survey = (await db.execute(stmt)).scalar_one_or_none()

        if survey:
            survey.name = name
            survey.description = description
            survey.is_active = is_active
            survey.last_synced_at = datetime.now(timezone.utc)
            result.updated += 1
        else:
            survey = Survey(
                location_id=location.id, name=name,
                description=description, is_active=is_active,
                ghl_id=ghl_id, ghl_location_id=location.ghl_location_id,
                last_synced_at=datetime.now(timezone.utc),
            )
            db.add(survey)
            await db.flush()
            result.created += 1

        # Import/update questions
        questions_data = _extract_questions(detail_payload, _to_dict(s_data))
        for i, question_data in enumerate(questions_data):
            question_text = (
                question_data.get("question")
                or question_data.get("questionText")
                or question_data.get("label")
                or f"Question {i + 1}"
            )
            question_type = str(
                question_data.get("questionType", question_data.get("type", "text"))
            ).lower()
            is_required = bool(
                question_data.get("isRequired", question_data.get("required", False))
            )
            options_json = _build_options_json(question_data)

            stmt = select(SurveyQuestion).where(
                SurveyQuestion.survey_id == survey.id,
                SurveyQuestion.position == i,
            )
            question = (await db.execute(stmt)).scalar_one_or_none()

            if question:
                question.question_text = question_text
                question.question_type = question_type
                question.is_required = is_required
                question.options_json = options_json
            else:
                question = SurveyQuestion(
                    survey_id=survey.id,
                    question_text=question_text,
                    question_type=question_type,
                    is_required=is_required,
                    options_json=options_json,
                    position=i,
                )
                db.add(question)

        # Import submissions (dedup by submitted_at + survey_id)
        existing_stmt = select(SurveySubmission).where(SurveySubmission.survey_id == survey.id)
        existing_submissions = list((await db.execute(existing_stmt)).scalars().all())
        existing_ghl_submission_ids = {
            sub.answers_json.get("_ghl_submission_id")
            for sub in existing_submissions
            if isinstance(sub.answers_json, dict) and sub.answers_json.get("_ghl_submission_id")
        }

        for sub_data in submissions_by_survey.get(ghl_id, []):
            sub_ghl_id = sub_data.get("id", sub_data.get("_id"))
            if isinstance(sub_ghl_id, str) and sub_ghl_id in existing_ghl_submission_ids:
                continue

            submitted_at_raw = sub_data.get("createdAt", sub_data.get("submittedAt"))
            if submitted_at_raw:
                try:
                    parsed_ts = datetime.fromisoformat(submitted_at_raw.replace("Z", "+00:00"))
                    dup_stmt = select(SurveySubmission).where(
                        SurveySubmission.survey_id == survey.id,
                        SurveySubmission.submitted_at == parsed_ts,
                    )
                    if (await db.execute(dup_stmt)).scalar_one_or_none():
                        continue
                except (ValueError, AttributeError):
                    pass

            answers_data = sub_data.get("data", sub_data.get("others", {}))
            if not isinstance(answers_data, dict):
                answers_data = {"value": answers_data}
            else:
                answers_data = dict(answers_data)

            raw_submission = copy.deepcopy(sub_data)

            if isinstance(sub_ghl_id, str) and sub_ghl_id:
                answers_data["_ghl_submission_id"] = sub_ghl_id
            answers_data["_ghl_raw"] = raw_submission

            contact_id = None
            ghl_contact_id = sub_data.get("contactId")
            if isinstance(ghl_contact_id, str) and ghl_contact_id:
                contact_stmt = select(Contact).where(
                    Contact.location_id == location.id,
                    Contact.ghl_id == ghl_contact_id,
                )
                contact = (await db.execute(contact_stmt)).scalar_one_or_none()
                if contact:
                    contact_id = contact.id

            sub = SurveySubmission(
                location_id=location.id,
                survey_id=survey.id,
                contact_id=contact_id,
                answers_json=answers_data,
            )
            submitted_at = sub_data.get("createdAt", sub_data.get("submittedAt"))
            if submitted_at:
                try:
                    sub.submitted_at = datetime.fromisoformat(
                        submitted_at.replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    pass
            db.add(sub)
            if isinstance(sub_ghl_id, str) and sub_ghl_id:
                existing_ghl_submission_ids.add(sub_ghl_id)

    await db.commit()
    return result
