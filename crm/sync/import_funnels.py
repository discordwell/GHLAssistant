"""Import funnels and pages from GHL."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.funnel import Funnel, FunnelPage
from ..models.location import Location
from ..schemas.sync import SyncResult
from .raw_store import upsert_raw_entity


def _to_dict(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    return {}


def _extract_funnel_payload(detail: dict) -> dict:
    if not detail:
        return {}
    if isinstance(detail.get("funnel"), dict):
        return detail["funnel"]
    return detail


def _extract_page_payload(detail: dict) -> dict:
    if not detail:
        return {}
    if isinstance(detail.get("page"), dict):
        return detail["page"]
    return detail


def _is_true(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"true", "1", "yes", "published", "active"}
    if isinstance(value, (int, float)):
        return bool(value)
    return default


async def import_funnels(
    db: AsyncSession, location: Location, funnels_data: list[dict],
    pages_by_funnel: dict[str, list[dict]] | None = None,
    details_by_funnel: dict[str, dict] | None = None,
    page_details_by_funnel: dict[str, dict[str, dict]] | None = None,
) -> SyncResult:
    """Import funnels and pages from GHL."""
    result = SyncResult()
    pages_by_funnel = pages_by_funnel or {}
    details_by_funnel = details_by_funnel or {}
    page_details_by_funnel = page_details_by_funnel or {}

    for f_data in funnels_data:
        ghl_id = f_data.get("id", f_data.get("_id", ""))
        name = f_data.get("name", "")
        if not name:
            continue

        detail_payload = _extract_funnel_payload(_to_dict(details_by_funnel.get(ghl_id)))
        await upsert_raw_entity(
            db,
            location=location,
            entity_type="funnel",
            ghl_id=ghl_id,
            payload={"list": _to_dict(f_data), "detail": _to_dict(detail_payload)},
        )
        description = detail_payload.get("description", f_data.get("description"))
        is_published = _is_true(
            detail_payload.get("isPublished", f_data.get("isPublished", False)),
            default=False,
        )

        stmt = select(Funnel).where(
            Funnel.location_id == location.id, Funnel.ghl_id == ghl_id
        )
        funnel = (await db.execute(stmt)).scalar_one_or_none()

        if funnel:
            funnel.name = name
            funnel.description = description
            funnel.is_published = is_published
            funnel.last_synced_at = datetime.now(timezone.utc)
            result.updated += 1
        else:
            funnel = Funnel(
                location_id=location.id, name=name,
                description=description, is_published=is_published,
                ghl_id=ghl_id, ghl_location_id=location.ghl_location_id,
                last_synced_at=datetime.now(timezone.utc),
            )
            db.add(funnel)
            await db.flush()
            result.created += 1

        # Import pages
        details_for_funnel = page_details_by_funnel.get(ghl_id, {})
        for i, p_data in enumerate(pages_by_funnel.get(ghl_id, [])):
            p_ghl_id = p_data.get("id", p_data.get("_id", ""))
            p_name = p_data.get("name", f"Page {i+1}")
            slug = p_data.get("slug", p_data.get("path", f"page-{i+1}"))
            page_detail = _extract_page_payload(_to_dict(details_for_funnel.get(p_ghl_id, {})))
            await upsert_raw_entity(
                db,
                location=location,
                entity_type="funnel_page",
                ghl_id=p_ghl_id,
                payload={"list": _to_dict(p_data), "detail": _to_dict(page_detail)},
            )

            content_html = (
                page_detail.get("html")
                or page_detail.get("contentHtml")
                or p_data.get("html")
                or p_data.get("contentHtml")
                or ""
            )
            page_is_published = _is_true(
                page_detail.get("isPublished", p_data.get("isPublished", False)),
                default=False,
            )

            if p_ghl_id:
                stmt = select(FunnelPage).where(
                    FunnelPage.funnel_id == funnel.id, FunnelPage.ghl_id == p_ghl_id
                )
                page = (await db.execute(stmt)).scalar_one_or_none()
            else:
                stmt = select(FunnelPage).where(
                    FunnelPage.funnel_id == funnel.id, FunnelPage.url_slug == slug
                )
                page = (await db.execute(stmt)).scalar_one_or_none()

            if page:
                page.name = p_name
                page.url_slug = slug
                page.content_html = content_html
                page.position = i
                page.is_published = page_is_published
            else:
                page = FunnelPage(
                    funnel_id=funnel.id,
                    name=p_name,
                    url_slug=slug,
                    content_html=content_html,
                    position=i,
                    is_published=page_is_published,
                    ghl_id=p_ghl_id,
                )
                db.add(page)

    await db.commit()
    return result
