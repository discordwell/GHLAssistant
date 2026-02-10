"""Funnel page builder JSON capture (loss-minimizing).

GHL's page builder stores the editable "page-data" JSON separately (often in
Firebase Storage) and the backend UI calls `/funnels/page/<pageId>` to get
metadata + a signed `pageDataDownloadUrl`.

To minimize data loss during import, we:
  - Fetch the builder metadata for each funnel page.
  - Download the page-data JSON bytes immediately (signed URLs can rotate).
  - Store bytes in the canonical blobstore and reference them via Asset/AssetRef.
  - Persist latest metadata + sha256 into `ghl_raw_entity`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..assets.blobstore import BlobStore, Sha256BlobStore
from ..assets.downloader import AssetDownloader
from ..models.asset import AssetRef
from ..models.funnel import Funnel, FunnelPage
from ..models.ghl_raw import GHLRawEntity
from ..models.location import Location
from .import_assets import AssetDiscoveryResult, _upsert_asset, _upsert_asset_ref
from .raw_store import upsert_raw_entity

if TYPE_CHECKING:
    from maxlevel.api.client import GHLClient


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _to_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _first_str(d: dict, keys: list[str]) -> str | None:
    for key in keys:
        v = d.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


async def capture_funnel_page_builder_data(
    db: AsyncSession,
    location: Location,
    ghl: "GHLClient",
    *,
    blobstore_dir: str,
    limit: int = 0,
) -> AssetDiscoveryResult:
    """Capture builder metadata + page-data JSON for funnel pages.

    Args:
        db: DB session
        location: Tenant location
        ghl: Authenticated GHL API client
        blobstore_dir: Root directory for blobstore bytes (e.g. data/blobstore)
        limit: Max pages to process (0 = unlimited). When limiting, pages without
            an existing builder-json AssetRef are processed first.
    """
    result = AssetDiscoveryResult()
    blobstore = BlobStore(blobstore_dir)
    streaming_store = Sha256BlobStore(blobstore_dir)
    downloader = AssetDownloader(streaming_store)

    try:
        stmt = (
            select(FunnelPage)
            .join(Funnel, FunnelPage.funnel_id == Funnel.id)
            .where(Funnel.location_id == location.id)
            .order_by(FunnelPage.created_at.asc())
        )
        pages = list((await db.execute(stmt)).scalars().all())

        # When capped, prefer pages we haven't captured builder JSON for yet.
        if limit and pages:
            captured_stmt = select(AssetRef.entity_id).where(
                AssetRef.location_id == location.id,
                AssetRef.entity_type == "funnel_page",
                AssetRef.usage == "builder_json",
                AssetRef.entity_id.is_not(None),
            )
            captured_ids = set((await db.execute(captured_stmt)).scalars().all())
            pages.sort(key=lambda p: (p.id in captured_ids, p.created_at or _now()))
            pages = pages[: int(limit)]

        for page in pages:
            if not isinstance(page.ghl_id, str) or not page.ghl_id:
                continue

            try:
                meta = _to_dict(await ghl.funnels.get_page_builder_meta(page.ghl_id))
            except Exception as exc:
                result.errors.append(f"Funnel page {page.id}: builder meta fetch failed: {exc}")
                continue

            meta_payload = meta.get("page") if isinstance(meta.get("page"), dict) else meta
            meta_payload = _to_dict(meta_payload)

            page_data_url = _first_str(meta_payload, ["pageDataUrl", "page_data_url"])
            download_url = _first_str(meta_payload, ["pageDataDownloadUrl", "page_data_download_url"])

            # Skip download if pageDataUrl matches a previous capture and bytes still exist.
            existing_sha = None
            existing_size = None
            existing_ct = None
            existing_page_data_url = None

            try:
                existing_stmt = select(GHLRawEntity).where(
                    GHLRawEntity.location_id == location.id,
                    GHLRawEntity.entity_type == "funnel_page_builder",
                    GHLRawEntity.ghl_id == page.ghl_id,
                )
                existing = (await db.execute(existing_stmt)).scalar_one_or_none()
                if existing and isinstance(existing.payload_json, dict):
                    existing_sha = existing.payload_json.get("page_data_sha256")
                    existing_size = existing.payload_json.get("page_data_size_bytes")
                    existing_ct = existing.payload_json.get("page_data_content_type")
                    existing_page_data_url = existing.payload_json.get("page_data_url")
            except Exception:
                existing = None

            need_download = True
            if (
                isinstance(page_data_url, str)
                and page_data_url
                and page_data_url == existing_page_data_url
                and isinstance(existing_sha, str)
                and blobstore.has(existing_sha)
            ):
                need_download = False

            sha = existing_sha if isinstance(existing_sha, str) else None
            size_bytes = existing_size if isinstance(existing_size, int) else None
            content_type = existing_ct if isinstance(existing_ct, str) else None
            final_url = None

            if need_download and isinstance(download_url, str) and download_url:
                try:
                    dl = await downloader.download(download_url)
                    sha = dl.sha256
                    size_bytes = dl.size_bytes
                    content_type = dl.content_type or "application/json"
                    final_url = dl.final_url
                except Exception as exc:
                    result.errors.append(f"Funnel page {page.id}: page-data download failed: {exc}")

            # Persist raw payload (even if download failed).
            try:
                await upsert_raw_entity(
                    db,
                    location=location,
                    entity_type="funnel_page_builder",
                    ghl_id=page.ghl_id,
                    payload={
                        "meta": meta_payload,
                        "page_data_url": page_data_url,
                        "page_data_download_url": download_url,
                        "page_data_sha256": sha,
                        "page_data_size_bytes": size_bytes,
                        "page_data_content_type": content_type,
                        "page_data_final_url": final_url,
                        "captured_at": _now().isoformat(),
                    },
                    source="api",
                )
            except Exception as exc:
                result.errors.append(f"Funnel page {page.id}: raw upsert failed: {exc}")

            if not (isinstance(sha, str) and isinstance(size_bytes, int) and size_bytes >= 0):
                # Without bytes, we can't create/update the canonical Asset.
                continue

            try:
                asset, created = await _upsert_asset(
                    db,
                    location_id=location.id,
                    sha256=sha,
                    size_bytes=size_bytes,
                    content_type=content_type or "application/json",
                    original_url=final_url or download_url,
                    original_filename=None,
                    source="funnel_page_builder",
                    meta_json={
                        "remote_page_id": page.ghl_id,
                        "page_data_url": page_data_url,
                        "download_url": download_url,
                    },
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
                    field_path="builder_json",
                    usage="builder_json",
                    # Keep identity stable across rotating signed URLs.
                    original_url=None,
                    meta_json={
                        "remote_page_id": page.ghl_id,
                        "page_data_url": page_data_url,
                    },
                )
                if ref_created:
                    result.refs_created += 1
                else:
                    result.refs_updated += 1
            except Exception as exc:
                result.errors.append(f"Funnel page {page.id}: asset upsert failed: {exc}")

        await db.commit()
        return result
    finally:
        await downloader.aclose()
