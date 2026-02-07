"""Funnel service - CRUD funnels and pages."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.funnel import Funnel, FunnelPage


async def list_funnels(
    db: AsyncSession, location_id: uuid.UUID
) -> list[Funnel]:
    stmt = (
        select(Funnel)
        .where(Funnel.location_id == location_id)
        .options(selectinload(Funnel.pages))
        .order_by(Funnel.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_funnel(db: AsyncSession, funnel_id: uuid.UUID) -> Funnel | None:
    stmt = (
        select(Funnel)
        .where(Funnel.id == funnel_id)
        .options(selectinload(Funnel.pages))
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_funnel(
    db: AsyncSession, location_id: uuid.UUID, **kwargs
) -> Funnel:
    funnel = Funnel(location_id=location_id, **kwargs)
    db.add(funnel)
    await db.commit()
    await db.refresh(funnel)
    return funnel


async def update_funnel(
    db: AsyncSession, funnel_id: uuid.UUID, **kwargs
) -> Funnel | None:
    stmt = select(Funnel).where(Funnel.id == funnel_id)
    funnel = (await db.execute(stmt)).scalar_one_or_none()
    if not funnel:
        return None
    for k, v in kwargs.items():
        setattr(funnel, k, v)
    await db.commit()
    await db.refresh(funnel)
    return funnel


async def delete_funnel(db: AsyncSession, funnel_id: uuid.UUID) -> bool:
    stmt = select(Funnel).where(Funnel.id == funnel_id)
    funnel = (await db.execute(stmt)).scalar_one_or_none()
    if not funnel:
        return False
    await db.delete(funnel)
    await db.commit()
    return True


async def add_page(
    db: AsyncSession, funnel_id: uuid.UUID, **kwargs
) -> FunnelPage:
    stmt = select(func.max(FunnelPage.position)).where(FunnelPage.funnel_id == funnel_id)
    result = (await db.execute(stmt)).scalar()
    max_pos = result if result is not None else -1
    page = FunnelPage(funnel_id=funnel_id, position=max_pos + 1, **kwargs)
    db.add(page)
    await db.commit()
    await db.refresh(page)
    return page


async def update_page(
    db: AsyncSession, page_id: uuid.UUID, **kwargs
) -> FunnelPage | None:
    stmt = select(FunnelPage).where(FunnelPage.id == page_id)
    page = (await db.execute(stmt)).scalar_one_or_none()
    if not page:
        return None
    for k, v in kwargs.items():
        setattr(page, k, v)
    await db.commit()
    await db.refresh(page)
    return page


async def delete_page(db: AsyncSession, page_id: uuid.UUID) -> bool:
    stmt = select(FunnelPage).where(FunnelPage.id == page_id)
    page = (await db.execute(stmt)).scalar_one_or_none()
    if not page:
        return False
    await db.delete(page)
    await db.commit()
    return True


async def get_public_page(
    db: AsyncSession, funnel_id: uuid.UUID, url_slug: str
) -> FunnelPage | None:
    stmt = select(FunnelPage).where(
        FunnelPage.funnel_id == funnel_id,
        FunnelPage.url_slug == url_slug,
        FunnelPage.is_published == True,  # noqa: E712
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def reorder_pages(
    db: AsyncSession, funnel_id: uuid.UUID, page_ids: list[str]
) -> None:
    for i, pid in enumerate(page_ids):
        stmt = select(FunnelPage).where(
            FunnelPage.id == uuid.UUID(pid), FunnelPage.funnel_id == funnel_id
        )
        page = (await db.execute(stmt)).scalar_one_or_none()
        if page:
            page.position = i
    await db.commit()
