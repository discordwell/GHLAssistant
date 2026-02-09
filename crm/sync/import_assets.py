"""Asset discovery for import (F2): find references and queue downloads.

This module intentionally focuses on discovery + queueing. Download/upload
workers can be implemented separately so main sync remains fast.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..assets.blobstore import BlobStore
from ..assets.hashes import asset_ref_identity_sha256, url_sha256 as url_sha256_hex
from ..assets.html import iter_html_asset_candidates, parse_data_uri, sha256_hex
from ..models.asset import Asset, AssetJob, AssetRef
from ..models.funnel import Funnel, FunnelPage
from ..models.conversation import Conversation, Message
from ..models.ghl_raw import GHLRawEntity
from ..models.location import Location


@dataclass
class AssetDiscoveryResult:
    assets_created: int = 0
    assets_updated: int = 0
    refs_created: int = 0
    refs_updated: int = 0
    jobs_created: int = 0
    jobs_updated: int = 0
    errors: list[str] = field(default_factory=list)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _upsert_asset(
    db: AsyncSession,
    *,
    location_id: uuid.UUID,
    sha256: str,
    size_bytes: int,
    content_type: str | None,
    original_url: str | None,
    original_filename: str | None = None,
    source: str,
    meta_json: dict | None,
) -> tuple[Asset, bool]:
    stmt = select(Asset).where(Asset.location_id == location_id, Asset.sha256 == sha256)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    now = _now()
    if existing:
        existing.last_seen_at = now
        if not existing.content_type and content_type:
            existing.content_type = content_type
        if not existing.original_url and original_url:
            existing.original_url = original_url
        if not existing.source and source:
            existing.source = source
        if existing.size_bytes != size_bytes and size_bytes:
            # Theoretically impossible for sha256, but keep last seen metadata truthful.
            existing.size_bytes = size_bytes
        if meta_json and not existing.meta_json:
            existing.meta_json = meta_json
        return existing, False

    asset = Asset(
        location_id=location_id,
        sha256=sha256,
        size_bytes=size_bytes,
        content_type=content_type,
        original_filename=original_filename,
        original_url=original_url,
        source=source,
        last_seen_at=now,
        meta_json=meta_json,
    )
    db.add(asset)
    await db.flush()
    return asset, True


async def _upsert_asset_ref(
    db: AsyncSession,
    *,
    location_id: uuid.UUID,
    asset_id: uuid.UUID | None,
    entity_type: str,
    entity_id: uuid.UUID | None,
    remote_entity_id: str | None,
    field_path: str,
    usage: str | None,
    original_url: str | None,
    meta_json: dict | None,
) -> tuple[AssetRef, bool]:
    identity = asset_ref_identity_sha256(
        entity_type=entity_type,
        entity_id=entity_id,
        remote_entity_id=remote_entity_id,
        field_path=field_path,
        usage=usage,
        original_url=original_url,
    )
    stmt = select(AssetRef).where(
        AssetRef.location_id == location_id,
        AssetRef.identity_sha256 == identity,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    now = _now()

    if existing:
        existing.last_seen_at = now
        existing.updated_at = now  # best-effort "last seen"
        if asset_id and existing.asset_id != asset_id:
            existing.asset_id = asset_id
        if meta_json and not existing.meta_json:
            existing.meta_json = meta_json
        return existing, False

    ref = AssetRef(
        location_id=location_id,
        identity_sha256=identity,
        asset_id=asset_id,
        entity_type=entity_type,
        entity_id=entity_id,
        remote_entity_id=remote_entity_id,
        field_path=field_path,
        usage=usage,
        original_url=original_url,
        last_seen_at=now,
        meta_json=meta_json,
    )
    db.add(ref)
    await db.flush()
    return ref, True


async def _enqueue_download_job(
    db: AsyncSession,
    *,
    location_id: uuid.UUID,
    url: str,
    asset_ref_id: uuid.UUID | None = None,
    priority: int = 0,
    meta_json: dict | None = None,
) -> tuple[AssetJob, bool]:
    url_key = url_sha256_hex(url)
    stmt = select(AssetJob).where(
        AssetJob.location_id == location_id,
        AssetJob.job_type == "download",
        AssetJob.url_sha256 == url_key,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        if asset_ref_id and not existing.asset_ref_id:
            existing.asset_ref_id = asset_ref_id
        if meta_json and not existing.meta_json:
            existing.meta_json = meta_json
        return existing, False

    job = AssetJob(
        location_id=location_id,
        job_type="download",
        status="pending",
        priority=int(priority or 0),
        asset_ref_id=asset_ref_id,
        url_sha256=url_key,
        url=url,
        attempts=0,
        max_attempts=5,
        next_attempt_at=_now(),
        meta_json=meta_json,
    )
    db.add(job)
    await db.flush()
    return job, True


async def discover_funnel_page_html_assets(
    db: AsyncSession,
    location: Location,
    *,
    blobstore: BlobStore | None = None,
    include_relative: bool = False,
) -> AssetDiscoveryResult:
    """Scan `funnel_page.content_html` for asset references and queue downloads."""
    result = AssetDiscoveryResult()
    # Keep this module usable without CRM extras installed (pydantic-settings).
    blobstore = blobstore or BlobStore("data/blobstore")

    stmt = (
        select(FunnelPage)
        .join(Funnel, FunnelPage.funnel_id == Funnel.id)
        .where(Funnel.location_id == location.id)
        .order_by(FunnelPage.created_at.asc())
    )
    pages = list((await db.execute(stmt)).scalars().all())

    for page in pages:
        html = page.content_html or ""
        if not html:
            continue

        try:
            candidates = list(iter_html_asset_candidates(html, include_relative=include_relative))
        except Exception as exc:
            result.errors.append(f"Funnel page {page.id}: HTML parse error: {exc}")
            continue

        for c in candidates:
            try:
                if c.is_data_uri:
                    content_type, data = parse_data_uri(c.fetch_url)
                    sha = sha256_hex(data)
                    blobstore.put_bytes_atomic(sha, data)
                    asset, created = await _upsert_asset(
                        db,
                        location_id=location.id,
                        sha256=sha,
                        size_bytes=len(data),
                        content_type=content_type,
                        original_url=None,
                        original_filename=None,
                        source="funnel_page_data_uri",
                        meta_json={"context": c.context},
                    )
                    if created:
                        result.assets_created += 1
                    else:
                            result.assets_updated += 1

                    _, ref_created = await _upsert_asset_ref(
                        db,
                        location_id=location.id,
                        asset_id=asset.id,
                        entity_type="funnel_page",
                        entity_id=page.id,
                        remote_entity_id=page.ghl_id,
                        field_path="content_html",
                        usage=c.usage,
                        # Avoid storing massive base64 payloads in the DB; bytes live in blobstore.
                        original_url=f"data:sha256:{sha}",
                        meta_json={"sha256": sha, "content_type": content_type, "context": c.context},
                    )
                    if ref_created:
                        result.refs_created += 1
                    else:
                        result.refs_updated += 1
                    continue

                    # URL reference: create ref + queue download.
                ref, ref_created = await _upsert_asset_ref(
                    db,
                    location_id=location.id,
                    asset_id=None,
                    entity_type="funnel_page",
                    entity_id=page.id,
                    remote_entity_id=page.ghl_id,
                    field_path="content_html",
                    usage=c.usage,
                    original_url=c.raw_url,
                    meta_json={"fetch_url": c.fetch_url, "context": c.context},
                )
                if ref_created:
                    result.refs_created += 1
                else:
                    result.refs_updated += 1

                _, job_created = await _enqueue_download_job(
                    db,
                    location_id=location.id,
                    url=c.fetch_url,
                    asset_ref_id=ref.id,
                    meta_json={
                        "source": "funnel_page_html",
                        "entity_type": "funnel_page",
                        "entity_id": str(page.id),
                        "remote_entity_id": page.ghl_id,
                        "field_path": "content_html",
                        "original_url_raw": c.raw_url,
                        "context": c.context,
                    },
                )
                if job_created:
                    result.jobs_created += 1
                else:
                    result.jobs_updated += 1
            except Exception as exc:
                result.errors.append(f"Funnel page {page.id}: asset ref '{c.fetch_url}': {exc}")

    await db.commit()
    return result


def _iter_urls_in_json(obj: Any) -> Iterable[tuple[str, str]]:
    """Yield (path, url) for any string value that looks like a URL."""
    def _walk(v: Any, path: str):
        if isinstance(v, dict):
            for k, vv in v.items():
                k_str = str(k)
                next_path = f"{path}.{k_str}" if path else k_str
                yield from _walk(vv, next_path)
        elif isinstance(v, list):
            for i, vv in enumerate(v):
                next_path = f"{path}[{i}]"
                yield from _walk(vv, next_path)
        elif isinstance(v, str):
            s = v.strip()
            if s.startswith("//"):
                yield path, "https:" + s
            elif s.lower().startswith(("http://", "https://")):
                yield path, s
        return

    yield from _walk(obj, "")


async def discover_conversation_message_attachments_from_raw(
    db: AsyncSession,
    location: Location,
    *,
    include_conversations: bool = True,
    include_messages: bool = True,
) -> AssetDiscoveryResult:
    """Best-effort scan raw conversation/message payloads for attachment URLs.

    This is intentionally permissive; fidelity can be tightened as we learn
    concrete payload shapes.
    """
    result = AssetDiscoveryResult()

    types: list[str] = []
    if include_conversations:
        types.append("conversation")
    if include_messages:
        types.append("message")

    stmt = select(GHLRawEntity).where(
        GHLRawEntity.location_id == location.id,
        GHLRawEntity.entity_type.in_(types),
    )
    raws = list((await db.execute(stmt)).scalars().all())

    for raw in raws:
        payload = raw.payload_json
        if not isinstance(payload, dict):
            continue

        for path, url in _iter_urls_in_json(payload):
            if not url:
                continue
            try:
                lowered_path = path.lower()
                if not any(key in lowered_path for key in ("attachments", "attach", "media", "file")):
                    continue

                entity_id: uuid.UUID | None = None
                if raw.entity_type == "message":
                    stmt_msg = select(Message).where(
                        Message.location_id == location.id,
                        Message.provider_id == raw.ghl_id,
                    )
                    msg = (await db.execute(stmt_msg)).scalar_one_or_none()
                    if msg:
                        entity_id = msg.id
                elif raw.entity_type == "conversation":
                    stmt_conv = select(Conversation).where(
                        Conversation.location_id == location.id,
                        Conversation.ghl_id == raw.ghl_id,
                    )
                    conv = (await db.execute(stmt_conv)).scalar_one_or_none()
                    if conv:
                        entity_id = conv.id

                ref, ref_created = await _upsert_asset_ref(
                    db,
                    location_id=location.id,
                    asset_id=None,
                    entity_type=f"{raw.entity_type}_raw",
                    entity_id=entity_id,
                    remote_entity_id=raw.ghl_id,
                    field_path="/" + path.replace(".", "/").replace("[", "/").replace("]", ""),
                    usage="attachment",
                    original_url=url,
                    meta_json={"source": "raw_store", "raw_entity_type": raw.entity_type},
                )
                if ref_created:
                    result.refs_created += 1
                else:
                    result.refs_updated += 1

                _, job_created = await _enqueue_download_job(
                    db,
                    location_id=location.id,
                    url=url,
                    asset_ref_id=ref.id,
                    meta_json={
                        "source": "raw_conversation_message",
                        "remote_entity_id": raw.ghl_id,
                        "raw_entity_type": raw.entity_type,
                        "field_path": path,
                    },
                )
                if job_created:
                    result.jobs_created += 1
                else:
                    result.jobs_updated += 1
            except Exception as exc:
                result.errors.append(f"Raw {raw.entity_type} {raw.ghl_id}: url {url}: {exc}")

    await db.commit()
    return result
