"""Agency API - Manage sub-accounts (locations) at the agency level.

Requires Agency Pro ($497/mo) plan for full sub-account creation capabilities.
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .client import GHLClient


class AgencyAPI:
    """Agency-level API for GoHighLevel.

    Manage sub-accounts (locations) under your agency. This API requires
    agency-level access and typically the Agency Pro plan for creating
    new sub-accounts.

    Usage:
        async with GHLClient.from_session() as ghl:
            # List all sub-accounts under your agency
            locations = await ghl.agency.list_locations()

            # Create a new sub-account
            location = await ghl.agency.create_location(
                name="Client Business",
                email="client@example.com",
                phone="+15551234567",
            )

            # Get specific location details
            details = await ghl.agency.get_location("location_id")

            # Update location settings
            await ghl.agency.update_location(
                location_id="location_id",
                name="Updated Business Name",
            )
    """

    def __init__(self, client: "GHLClient"):
        self._client = client

    @property
    def _company_id(self) -> str:
        """Get company ID or raise error."""
        cid = self._client.config.company_id
        if not cid:
            raise ValueError("company_id required. Set via config or run 'maxlevel auth login'")
        return cid

    # =========================================================================
    # Locations (Sub-Accounts)
    # =========================================================================

    async def list_locations(
        self,
        company_id: str | None = None,
        limit: int = 100,
        skip: int = 0,
        search: str | None = None,
    ) -> dict[str, Any]:
        """List all sub-accounts (locations) under the agency.

        Args:
            company_id: Override default company ID
            limit: Max locations to return (default 100)
            skip: Number of locations to skip (for pagination)
            search: Search query to filter locations by name

        Returns:
            {"locations": [...], "total": N}
        """
        cid = company_id or self._company_id
        params = {"companyId": cid, "limit": limit, "skip": skip}

        if search:
            params["search"] = search

        return await self._client._get("/locations/search", **params)

    async def get_location(self, location_id: str) -> dict[str, Any]:
        """Get detailed information about a sub-account.

        Args:
            location_id: The location/sub-account ID

        Returns:
            {"location": {...}} with full location details including
            settings, branding, and configuration.
        """
        return await self._client._get(f"/locations/{location_id}")

    async def create_location(
        self,
        name: str,
        email: str | None = None,
        phone: str | None = None,
        address: str | None = None,
        city: str | None = None,
        state: str | None = None,
        postal_code: str | None = None,
        country: str = "US",
        website: str | None = None,
        timezone: str = "America/New_York",
        company_id: str | None = None,
        snapshot_id: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Create a new sub-account (location).

        Requires Agency Pro plan. Creates a new sub-account under your agency
        that can be assigned to a client.

        Args:
            name: Business name for the sub-account
            email: Primary contact email
            phone: Business phone number (E.164 format preferred)
            address: Street address
            city: City name
            state: State/province code
            postal_code: ZIP/postal code
            country: Country code (default: US)
            website: Business website URL
            timezone: IANA timezone (default: America/New_York)
            company_id: Override default company/agency ID
            snapshot_id: Optional snapshot ID to use as template
            **kwargs: Additional location configuration

        Returns:
            {"location": {...}} with created location data

        Raises:
            HTTPStatusError: If creation fails (e.g., plan limits exceeded)
        """
        cid = company_id or self._company_id

        data = {
            "companyId": cid,
            "name": name,
            "country": country,
            "timezone": timezone,
        }

        if email:
            data["email"] = email
        if phone:
            data["phone"] = phone
        if address:
            data["address"] = address
        if city:
            data["city"] = city
        if state:
            data["state"] = state
        if postal_code:
            data["postalCode"] = postal_code
        if website:
            data["website"] = website
        if snapshot_id:
            data["snapshotId"] = snapshot_id

        data.update(kwargs)

        return await self._client._post("/locations/", data)

    async def update_location(
        self,
        location_id: str,
        name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        address: str | None = None,
        city: str | None = None,
        state: str | None = None,
        postal_code: str | None = None,
        country: str | None = None,
        website: str | None = None,
        timezone: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Update an existing sub-account.

        Args:
            location_id: The location ID to update
            name: New business name
            email: New contact email
            phone: New phone number
            address: New street address
            city: New city
            state: New state/province
            postal_code: New ZIP/postal code
            country: New country code
            website: New website URL
            timezone: New timezone
            **kwargs: Additional fields to update

        Returns:
            {"location": {...}} with updated location data
        """
        data = {}

        if name is not None:
            data["name"] = name
        if email is not None:
            data["email"] = email
        if phone is not None:
            data["phone"] = phone
        if address is not None:
            data["address"] = address
        if city is not None:
            data["city"] = city
        if state is not None:
            data["state"] = state
        if postal_code is not None:
            data["postalCode"] = postal_code
        if country is not None:
            data["country"] = country
        if website is not None:
            data["website"] = website
        if timezone is not None:
            data["timezone"] = timezone

        data.update(kwargs)

        return await self._client._put(f"/locations/{location_id}", data)

    async def delete_location(self, location_id: str) -> dict[str, Any]:
        """Delete a sub-account.

        WARNING: This permanently deletes the sub-account and all its data.
        This action cannot be undone.

        Args:
            location_id: The location ID to delete

        Returns:
            {"succeeded": true} or error
        """
        return await self._client._delete(f"/locations/{location_id}")

    # =========================================================================
    # Snapshots (Location Templates)
    # =========================================================================

    async def list_snapshots(
        self,
        company_id: str | None = None,
        limit: int = 50,
        skip: int = 0,
    ) -> dict[str, Any]:
        """List available snapshots (location templates).

        Snapshots are pre-configured location templates that can be used
        when creating new sub-accounts.

        Args:
            company_id: Override default company ID
            limit: Max snapshots to return
            skip: Number to skip (for pagination)

        Returns:
            {"snapshots": [...], "total": N}
        """
        cid = company_id or self._company_id
        return await self._client._get(
            "/snapshots/",
            companyId=cid,
            limit=limit,
            skip=skip,
        )

    async def get_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        """Get snapshot details.

        Args:
            snapshot_id: The snapshot ID

        Returns:
            {"snapshot": {...}} with snapshot configuration
        """
        return await self._client._get(f"/snapshots/{snapshot_id}")

    # =========================================================================
    # Users (Agency Team Members)
    # =========================================================================

    async def list_users(
        self,
        company_id: str | None = None,
        location_id: str | None = None,
        limit: int = 50,
        skip: int = 0,
    ) -> dict[str, Any]:
        """List users in the agency or a specific location.

        Args:
            company_id: Filter by company/agency
            location_id: Filter by specific location
            limit: Max users to return
            skip: Number to skip (for pagination)

        Returns:
            {"users": [...], "total": N}
        """
        params = {"limit": limit, "skip": skip}

        if location_id:
            params["locationId"] = location_id
        else:
            cid = company_id or self._company_id
            params["companyId"] = cid

        return await self._client._get("/users/search", **params)

    async def invite_user(
        self,
        email: str,
        first_name: str,
        last_name: str,
        role: str = "user",
        location_id: str | None = None,
        company_id: str | None = None,
        permissions: list[str] | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Invite a user to the agency or a location.

        Args:
            email: User's email address
            first_name: User's first name
            last_name: User's last name
            role: User role (admin, user, etc.)
            location_id: Invite to specific location (sub-account access)
            company_id: Override default company ID
            permissions: List of permission strings
            **kwargs: Additional user configuration

        Returns:
            {"user": {...}} with invited user data
        """
        cid = company_id or self._company_id

        data = {
            "companyId": cid,
            "email": email,
            "firstName": first_name,
            "lastName": last_name,
            "role": role,
        }

        if location_id:
            data["locationId"] = location_id
        if permissions:
            data["permissions"] = permissions

        data.update(kwargs)

        return await self._client._post("/users/", data)

    # =========================================================================
    # SaaS Configuration
    # =========================================================================

    async def get_saas_config(
        self,
        location_id: str,
    ) -> dict[str, Any]:
        """Get SaaS (white-label) configuration for a location.

        Args:
            location_id: The location ID

        Returns:
            {"config": {...}} with SaaS settings
        """
        return await self._client._get(f"/locations/{location_id}/saas")

    async def update_saas_config(
        self,
        location_id: str,
        enabled: bool | None = None,
        domain: str | None = None,
        branding: dict | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Update SaaS configuration for a location.

        Args:
            location_id: The location ID
            enabled: Enable/disable SaaS mode
            domain: Custom domain for white-label
            branding: Branding configuration (logo, colors, etc.)
            **kwargs: Additional SaaS settings

        Returns:
            {"config": {...}} with updated settings
        """
        data = {}

        if enabled is not None:
            data["enabled"] = enabled
        if domain is not None:
            data["domain"] = domain
        if branding is not None:
            data["branding"] = branding

        data.update(kwargs)

        return await self._client._put(f"/locations/{location_id}/saas", data)

    # =========================================================================
    # Billing & Plans
    # =========================================================================

    async def get_agency_plan(
        self,
        company_id: str | None = None,
    ) -> dict[str, Any]:
        """Get the agency's current billing plan.

        Args:
            company_id: Override default company ID

        Returns:
            Plan details including tier, limits, and usage
        """
        cid = company_id or self._company_id
        return await self._client._get(f"/internal-tools/billing/company/{cid}/plan")

    async def get_location_limits(
        self,
        company_id: str | None = None,
    ) -> dict[str, Any]:
        """Get sub-account limits for the agency plan.

        Args:
            company_id: Override default company ID

        Returns:
            {"used": N, "limit": N, "remaining": N}
        """
        cid = company_id or self._company_id
        return await self._client._get(f"/companies/{cid}/location-limits")
