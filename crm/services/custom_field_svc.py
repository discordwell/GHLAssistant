"""Custom field definition + value service (EAV)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.custom_field import CustomFieldDefinition, CustomFieldValue


async def list_definitions(
    db: AsyncSession, location_id: uuid.UUID, entity_type: str = "contact"
) -> list[CustomFieldDefinition]:
    stmt = (
        select(CustomFieldDefinition)
        .where(
            CustomFieldDefinition.location_id == location_id,
            CustomFieldDefinition.entity_type == entity_type,
        )
        .order_by(CustomFieldDefinition.position)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_definition(
    db: AsyncSession, location_id: uuid.UUID, **kwargs
) -> CustomFieldDefinition:
    defn = CustomFieldDefinition(location_id=location_id, **kwargs)
    db.add(defn)
    await db.commit()
    await db.refresh(defn)
    return defn


async def delete_definition(db: AsyncSession, defn_id: uuid.UUID) -> bool:
    stmt = select(CustomFieldDefinition).where(CustomFieldDefinition.id == defn_id)
    result = await db.execute(stmt)
    defn = result.scalar_one_or_none()
    if not defn:
        return False
    await db.delete(defn)
    await db.commit()
    return True


async def get_values_for_entity(
    db: AsyncSession, entity_id: uuid.UUID, entity_type: str = "contact"
) -> dict[uuid.UUID, CustomFieldValue]:
    """Returns {definition_id: value} mapping for an entity."""
    stmt = select(CustomFieldValue).where(
        CustomFieldValue.entity_id == entity_id,
        CustomFieldValue.entity_type == entity_type,
    )
    result = await db.execute(stmt)
    return {v.definition_id: v for v in result.scalars().all()}


async def set_value(
    db: AsyncSession,
    definition_id: uuid.UUID,
    entity_id: uuid.UUID,
    entity_type: str,
    *,
    value_text: str | None = None,
    value_number: float | None = None,
    value_date: str | None = None,
    value_bool: bool | None = None,
) -> CustomFieldValue:
    """Set (upsert) a custom field value for an entity."""
    stmt = select(CustomFieldValue).where(
        CustomFieldValue.definition_id == definition_id,
        CustomFieldValue.entity_id == entity_id,
    )
    result = await db.execute(stmt)
    cfv = result.scalar_one_or_none()

    if cfv:
        cfv.value_text = value_text
        cfv.value_number = value_number
        cfv.value_date = value_date
        cfv.value_bool = value_bool
    else:
        cfv = CustomFieldValue(
            definition_id=definition_id,
            entity_id=entity_id,
            entity_type=entity_type,
            value_text=value_text,
            value_number=value_number,
            value_date=value_date,
            value_bool=value_bool,
        )
        db.add(cfv)

    await db.commit()
    await db.refresh(cfv)
    return cfv
