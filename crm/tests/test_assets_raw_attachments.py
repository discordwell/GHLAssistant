"""Tests for discovering asset references from raw conversation/message payloads."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from crm.models.asset import AssetJob, AssetRef
from crm.models.conversation import Conversation, Message
from crm.models.ghl_raw import GHLRawEntity
from crm.models.location import Location
from crm.sync.import_assets import discover_conversation_message_attachments_from_raw


@pytest.mark.asyncio
async def test_discover_message_attachments_from_raw_payloads(db: AsyncSession, location: Location):
    conv = Conversation(location_id=location.id, ghl_id="conv_1", channel="sms")
    db.add(conv)
    await db.flush()

    msg = Message(
        location_id=location.id,
        conversation_id=conv.id,
        contact_id=None,
        direction="inbound",
        channel="sms",
        body="Hello",
        provider_id="msg_1",
        status="received",
    )
    db.add(msg)
    await db.flush()

    raw_msg = GHLRawEntity(
        location_id=location.id,
        entity_type="message",
        ghl_id="msg_1",
        ghl_location_id=location.ghl_location_id,
        payload_json={
            "id": "msg_1",
            "attachments": [
                {
                    "url": "https://example.com/a.png",
                    "filename": "a.png",
                    "contentType": "image/png",
                    "size": 123,
                },
                {"fileUrl": "https://example.com/b.pdf", "name": "b.pdf"},
            ],
        },
        source="api",
    )
    db.add(raw_msg)
    await db.commit()

    r1 = await discover_conversation_message_attachments_from_raw(
        db, location, include_conversations=False, include_messages=True
    )
    assert r1.refs_created == 2
    assert r1.jobs_created == 2
    assert r1.errors == []

    refs = list(
        (await db.execute(select(AssetRef).where(AssetRef.location_id == location.id)))
        .scalars()
        .all()
    )
    assert len(refs) == 2
    assert all(ref.entity_type == "message_raw" for ref in refs)
    assert all(ref.remote_entity_id == "msg_1" for ref in refs)
    assert all(ref.entity_id == msg.id for ref in refs)

    field_paths = sorted(ref.field_path for ref in refs)
    assert field_paths == ["/attachments/0/url", "/attachments/1/fileUrl"]

    urls = sorted(ref.original_url for ref in refs)
    assert urls == ["https://example.com/a.png", "https://example.com/b.pdf"]

    jobs = list(
        (
            await db.execute(
                select(AssetJob).where(
                    AssetJob.location_id == location.id,
                    AssetJob.job_type == "download",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(jobs) == 2
    assert sorted(j.url for j in jobs) == urls

    # Idempotency: re-running should not create duplicates.
    r2 = await discover_conversation_message_attachments_from_raw(
        db, location, include_conversations=False, include_messages=True
    )
    assert r2.refs_created == 0
    assert r2.jobs_created == 0

