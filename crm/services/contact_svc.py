"""Contact service - CRUD, search, tag assignment."""

from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.contact import Contact
from ..models.tag import Tag, ContactTag


async def list_contacts(
    db: AsyncSession,
    location_id: uuid.UUID,
    *,
    search: str | None = None,
    tag_name: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[Contact], int]:
    """List contacts with optional search and pagination. Returns (contacts, total)."""
    stmt = select(Contact).where(Contact.location_id == location_id)

    if search:
        q = f"%{search}%"
        stmt = stmt.where(
            or_(
                Contact.first_name.ilike(q),
                Contact.last_name.ilike(q),
                Contact.email.ilike(q),
                Contact.phone.ilike(q),
                Contact.company_name.ilike(q),
            )
        )

    if tag_name:
        stmt = stmt.join(ContactTag).join(Tag).where(Tag.name == tag_name)

    # Count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # Fetch page
    stmt = stmt.options(selectinload(Contact.tags)).order_by(
        Contact.created_at.desc()
    ).offset(offset).limit(limit)
    result = await db.execute(stmt)
    contacts = list(result.scalars().all())

    return contacts, total


async def get_contact(
    db: AsyncSession, contact_id: uuid.UUID
) -> Contact | None:
    """Get a single contact with relationships loaded."""
    stmt = (
        select(Contact)
        .where(Contact.id == contact_id)
        .options(
            selectinload(Contact.tags),
            selectinload(Contact.notes),
            selectinload(Contact.tasks),
            selectinload(Contact.opportunities),
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_contact(
    db: AsyncSession, location_id: uuid.UUID, **kwargs
) -> Contact:
    """Create a new contact."""
    contact = Contact(location_id=location_id, **kwargs)
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return contact


async def update_contact(
    db: AsyncSession, contact_id: uuid.UUID, **kwargs
) -> Contact | None:
    """Update an existing contact."""
    contact = await get_contact(db, contact_id)
    if not contact:
        return None
    for key, value in kwargs.items():
        setattr(contact, key, value)
    await db.commit()
    await db.refresh(contact)
    return contact


async def delete_contact(db: AsyncSession, contact_id: uuid.UUID) -> bool:
    """Delete a contact. Returns True if found and deleted."""
    stmt = select(Contact).where(Contact.id == contact_id)
    result = await db.execute(stmt)
    contact = result.scalar_one_or_none()
    if not contact:
        return False
    await db.delete(contact)
    await db.commit()
    return True


async def add_tag_to_contact(
    db: AsyncSession, contact_id: uuid.UUID, tag_id: uuid.UUID
) -> bool:
    """Add a tag to a contact. Returns False if already tagged."""
    stmt = select(ContactTag).where(
        ContactTag.contact_id == contact_id, ContactTag.tag_id == tag_id
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        return False
    db.add(ContactTag(contact_id=contact_id, tag_id=tag_id))
    await db.commit()
    return True


async def remove_tag_from_contact(
    db: AsyncSession, contact_id: uuid.UUID, tag_id: uuid.UUID
) -> bool:
    """Remove a tag from a contact."""
    stmt = select(ContactTag).where(
        ContactTag.contact_id == contact_id, ContactTag.tag_id == tag_id
    )
    result = await db.execute(stmt)
    ct = result.scalar_one_or_none()
    if not ct:
        return False
    await db.delete(ct)
    await db.commit()
    return True
