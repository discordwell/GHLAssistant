"""Asset job queue helpers (download worker)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .blobstore import Sha256BlobStore
from .downloader import AssetDownloader, DownloadError
from .hashes import url_sha256
from ..models.asset import Asset, AssetJob, AssetRef


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _backoff_seconds(attempts: int) -> int:
    # 30s, 60s, 120s, ... cap at 1h
    return min(3600, max(30, int(30 * (2 ** max(0, attempts)))))


@dataclass(frozen=True)
class JobRunStats:
    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0


async def enqueue_download_job(
    db: AsyncSession,
    *,
    location_id: uuid.UUID,
    url: str,
    asset_ref_id: uuid.UUID | None = None,
    priority: int = 0,
    meta_json: dict[str, Any] | None = None,
) -> AssetJob | None:
    if not isinstance(url, str) or not url.strip():
        return None

    url = url.strip()
    url_key = url_sha256(url)

    stmt = select(AssetJob).where(
        AssetJob.location_id == location_id,
        AssetJob.job_type == "download",
        AssetJob.url_sha256 == url_key,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        # If a new ref is provided, attach it (best-effort).
        if asset_ref_id and not existing.asset_ref_id:
            existing.asset_ref_id = asset_ref_id
        if meta_json and not existing.meta_json:
            existing.meta_json = meta_json
        return existing

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
        next_attempt_at=_utcnow(),
        meta_json=meta_json,
    )
    db.add(job)
    return job


async def upsert_asset(
    db: AsyncSession,
    *,
    location_id: uuid.UUID,
    sha256: str,
    size_bytes: int,
    content_type: str | None = None,
    original_filename: str | None = None,
    original_url: str | None = None,
    source: str | None = None,
    meta_json: dict[str, Any] | None = None,
) -> Asset:
    stmt = select(Asset).where(
        Asset.location_id == location_id,
        Asset.sha256 == sha256,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    now = _utcnow()

    if existing:
        existing.size_bytes = int(size_bytes)
        existing.last_seen_at = now

        # Only fill missing metadata (don't churn on repeated imports).
        if content_type and not existing.content_type:
            existing.content_type = content_type
        if original_filename and not existing.original_filename:
            existing.original_filename = original_filename
        if original_url and not existing.original_url:
            existing.original_url = original_url
        if source and not existing.source:
            existing.source = source
        if meta_json and not existing.meta_json:
            existing.meta_json = meta_json

        return existing

    asset = Asset(
        location_id=location_id,
        sha256=sha256,
        size_bytes=int(size_bytes),
        content_type=content_type,
        original_filename=original_filename,
        original_url=original_url,
        source=source,
        last_seen_at=now,
        meta_json=meta_json,
    )
    db.add(asset)
    return asset


async def _claim_next_download_job(
    db: AsyncSession,
    *,
    location_id: uuid.UUID,
    worker_id: str,
) -> AssetJob | None:
    now = _utcnow()
    pick_id = (
        select(AssetJob.id)
        .where(
            AssetJob.location_id == location_id,
            AssetJob.job_type == "download",
            AssetJob.status == "pending",
            AssetJob.next_attempt_at <= now,
        )
        .order_by(AssetJob.priority.desc(), AssetJob.next_attempt_at.asc(), AssetJob.created_at.asc())
        .limit(1)
        .scalar_subquery()
    )

    # Atomic claim: update the next pending row and return its id.
    # This avoids a race where multiple workers SELECT the same job before updating.
    stmt = (
        update(AssetJob)
        .where(
            AssetJob.id == pick_id,
            AssetJob.location_id == location_id,
            AssetJob.job_type == "download",
            AssetJob.status == "pending",
        )
        .values(
            status="in_progress",
            locked_at=now,
            locked_by=worker_id,
            started_at=func.coalesce(AssetJob.started_at, now),
        )
        .returning(AssetJob.id)
    )
    job_id = (await db.execute(stmt)).scalar_one_or_none()
    if not job_id:
        return None

    await db.commit()
    return await db.get(AssetJob, job_id)


async def process_download_jobs(
    db: AsyncSession,
    *,
    location_id: uuid.UUID,
    blobstore_dir: str,
    limit: int = 50,
    worker_id: str = "asset-worker",
    request_headers: dict[str, str] | None = None,
) -> JobRunStats:
    """Process pending download jobs (best-effort; sequential)."""
    blobstore = Sha256BlobStore(blobstore_dir)
    downloader = AssetDownloader(blobstore)

    processed = succeeded = failed = skipped = 0
    try:
        for _ in range(max(0, int(limit))):
            job = await _claim_next_download_job(db, location_id=location_id, worker_id=worker_id)
            if not job:
                break

            processed += 1
            url = (job.url or "").strip()
            if not url:
                job.status = "failed"
                job.finished_at = _utcnow()
                job.last_error = "missing_url"
                await db.commit()
                failed += 1
                continue

            meta = job.meta_json if isinstance(job.meta_json, dict) else {}
            source = meta.get("source") if isinstance(meta.get("source"), str) else None

            try:
                result = await downloader.download(url, headers=request_headers)
            except DownloadError as e:
                job.attempts = int(job.attempts or 0) + 1
                job.last_error = str(e)[:2000]
                if job.attempts >= int(job.max_attempts or 5):
                    job.status = "failed"
                    job.finished_at = _utcnow()
                    job.next_attempt_at = _utcnow()
                else:
                    job.status = "pending"
                    job.next_attempt_at = _utcnow() + timedelta(seconds=_backoff_seconds(job.attempts))
                await db.commit()
                failed += 1
                continue

            # Create/update canonical Asset row.
            asset = await upsert_asset(
                db,
                location_id=location_id,
                sha256=result.sha256,
                size_bytes=result.size_bytes,
                content_type=result.content_type,
                original_filename=result.original_filename,
                original_url=url,
                source=source,
                meta_json={"final_url": result.final_url} if result.final_url else None,
            )
            await db.flush()

            # Link ref (if present) to the resolved asset.
            if job.asset_ref_id:
                ref = await db.get(AssetRef, job.asset_ref_id)
                if ref and not ref.asset_id:
                    ref.asset_id = asset.id

            job.status = "succeeded"
            job.asset_id = asset.id
            job.finished_at = _utcnow()
            job.last_error = None
            await db.commit()
            succeeded += 1

    finally:
        await downloader.aclose()

    return JobRunStats(
        processed=processed,
        succeeded=succeeded,
        failed=failed,
        skipped=skipped,
    )
