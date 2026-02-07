"""Import surveys and submissions from GHL."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.survey import Survey, SurveyQuestion, SurveySubmission
from ..models.location import Location
from ..schemas.sync import SyncResult


async def import_surveys(
    db: AsyncSession, location: Location, surveys_data: list[dict],
    submissions_by_survey: dict[str, list[dict]] | None = None,
) -> SyncResult:
    """Import surveys and submissions from GHL."""
    result = SyncResult()
    submissions_by_survey = submissions_by_survey or {}

    for s_data in surveys_data:
        ghl_id = s_data.get("id", s_data.get("_id", ""))
        name = s_data.get("name", "")
        if not name:
            continue

        stmt = select(Survey).where(
            Survey.location_id == location.id, Survey.ghl_id == ghl_id
        )
        survey = (await db.execute(stmt)).scalar_one_or_none()

        if survey:
            survey.name = name
            survey.last_synced_at = datetime.now(timezone.utc)
            result.updated += 1
        else:
            survey = Survey(
                location_id=location.id, name=name,
                ghl_id=ghl_id, ghl_location_id=location.ghl_location_id,
                last_synced_at=datetime.now(timezone.utc),
            )
            db.add(survey)
            await db.flush()
            result.created += 1

        # Import submissions (dedup by submitted_at + survey_id)
        for sub_data in submissions_by_survey.get(ghl_id, []):
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
            sub = SurveySubmission(
                location_id=location.id,
                survey_id=survey.id,
                answers_json=sub_data.get("data", sub_data.get("others", {})),
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

    await db.commit()
    return result
