"""Asset export: upload local canonical assets into GHL Media Library.

This is intentionally conservative:
  - It only uploads assets with known bytes in the local blobstore.
  - Uploading is opt-in via settings (can be expensive/noisy on large accounts).
  - It records a bijection in AssetRemoteMap so subsequent exports are idempotent.
"""

from __future__ import annotations

import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..assets.blobstore import BlobStore
from ..models.asset import Asset, AssetRef, AssetRemoteMap
from ..models.location import Location
from ..schemas.sync import SyncResult


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _extract_remote_id(payload: dict[str, Any] | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    for key in ("_id", "id", "aknId", "fileId", "mediaId"):
        v = payload.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _extract_remote_url(payload: dict[str, Any] | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    for key in ("url", "publicUrl", "downloadUrl", "fileUrl", "link"):
        v = payload.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _sanitize_filename(name: str) -> str:
    # Avoid path traversal or weird separators.
    cleaned = (name or "").strip().replace("\\", "_").replace("/", "_")
    cleaned = " ".join(cleaned.split())
    if not cleaned:
        return "upload.bin"
    # Keep names reasonably sized (providers often cap around 255).
    return cleaned[:200]


def _ensure_extension(filename: str, *, content_type: str | None) -> str:
    # If filename already has an extension, keep it.
    if "." in Path(filename).name:
        return filename
    if not isinstance(content_type, str) or not content_type.strip():
        return filename
    ext = mimetypes.guess_extension(content_type.strip()) or ""
    if not ext:
        return filename
    return f"{filename}{ext}"


def _parse_csv(value: str | None) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        return []
    out: list[str] = []
    for part in value.split(","):
        p = part.strip()
        if p and p not in out:
            out.append(p)
    return out


async def _upsert_remote_map(
    db: AsyncSession,
    *,
    location: Location,
    asset_id,
    remote_id: str | None,
    remote_url: str | None,
    meta_json: dict[str, Any] | None,
    uploaded_at: datetime | None,
) -> tuple[AssetRemoteMap, bool]:
    stmt = select(AssetRemoteMap).where(
        AssetRemoteMap.asset_id == asset_id,
        AssetRemoteMap.target_system == "ghl",
        AssetRemoteMap.target_location_id == location.id,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        changed = False
        if remote_id and not existing.remote_id:
            existing.remote_id = remote_id
            changed = True
        if remote_url and not existing.remote_url:
            existing.remote_url = remote_url
            changed = True
        if uploaded_at and not existing.uploaded_at:
            existing.uploaded_at = uploaded_at
            changed = True
        if meta_json and not existing.meta_json:
            existing.meta_json = meta_json
            changed = True
        return existing, changed

    row = AssetRemoteMap(
        asset_id=asset_id,
        target_system="ghl",
        target_location_id=location.id,
        remote_id=remote_id,
        remote_url=remote_url,
        uploaded_at=uploaded_at,
        meta_json=meta_json,
    )
    db.add(row)
    await db.flush()
    return row, True


async def export_assets(
    db: AsyncSession,
    location: Location,
    ghl,
    *,
    blobstore_dir: str,
    limit: int = 50,
    sources_csv: str | None = None,
) -> SyncResult:
    """Upload selected canonical assets to GHL Media Library and persist remote maps."""
    result = SyncResult()
    now = _utcnow()

    # 1) Bijection: assets that already came from GHL media library should map back
    # to their remote ids/urls (no upload needed).
    stmt = select(AssetRef).where(
        AssetRef.location_id == location.id,
        AssetRef.usage == "media_library",
        AssetRef.asset_id.is_not(None),
        AssetRef.remote_entity_id.is_not(None),
    )
    refs = list((await db.execute(stmt)).scalars().all())
    for ref in refs:
        try:
            remote_id = ref.remote_entity_id
            remote_url = ref.original_url
            _, changed = await _upsert_remote_map(
                db,
                location=location,
                asset_id=ref.asset_id,
                remote_id=remote_id,
                remote_url=remote_url,
                meta_json={"source": "media_library_ref"},
                uploaded_at=ref.last_seen_at or now,
            )
            if changed:
                result.updated += 1
        except Exception as exc:
            result.errors.append(f"AssetRemoteMap upsert (media library ref) failed: {exc}")

    # 2) Upload: requires token-id captured from browser traffic.
    token_id = getattr(getattr(ghl, "config", None), "token_id", None)
    if not isinstance(token_id, str) or not token_id.strip():
        await db.commit()
        result.errors.append(
            "Assets upload skipped: GHL client has no token_id. "
            "Run `python -m maxlevel browser capture --profile <profile> --duration 120` "
            "and ensure you load that session when exporting."
        )
        return result

    sources = _parse_csv(sources_csv)
    if not sources:
        sources = ["funnel_page_data_uri", "funnel_page_html"]

    # Conservative selection: only upload assets with allowed sources.
    stmt_assets = (
        select(Asset)
        .where(Asset.location_id == location.id, Asset.source.in_(sources))
        .order_by(Asset.created_at.asc())
    )
    assets = list((await db.execute(stmt_assets)).scalars().all())

    blobstore = BlobStore(blobstore_dir)
    uploaded = 0
    for asset in assets:
        if limit > 0 and uploaded >= int(limit):
            result.skipped += max(0, len(assets) - uploaded)
            break

        # Skip if already mapped.
        stmt_map = select(AssetRemoteMap).where(
            AssetRemoteMap.asset_id == asset.id,
            AssetRemoteMap.target_system == "ghl",
            AssetRemoteMap.target_location_id == location.id,
        )
        existing_map = (await db.execute(stmt_map)).scalar_one_or_none()
        if existing_map and (existing_map.remote_id or existing_map.remote_url):
            result.skipped += 1
            continue

        blob_path = blobstore.path_for_sha256(asset.sha256)
        if not blob_path.is_file():
            result.errors.append(f"Asset {asset.sha256}: missing blob bytes at {blob_path}")
            continue

        filename = _sanitize_filename(asset.original_filename or f"{asset.sha256}")
        filename = _ensure_extension(filename, content_type=asset.content_type)

        try:
            verified = await ghl.media_library.upload_path(
                path=blob_path,
                filename=filename,
                content_type=asset.content_type,
                location_id=location.ghl_location_id,
            )
        except Exception as exc:
            result.errors.append(f"Asset upload failed ({asset.sha256}): {exc}")
            continue

        remote_id = _extract_remote_id(verified)
        remote_url = _extract_remote_url(verified)
        try:
            await _upsert_remote_map(
                db,
                location=location,
                asset_id=asset.id,
                remote_id=remote_id,
                remote_url=remote_url,
                meta_json={"source": "upload", "verified": verified},
                uploaded_at=now,
            )
            result.created += 1
            uploaded += 1
        except Exception as exc:
            result.errors.append(f"AssetRemoteMap upsert (upload) failed ({asset.sha256}): {exc}")

    await db.commit()
    return result
