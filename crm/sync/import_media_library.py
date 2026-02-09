"""Media library discovery import (enqueue/download assets)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..assets.hashes import asset_ref_identity_sha256
from ..assets.jobs import enqueue_download_job
from ..models.asset import AssetRef
from ..models.location import Location
from ..schemas.sync import SyncResult
from .raw_store import upsert_raw_entity


def _extract_id(item: dict[str, Any]) -> str:
    for key in ("id", "_id", "fileId", "mediaId"):
        value = item.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _extract_url(item: dict[str, Any]) -> str:
    for key in ("url", "fileUrl", "publicUrl", "downloadUrl", "link"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    # Some shapes embed nested file objects.
    for key in ("file", "media", "asset"):
        nested = item.get(key)
        if isinstance(nested, dict):
            url = _extract_url(nested)
            if url:
                return url

    return ""


def _extract_filename(item: dict[str, Any]) -> str | None:
    for key in ("name", "fileName", "filename", "originalName", "original_filename"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _extract_content_type(item: dict[str, Any]) -> str | None:
    for key in ("contentType", "mimeType", "content_type"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


async def import_media_library(
    db: AsyncSession,
    *,
    location: Location,
    items: list[dict[str, Any]],
    source: str = "api",
) -> SyncResult:
    """Upsert raw payloads + enqueue download jobs for media library files."""
    result = SyncResult()
    now = datetime.now(timezone.utc)

    for item in items:
        if not isinstance(item, dict):
            continue

        remote_id = _extract_id(item)
        if not remote_id:
            continue

        await upsert_raw_entity(
            db,
            location=location,
            entity_type="media_library_file",
            ghl_id=remote_id,
            payload=item,
            source=source,
        )

        url = _extract_url(item)
        filename = _extract_filename(item)
        content_type = _extract_content_type(item)

        # Upsert AssetRef (idempotent across repeated imports).
        identity = asset_ref_identity_sha256(
            entity_type="media_library_file",
            entity_id=None,
            remote_entity_id=remote_id,
            field_path="url",
            usage="media_library",
            original_url=(url or None),
        )
        stmt = select(AssetRef).where(
            AssetRef.location_id == location.id,
            AssetRef.identity_sha256 == identity,
        )
        ref = (await db.execute(stmt)).scalar_one_or_none()

        if ref:
            # Preserve any new metadata but avoid churning.
            ref.last_seen_at = now
            if not ref.meta_json:
                ref.meta_json = {}
            if isinstance(ref.meta_json, dict):
                ref.meta_json.setdefault("filename", filename)
                ref.meta_json.setdefault("content_type", content_type)
            result.updated += 1
        else:
            ref = AssetRef(
                location_id=location.id,
                identity_sha256=identity,
                asset_id=None,
                entity_type="media_library_file",
                entity_id=None,
                remote_entity_id=remote_id,
                field_path="url",
                usage="media_library",
                original_url=(url or None),
                last_seen_at=now,
                meta_json={"filename": filename, "content_type": content_type},
            )
            db.add(ref)
            result.created += 1

        await db.flush()

        if url:
            job = await enqueue_download_job(
                db,
                location_id=location.id,
                url=url,
                asset_ref_id=ref.id,
                meta_json={
                    "source": "media_library",
                    "remote_id": remote_id,
                    "filename": filename,
                    "content_type": content_type,
                },
            )
            if job and job.id:
                # Count only newly-created jobs; enqueue_download_job is idempotent but
                # doesn't expose creation status. We'll treat "missing id" as not created.
                # (Flush will assign id for new rows.)
                pass

    await db.commit()
    return result
