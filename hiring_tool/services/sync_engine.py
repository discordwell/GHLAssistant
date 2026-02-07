"""Bidirectional GHL sync engine."""

from __future__ import annotations

import json
import logging
from datetime import datetime

from sqlmodel import Session, select

from ..config import settings
from ..models import Candidate, CandidateActivity

logger = logging.getLogger(__name__)

# Field mapping: local -> GHL custom field keys
FIELD_MAP = {
    "source": "contact.referral_source",
    "desired_salary": "contact.desired_salary",
    "available_start": "contact.available_start_date",
    "resume_url": "contact.resume_url",
    "score": "contact.interview_score",
}

# Tag mappings
STATUS_TAG_MAP = {
    "active": "applicant",
    "hired": "hired",
    "rejected": "rejected",
}


def _candidate_to_ghl_contact(candidate: Candidate) -> dict:
    """Map local candidate fields to GHL contact payload."""
    data: dict = {}
    if candidate.first_name:
        data["firstName"] = candidate.first_name
    if candidate.last_name:
        data["lastName"] = candidate.last_name
    if candidate.email:
        data["email"] = candidate.email
    if candidate.phone:
        data["phone"] = candidate.phone

    custom_fields = {}
    if candidate.source:
        custom_fields["referral_source"] = candidate.source
    if candidate.desired_salary is not None:
        custom_fields["desired_salary"] = str(candidate.desired_salary)
    if candidate.available_start:
        custom_fields["available_start_date"] = candidate.available_start.isoformat()
    if candidate.resume_url:
        custom_fields["resume_url"] = candidate.resume_url
    if candidate.score is not None:
        custom_fields["interview_score"] = str(candidate.score)

    if custom_fields:
        data["customFields"] = custom_fields

    return data


def _ghl_contact_to_candidate_fields(contact: dict) -> dict:
    """Map GHL contact data to local candidate fields."""
    fields = {
        "first_name": contact.get("firstName", ""),
        "last_name": contact.get("lastName", ""),
        "email": contact.get("email"),
        "phone": contact.get("phone"),
    }

    custom = contact.get("customFields", {})
    if isinstance(custom, list):
        cf = {}
        for item in custom:
            cf[item.get("key", "")] = item.get("value")
        custom = cf

    if custom.get("referral_source"):
        fields["source"] = custom["referral_source"]
    if custom.get("desired_salary"):
        try:
            fields["desired_salary"] = float(custom["desired_salary"])
        except (ValueError, TypeError):
            pass
    if custom.get("resume_url"):
        fields["resume_url"] = custom["resume_url"]
    if custom.get("interview_score"):
        try:
            fields["score"] = float(custom["interview_score"])
        except (ValueError, TypeError):
            pass

    return fields


async def push_all_to_ghl(db: Session) -> dict:
    """Push all local candidates to GHL."""
    try:
        from maxlevel.api import GHLClient
    except ImportError:
        return {"synced": 0, "total": 0, "message": "GHL client not available"}

    candidates = db.exec(select(Candidate).where(Candidate.status != "withdrawn")).all()

    synced = 0
    errors = []

    try:
        async with GHLClient.from_session() as ghl:
            # Find the hiring pipeline and stage IDs
            pipelines_resp = await ghl.opportunities.pipelines()
            pipeline = None
            stage_map: dict[str, str] = {}

            for p in pipelines_resp.get("pipelines", []):
                if p.get("name") == settings.ghl_pipeline_name:
                    pipeline = p
                    for s in p.get("stages", []):
                        stage_map[s["name"]] = s["id"]
                    break

            for candidate in candidates:
                try:
                    contact_data = _candidate_to_ghl_contact(candidate)

                    if not candidate.ghl_contact_id:
                        # Create new contact
                        tags = ["applicant"]
                        if candidate.status == "hired":
                            tags.append("hired")
                        elif candidate.status == "rejected":
                            tags.append("rejected")

                        result = await ghl.contacts.create(
                            first_name=candidate.first_name,
                            last_name=candidate.last_name,
                            email=candidate.email,
                            phone=candidate.phone,
                            tags=tags,
                            custom_fields=contact_data.get("customFields"),
                        )
                        contact = result.get("contact", {})
                        candidate.ghl_contact_id = contact.get("id")

                        # Create opportunity if pipeline exists
                        if pipeline and candidate.stage in stage_map:
                            opp_result = await ghl.opportunities.create(
                                pipeline_id=pipeline["id"],
                                stage_id=stage_map[candidate.stage],
                                contact_id=candidate.ghl_contact_id,
                                name=f"{candidate.first_name} {candidate.last_name}",
                            )
                            opp = opp_result.get("opportunity", {})
                            candidate.ghl_opportunity_id = opp.get("id")
                    else:
                        # Update existing contact
                        await ghl.contacts.update(
                            candidate.ghl_contact_id,
                            **contact_data,
                        )

                        # Move stage if opportunity exists
                        if candidate.ghl_opportunity_id and candidate.stage in stage_map:
                            await ghl.opportunities.move_stage(
                                candidate.ghl_opportunity_id,
                                stage_map[candidate.stage],
                            )

                        # Handle terminal states
                        if candidate.status == "hired" and candidate.ghl_opportunity_id:
                            await ghl.opportunities.mark_won(candidate.ghl_opportunity_id)
                            await ghl.contacts.add_tag(candidate.ghl_contact_id, "hired")
                        elif candidate.status == "rejected" and candidate.ghl_opportunity_id:
                            await ghl.opportunities.mark_lost(candidate.ghl_opportunity_id)
                            await ghl.contacts.add_tag(candidate.ghl_contact_id, "rejected")

                    candidate.last_synced_at = datetime.utcnow()
                    activity = CandidateActivity(
                        candidate_id=candidate.id,
                        activity_type="synced",
                        description="Pushed to GHL",
                        created_by="ghl_sync",
                    )
                    db.add(activity)
                    synced += 1

                except Exception as e:
                    errors.append(f"{candidate.first_name} {candidate.last_name}: {e}")
                    logger.warning("Failed to push candidate %s: %s", candidate.id, e)

            db.commit()

    except Exception as e:
        return {"synced": synced, "total": len(candidates), "message": f"Sync error: {e}"}

    msg = f"Pushed {synced}/{len(candidates)} candidates"
    if errors:
        msg += f" ({len(errors)} errors)"

    return {"synced": synced, "total": len(candidates), "message": msg}


async def pull_from_ghl(db: Session) -> dict:
    """Pull candidates from GHL hiring pipeline."""
    try:
        from maxlevel.api import GHLClient
    except ImportError:
        return {"synced": 0, "total": 0, "message": "GHL client not available"}

    synced = 0
    total = 0

    try:
        async with GHLClient.from_session() as ghl:
            pipelines_resp = await ghl.opportunities.pipelines()
            pipeline = None
            stage_map: dict[str, str] = {}  # id -> name

            for p in pipelines_resp.get("pipelines", []):
                if p.get("name") == settings.ghl_pipeline_name:
                    pipeline = p
                    for s in p.get("stages", []):
                        stage_map[s["id"]] = s["name"]
                    break

            if not pipeline:
                return {"synced": 0, "total": 0, "message": "Hiring Pipeline not found in GHL"}

            opps_resp = await ghl.opportunities.list(pipeline_id=pipeline["id"], limit=100)
            opportunities = opps_resp.get("opportunities", [])
            total = len(opportunities)

            for opp in opportunities:
                contact_id = opp.get("contactId") or opp.get("contact", {}).get("id")
                if not contact_id:
                    continue

                # Get full contact data
                contact_resp = await ghl.contacts.get(contact_id)
                contact = contact_resp.get("contact", {})

                fields = _ghl_contact_to_candidate_fields(contact)

                # Match to local candidate
                existing = db.exec(
                    select(Candidate).where(Candidate.ghl_contact_id == contact_id)
                ).first()

                if not existing and fields.get("email"):
                    existing = db.exec(
                        select(Candidate).where(Candidate.email == fields["email"])
                    ).first()

                stage_id = opp.get("pipelineStageId")
                stage_name = stage_map.get(stage_id, "Applied")

                if existing:
                    # Update if GHL is newer
                    ghl_updated = opp.get("updatedAt")
                    if ghl_updated and existing.last_synced_at:
                        try:
                            ghl_dt = datetime.fromisoformat(ghl_updated.replace("Z", "+00:00"))
                            if ghl_dt.replace(tzinfo=None) <= existing.last_synced_at:
                                continue
                        except (ValueError, TypeError):
                            pass

                    for key, val in fields.items():
                        if val is not None:
                            setattr(existing, key, val)
                    existing.ghl_contact_id = contact_id
                    existing.ghl_opportunity_id = opp.get("id")
                    existing.stage = stage_name
                    existing.last_synced_at = datetime.utcnow()

                    activity = CandidateActivity(
                        candidate_id=existing.id,
                        activity_type="synced",
                        description="Updated from GHL",
                        created_by="ghl_sync",
                    )
                    db.add(activity)
                else:
                    # Create new local candidate
                    candidate = Candidate(
                        ghl_contact_id=contact_id,
                        ghl_opportunity_id=opp.get("id"),
                        first_name=fields.get("first_name", ""),
                        last_name=fields.get("last_name", ""),
                        email=fields.get("email"),
                        phone=fields.get("phone"),
                        stage=stage_name,
                        source=fields.get("source"),
                        desired_salary=fields.get("desired_salary"),
                        resume_url=fields.get("resume_url"),
                        score=fields.get("score"),
                        last_synced_at=datetime.utcnow(),
                    )
                    db.add(candidate)
                    db.commit()
                    db.refresh(candidate)

                    activity = CandidateActivity(
                        candidate_id=candidate.id,
                        activity_type="synced",
                        description="Synced from GHL",
                        created_by="ghl_sync",
                    )
                    db.add(activity)

                synced += 1

            db.commit()

    except Exception as e:
        return {"synced": synced, "total": total, "message": f"Pull error: {e}"}

    return {"synced": synced, "total": total, "message": f"Pulled {synced}/{total} from GHL"}
