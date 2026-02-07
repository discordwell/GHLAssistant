"""Form service - CRUD forms, fields, submissions."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.form import Form, FormField, FormSubmission


async def list_forms(
    db: AsyncSession, location_id: uuid.UUID
) -> list[Form]:
    stmt = (
        select(Form)
        .where(Form.location_id == location_id)
        .options(selectinload(Form.fields))
        .order_by(Form.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_form(db: AsyncSession, form_id: uuid.UUID) -> Form | None:
    stmt = (
        select(Form)
        .where(Form.id == form_id)
        .options(
            selectinload(Form.fields),
            selectinload(Form.submissions),
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_form(
    db: AsyncSession, location_id: uuid.UUID, **kwargs
) -> Form:
    form = Form(location_id=location_id, **kwargs)
    db.add(form)
    await db.commit()
    await db.refresh(form)
    return form


async def update_form(
    db: AsyncSession, form_id: uuid.UUID, **kwargs
) -> Form | None:
    stmt = select(Form).where(Form.id == form_id)
    form = (await db.execute(stmt)).scalar_one_or_none()
    if not form:
        return None
    for k, v in kwargs.items():
        setattr(form, k, v)
    await db.commit()
    await db.refresh(form)
    return form


async def delete_form(db: AsyncSession, form_id: uuid.UUID) -> bool:
    stmt = select(Form).where(Form.id == form_id)
    form = (await db.execute(stmt)).scalar_one_or_none()
    if not form:
        return False
    await db.delete(form)
    await db.commit()
    return True


async def add_field(
    db: AsyncSession, form_id: uuid.UUID, **kwargs
) -> FormField:
    # Get max position
    stmt = select(func.max(FormField.position)).where(FormField.form_id == form_id)
    result = (await db.execute(stmt)).scalar()
    max_pos = result if result is not None else -1
    field = FormField(form_id=form_id, position=max_pos + 1, **kwargs)
    db.add(field)
    await db.commit()
    await db.refresh(field)
    return field


async def update_field(
    db: AsyncSession, field_id: uuid.UUID, **kwargs
) -> FormField | None:
    stmt = select(FormField).where(FormField.id == field_id)
    field = (await db.execute(stmt)).scalar_one_or_none()
    if not field:
        return None
    for k, v in kwargs.items():
        setattr(field, k, v)
    await db.commit()
    await db.refresh(field)
    return field


async def delete_field(db: AsyncSession, field_id: uuid.UUID) -> bool:
    stmt = select(FormField).where(FormField.id == field_id)
    field = (await db.execute(stmt)).scalar_one_or_none()
    if not field:
        return False
    await db.delete(field)
    await db.commit()
    return True


async def reorder_fields(
    db: AsyncSession, form_id: uuid.UUID, field_ids: list[str]
) -> None:
    for i, fid in enumerate(field_ids):
        stmt = select(FormField).where(
            FormField.id == uuid.UUID(fid), FormField.form_id == form_id
        )
        field = (await db.execute(stmt)).scalar_one_or_none()
        if field:
            field.position = i
    await db.commit()


async def create_submission(
    db: AsyncSession, location_id: uuid.UUID, form_id: uuid.UUID,
    data_json: dict, source_ip: str | None = None, contact_id: uuid.UUID | None = None,
) -> FormSubmission:
    sub = FormSubmission(
        location_id=location_id,
        form_id=form_id,
        contact_id=contact_id,
        data_json=data_json,
        source_ip=source_ip,
    )
    db.add(sub)
    await db.commit()
    await db.refresh(sub)
    return sub


async def list_submissions(
    db: AsyncSession, form_id: uuid.UUID, offset: int = 0, limit: int = 50,
) -> tuple[list[FormSubmission], int]:
    stmt = select(FormSubmission).where(FormSubmission.form_id == form_id)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0
    stmt = stmt.order_by(FormSubmission.submitted_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all()), total
