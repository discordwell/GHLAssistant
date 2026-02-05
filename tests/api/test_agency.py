"""Tests for Agency API (sub-account management)."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from tests.conftest import (
    SAMPLE_LOCATION_ID,
    SAMPLE_COMPANY_ID,
)


# Sample fixtures
SAMPLE_SNAPSHOT_ID = "snapshot_123456"


@pytest.fixture
def sample_location():
    """Sample location/sub-account data."""
    return {
        "_id": SAMPLE_LOCATION_ID,
        "name": "Test Business",
        "email": "test@example.com",
        "phone": "+15551234567",
        "address": "123 Main St",
        "city": "New York",
        "state": "NY",
        "postalCode": "10001",
        "country": "US",
        "website": "https://example.com",
        "timezone": "America/New_York",
        "companyId": SAMPLE_COMPANY_ID,
    }


@pytest.fixture
def sample_locations_list(sample_location):
    """Sample list of locations."""
    return {
        "locations": [
            sample_location,
            {
                "_id": "loc_second",
                "name": "Second Business",
                "email": "second@example.com",
                "timezone": "America/Los_Angeles",
            },
        ],
        "total": 2,
    }


@pytest.fixture
def sample_snapshot():
    """Sample snapshot data."""
    return {
        "_id": SAMPLE_SNAPSHOT_ID,
        "name": "Default Snapshot",
        "createdAt": "2024-01-15T10:00:00Z",
    }


@pytest.fixture
def sample_user():
    """Sample user data."""
    return {
        "_id": "user_123",
        "firstName": "John",
        "lastName": "Doe",
        "email": "john@example.com",
        "role": "admin",
    }


class TestAgencyAPILocations:
    """Test Agency API location management."""

    @pytest.mark.asyncio
    async def test_list_locations(self, mock_ghl_client, mock_response, sample_locations_list):
        """Test listing all sub-accounts."""
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response(sample_locations_list)
        )

        result = await mock_ghl_client.agency.list_locations()

        assert "locations" in result
        assert len(result["locations"]) == 2
        assert result["locations"][0]["name"] == "Test Business"
        mock_ghl_client._client.get.assert_called_with(
            "/locations/search",
            params={"companyId": SAMPLE_COMPANY_ID, "limit": 100, "skip": 0},
        )

    @pytest.mark.asyncio
    async def test_list_locations_with_search(self, mock_ghl_client, mock_response, sample_locations_list):
        """Test listing locations with search filter."""
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response(sample_locations_list)
        )

        result = await mock_ghl_client.agency.list_locations(search="Test")

        mock_ghl_client._client.get.assert_called_with(
            "/locations/search",
            params={"companyId": SAMPLE_COMPANY_ID, "limit": 100, "skip": 0, "search": "Test"},
        )

    @pytest.mark.asyncio
    async def test_get_location(self, mock_ghl_client, mock_response, sample_location):
        """Test getting a single sub-account."""
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response({"location": sample_location})
        )

        result = await mock_ghl_client.agency.get_location(SAMPLE_LOCATION_ID)

        assert result["location"]["name"] == "Test Business"
        mock_ghl_client._client.get.assert_called_with(
            f"/locations/{SAMPLE_LOCATION_ID}",
            params={},
        )

    @pytest.mark.asyncio
    async def test_create_location(self, mock_ghl_client, mock_response, sample_location):
        """Test creating a new sub-account."""
        mock_ghl_client._client.post = AsyncMock(
            return_value=mock_response({"location": sample_location})
        )

        result = await mock_ghl_client.agency.create_location(
            name="Test Business",
            email="test@example.com",
            phone="+15551234567",
        )

        assert result["location"]["name"] == "Test Business"
        mock_ghl_client._client.post.assert_called_once()
        call_args = mock_ghl_client._client.post.call_args
        assert call_args[0][0] == "/locations/"
        assert call_args[1]["json"]["name"] == "Test Business"
        assert call_args[1]["json"]["email"] == "test@example.com"
        assert call_args[1]["json"]["phone"] == "+15551234567"

    @pytest.mark.asyncio
    async def test_create_location_with_snapshot(self, mock_ghl_client, mock_response, sample_location):
        """Test creating sub-account with snapshot template."""
        mock_ghl_client._client.post = AsyncMock(
            return_value=mock_response({"location": sample_location})
        )

        result = await mock_ghl_client.agency.create_location(
            name="Test Business",
            snapshot_id=SAMPLE_SNAPSHOT_ID,
        )

        call_args = mock_ghl_client._client.post.call_args
        assert call_args[1]["json"]["snapshotId"] == SAMPLE_SNAPSHOT_ID

    @pytest.mark.asyncio
    async def test_update_location(self, mock_ghl_client, mock_response, sample_location):
        """Test updating a sub-account."""
        updated_location = {**sample_location, "name": "Updated Business"}
        mock_ghl_client._client.put = AsyncMock(
            return_value=mock_response({"location": updated_location})
        )

        result = await mock_ghl_client.agency.update_location(
            SAMPLE_LOCATION_ID,
            name="Updated Business",
            email="new@example.com",
        )

        assert result["location"]["name"] == "Updated Business"
        mock_ghl_client._client.put.assert_called_once()
        call_args = mock_ghl_client._client.put.call_args
        assert call_args[0][0] == f"/locations/{SAMPLE_LOCATION_ID}"
        assert call_args[1]["json"]["name"] == "Updated Business"
        assert call_args[1]["json"]["email"] == "new@example.com"

    @pytest.mark.asyncio
    async def test_delete_location(self, mock_ghl_client, mock_response):
        """Test deleting a sub-account."""
        mock_ghl_client._client.delete = AsyncMock(
            return_value=mock_response({"succeeded": True})
        )

        result = await mock_ghl_client.agency.delete_location(SAMPLE_LOCATION_ID)

        assert result["succeeded"] is True
        mock_ghl_client._client.delete.assert_called_with(
            f"/locations/{SAMPLE_LOCATION_ID}"
        )


class TestAgencyAPISnapshots:
    """Test Agency API snapshot management."""

    @pytest.mark.asyncio
    async def test_list_snapshots(self, mock_ghl_client, mock_response, sample_snapshot):
        """Test listing available snapshots."""
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response({"snapshots": [sample_snapshot], "total": 1})
        )

        result = await mock_ghl_client.agency.list_snapshots()

        assert "snapshots" in result
        assert len(result["snapshots"]) == 1
        assert result["snapshots"][0]["name"] == "Default Snapshot"
        mock_ghl_client._client.get.assert_called_with(
            "/snapshots/",
            params={"companyId": SAMPLE_COMPANY_ID, "limit": 50, "skip": 0},
        )

    @pytest.mark.asyncio
    async def test_get_snapshot(self, mock_ghl_client, mock_response, sample_snapshot):
        """Test getting a single snapshot."""
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response({"snapshot": sample_snapshot})
        )

        result = await mock_ghl_client.agency.get_snapshot(SAMPLE_SNAPSHOT_ID)

        assert result["snapshot"]["name"] == "Default Snapshot"
        mock_ghl_client._client.get.assert_called_with(
            f"/snapshots/{SAMPLE_SNAPSHOT_ID}",
            params={},
        )


class TestAgencyAPIUsers:
    """Test Agency API user management."""

    @pytest.mark.asyncio
    async def test_list_users(self, mock_ghl_client, mock_response, sample_user):
        """Test listing agency users."""
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response({"users": [sample_user], "total": 1})
        )

        result = await mock_ghl_client.agency.list_users()

        assert "users" in result
        assert result["users"][0]["firstName"] == "John"
        mock_ghl_client._client.get.assert_called_with(
            "/users/search",
            params={"companyId": SAMPLE_COMPANY_ID, "limit": 50, "skip": 0},
        )

    @pytest.mark.asyncio
    async def test_list_users_by_location(self, mock_ghl_client, mock_response, sample_user):
        """Test listing users for a specific location."""
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response({"users": [sample_user], "total": 1})
        )

        result = await mock_ghl_client.agency.list_users(location_id=SAMPLE_LOCATION_ID)

        mock_ghl_client._client.get.assert_called_with(
            "/users/search",
            params={"locationId": SAMPLE_LOCATION_ID, "limit": 50, "skip": 0},
        )

    @pytest.mark.asyncio
    async def test_invite_user(self, mock_ghl_client, mock_response, sample_user):
        """Test inviting a user to the agency."""
        mock_ghl_client._client.post = AsyncMock(
            return_value=mock_response({"user": sample_user})
        )

        result = await mock_ghl_client.agency.invite_user(
            email="john@example.com",
            first_name="John",
            last_name="Doe",
            role="admin",
        )

        assert result["user"]["email"] == "john@example.com"
        mock_ghl_client._client.post.assert_called_once()
        call_args = mock_ghl_client._client.post.call_args
        assert call_args[0][0] == "/users/"
        assert call_args[1]["json"]["email"] == "john@example.com"
        assert call_args[1]["json"]["firstName"] == "John"
        assert call_args[1]["json"]["role"] == "admin"


class TestAgencyAPISaaSConfig:
    """Test Agency API SaaS configuration."""

    @pytest.mark.asyncio
    async def test_get_saas_config(self, mock_ghl_client, mock_response):
        """Test getting SaaS config for a location."""
        config = {"enabled": True, "domain": "custom.example.com"}
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response({"config": config})
        )

        result = await mock_ghl_client.agency.get_saas_config(SAMPLE_LOCATION_ID)

        assert result["config"]["enabled"] is True
        mock_ghl_client._client.get.assert_called_with(
            f"/locations/{SAMPLE_LOCATION_ID}/saas",
            params={},
        )

    @pytest.mark.asyncio
    async def test_update_saas_config(self, mock_ghl_client, mock_response):
        """Test updating SaaS config for a location."""
        mock_ghl_client._client.put = AsyncMock(
            return_value=mock_response({"config": {"enabled": True}})
        )

        result = await mock_ghl_client.agency.update_saas_config(
            SAMPLE_LOCATION_ID,
            enabled=True,
            domain="custom.example.com",
        )

        mock_ghl_client._client.put.assert_called_once()
        call_args = mock_ghl_client._client.put.call_args
        assert call_args[0][0] == f"/locations/{SAMPLE_LOCATION_ID}/saas"
        assert call_args[1]["json"]["enabled"] is True
        assert call_args[1]["json"]["domain"] == "custom.example.com"


class TestAgencyAPIBilling:
    """Test Agency API billing methods."""

    @pytest.mark.asyncio
    async def test_get_agency_plan(self, mock_ghl_client, mock_response):
        """Test getting agency billing plan."""
        plan = {"name": "Agency Pro", "status": "active"}
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response(plan)
        )

        result = await mock_ghl_client.agency.get_agency_plan()

        assert result["name"] == "Agency Pro"
        mock_ghl_client._client.get.assert_called_with(
            f"/internal-tools/billing/company/{SAMPLE_COMPANY_ID}/plan",
            params={},
        )

    @pytest.mark.asyncio
    async def test_get_location_limits(self, mock_ghl_client, mock_response):
        """Test getting sub-account limits."""
        limits = {"used": 5, "limit": 10, "remaining": 5}
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response(limits)
        )

        result = await mock_ghl_client.agency.get_location_limits()

        assert result["used"] == 5
        assert result["limit"] == 10
        mock_ghl_client._client.get.assert_called_with(
            f"/companies/{SAMPLE_COMPANY_ID}/location-limits",
            params={},
        )


class TestAgencyAPIEdgeCases:
    """Test edge cases and error handling for Agency API."""

    @pytest.mark.asyncio
    async def test_list_locations_empty(self, mock_ghl_client, mock_response):
        """Test handling empty location list."""
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response({"locations": [], "total": 0})
        )

        result = await mock_ghl_client.agency.list_locations()

        assert result["locations"] == []
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_list_snapshots_empty(self, mock_ghl_client, mock_response):
        """Test handling empty snapshot list."""
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response({"snapshots": [], "total": 0})
        )

        result = await mock_ghl_client.agency.list_snapshots()

        assert result["snapshots"] == []

    @pytest.mark.asyncio
    async def test_create_location_minimal(self, mock_ghl_client, mock_response):
        """Test creating location with minimal data."""
        mock_ghl_client._client.post = AsyncMock(
            return_value=mock_response({"location": {"_id": "new_loc", "name": "Minimal"}})
        )

        result = await mock_ghl_client.agency.create_location(name="Minimal")

        call_args = mock_ghl_client._client.post.call_args
        data = call_args[1]["json"]
        assert data["name"] == "Minimal"
        assert data["companyId"] == SAMPLE_COMPANY_ID
        assert data["country"] == "US"
        assert data["timezone"] == "America/New_York"
        assert "email" not in data
        assert "phone" not in data

    @pytest.mark.asyncio
    async def test_update_location_partial(self, mock_ghl_client, mock_response):
        """Test updating only specific fields."""
        mock_ghl_client._client.put = AsyncMock(
            return_value=mock_response({"location": {"name": "Updated"}})
        )

        await mock_ghl_client.agency.update_location(SAMPLE_LOCATION_ID, name="Updated")

        call_args = mock_ghl_client._client.put.call_args
        data = call_args[1]["json"]
        assert data == {"name": "Updated"}
