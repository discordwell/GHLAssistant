"""Contact schemas."""

from __future__ import annotations

import uuid
from pydantic import BaseModel


class ContactCreate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    company_name: str | None = None
    address1: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None
    source: str | None = None
    dnd: bool = False


class ContactUpdate(ContactCreate):
    pass


class ContactResponse(ContactCreate):
    id: uuid.UUID

    model_config = {"from_attributes": True}
