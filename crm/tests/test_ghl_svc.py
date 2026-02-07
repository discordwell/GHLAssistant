"""Tests for GHL service layer."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crm.services.ghl_svc import (
    GHLNotLinkedError,
    get_ghl_client,
    fetch_forms,
    fetch_form_submissions,
    fetch_calendars,
    fetch_conversations,
    fetch_campaigns,
    fetch_funnels,
)


@pytest.mark.asyncio
async def test_get_ghl_client_no_token():
    """Raises GHLNotLinkedError when no token available."""
    with patch("maxlevel.auth.manager.TokenManager") as MockTM:
        MockTM.return_value.has_valid_token.return_value = False
        with pytest.raises(GHLNotLinkedError):
            await get_ghl_client()


@pytest.mark.asyncio
async def test_get_ghl_client_with_token():
    """Returns a GHLClient when token is available."""
    with patch("maxlevel.auth.manager.TokenManager") as MockTM, \
         patch("maxlevel.api.GHLClient") as MockClient:
        MockTM.return_value.has_valid_token.return_value = True
        MockClient.from_session.return_value = MagicMock()
        result = await get_ghl_client()
        MockClient.from_session.assert_called_once()
        assert result is not None


@pytest.mark.asyncio
async def test_fetch_forms():
    """fetch_forms calls GHL forms.list with location_id."""
    mock_ghl = AsyncMock()
    mock_ghl.forms.list.return_value = {"forms": [{"_id": "f1", "name": "Contact Form"}]}
    mock_ghl.__aenter__ = AsyncMock(return_value=mock_ghl)
    mock_ghl.__aexit__ = AsyncMock(return_value=False)

    with patch("crm.services.ghl_svc.get_ghl_client", return_value=mock_ghl):
        result = await fetch_forms("loc123")
    assert result["forms"][0]["name"] == "Contact Form"
    mock_ghl.forms.list.assert_called_once_with(location_id="loc123")


@pytest.mark.asyncio
async def test_fetch_form_submissions():
    """fetch_form_submissions passes pagination params."""
    mock_ghl = AsyncMock()
    mock_ghl.forms.submissions.return_value = {"submissions": [], "meta": {"total": 0}}
    mock_ghl.__aenter__ = AsyncMock(return_value=mock_ghl)
    mock_ghl.__aexit__ = AsyncMock(return_value=False)

    with patch("crm.services.ghl_svc.get_ghl_client", return_value=mock_ghl):
        result = await fetch_form_submissions("f1", "loc123", page=2, limit=25)
    mock_ghl.forms.submissions.assert_called_once_with("f1", limit=25, page=2, location_id="loc123")


@pytest.mark.asyncio
async def test_fetch_calendars():
    """fetch_calendars calls GHL calendars.list."""
    mock_ghl = AsyncMock()
    mock_ghl.calendars.list.return_value = {"calendars": [{"id": "c1", "name": "Main"}]}
    mock_ghl.__aenter__ = AsyncMock(return_value=mock_ghl)
    mock_ghl.__aexit__ = AsyncMock(return_value=False)

    with patch("crm.services.ghl_svc.get_ghl_client", return_value=mock_ghl):
        result = await fetch_calendars("loc123")
    assert len(result["calendars"]) == 1


@pytest.mark.asyncio
async def test_fetch_conversations():
    """fetch_conversations passes unread_only flag."""
    mock_ghl = AsyncMock()
    mock_ghl.conversations.list.return_value = {"conversations": [], "total": 0}
    mock_ghl.__aenter__ = AsyncMock(return_value=mock_ghl)
    mock_ghl.__aexit__ = AsyncMock(return_value=False)

    with patch("crm.services.ghl_svc.get_ghl_client", return_value=mock_ghl):
        await fetch_conversations("loc123", unread_only=True)
    mock_ghl.conversations.list.assert_called_once_with(
        limit=20, unread_only=True, location_id="loc123",
    )
