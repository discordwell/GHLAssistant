"""Tests for exporting custom fields and custom values to GHL."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from crm.models.base import Base
from crm.models.custom_field import CustomFieldDefinition
from crm.models.custom_value import CustomValue
from crm.models.location import Location
from crm.sync.exporter import export_custom_fields, export_custom_values


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def location(db: AsyncSession) -> Location:
    loc = Location(
        id=uuid.uuid4(),
        name="Test Location",
        slug="test-location",
        timezone="UTC",
        ghl_location_id="ghl_loc_123",
    )
    db.add(loc)
    await db.commit()
    await db.refresh(loc)
    return loc


class FakeCustomFieldsAPI:
    def __init__(self, items: list[dict] | None = None):
        self.items = list(items or [])
        self.create_calls: list[dict] = []
        self.update_calls: list[dict] = []

    async def list(self, location_id: str | None = None):
        return {"customFields": list(self.items)}

    async def create(
        self,
        name: str,
        field_key: str,
        data_type: str = "TEXT",
        placeholder: str | None = None,
        position: int | None = None,
        location_id: str | None = None,
    ):
        self.create_calls.append(
            {
                "name": name,
                "field_key": field_key,
                "data_type": data_type,
                "placeholder": placeholder,
                "position": position,
                "location_id": location_id,
            }
        )
        new_id = f"cf_{len(self.items) + 1}"
        payload = {"id": new_id, "name": name, "fieldKey": field_key, "dataType": data_type}
        self.items.append(payload)
        return {"customField": payload}

    async def update(
        self,
        field_id: str,
        name: str | None = None,
        placeholder: str | None = None,
        position: int | None = None,
        location_id: str | None = None,
    ):
        self.update_calls.append(
            {
                "field_id": field_id,
                "name": name,
                "placeholder": placeholder,
                "position": position,
                "location_id": location_id,
            }
        )
        return {"customField": {"id": field_id}}


class FakeCustomValuesAPI:
    def __init__(self, items: list[dict] | None = None):
        self.items = list(items or [])
        self.create_calls: list[dict] = []
        self.update_calls: list[dict] = []

    async def list(self, location_id: str | None = None):
        return {"customValues": list(self.items)}

    async def create(self, name: str, value: str, location_id: str | None = None):
        self.create_calls.append({"name": name, "value": value, "location_id": location_id})
        new_id = f"cv_{len(self.items) + 1}"
        payload = {"id": new_id, "name": name, "value": value}
        self.items.append(payload)
        return {"customValue": payload}

    async def update(
        self,
        value_id: str,
        name: str | None = None,
        value: str | None = None,
        location_id: str | None = None,
    ):
        self.update_calls.append(
            {"value_id": value_id, "name": name, "value": value, "location_id": location_id}
        )
        return {"customValue": {"id": value_id}}


class FakeGHL:
    def __init__(self, *, custom_fields: FakeCustomFieldsAPI, custom_values: FakeCustomValuesAPI):
        self.custom_fields = custom_fields
        self.custom_values = custom_values


@pytest.mark.asyncio
async def test_export_custom_fields_reconciles_by_field_key(db: AsyncSession, location: Location):
    db.add(
        CustomFieldDefinition(
            location_id=location.id,
            name="Lead Score",
            field_key="lead_score",
            data_type="number",
            position=0,
            ghl_id=None,
        )
    )
    await db.commit()

    ghl = FakeGHL(
        custom_fields=FakeCustomFieldsAPI(
            items=[{"id": "ghl_cf_1", "name": "Lead Score", "fieldKey": "lead_score", "dataType": "NUMBER"}]
        ),
        custom_values=FakeCustomValuesAPI(items=[]),
    )

    result = await export_custom_fields(db, location, ghl)
    assert result.created == 0
    assert result.updated == 1
    assert ghl.custom_fields.create_calls == []
    assert ghl.custom_fields.update_calls == []

    from sqlalchemy import select

    defn_model = (await db.execute(select(CustomFieldDefinition))).scalar_one()
    assert defn_model.ghl_id == "ghl_cf_1"
    assert defn_model.last_synced_at is not None


@pytest.mark.asyncio
async def test_export_custom_values_creates_missing(db: AsyncSession, location: Location):
    db.add(
        CustomValue(
            location_id=location.id,
            name="Business Hours",
            value="Mon-Fri 9am-5pm",
            ghl_id=None,
        )
    )
    await db.commit()

    ghl = FakeGHL(
        custom_fields=FakeCustomFieldsAPI(items=[]),
        custom_values=FakeCustomValuesAPI(items=[]),
    )

    result = await export_custom_values(db, location, ghl)
    assert result.created == 1
    assert result.updated == 0
    assert len(ghl.custom_values.create_calls) == 1
    assert ghl.custom_values.update_calls == []

    from sqlalchemy import select

    cv = (await db.execute(select(CustomValue))).scalar_one()
    assert cv.ghl_id == "cv_1"
    assert cv.last_synced_at is not None
