"""Tests for AI Chat service and routes."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from workflows.app import app
from workflows.services import chat_svc


@pytest.mark.asyncio
async def test_chat_page(client: AsyncClient):
    resp = await client.get("/chat")
    assert resp.status_code == 200
    assert "AI Chat" in resp.text
    assert "MaxLevel AI" in resp.text


@pytest.mark.asyncio
async def test_chat_page_has_input(client: AsyncClient):
    resp = await client.get("/chat")
    assert 'id="chat-input"' in resp.text
    assert 'id="send-btn"' in resp.text


class TestToolDefinitions:
    def test_tools_are_list(self):
        assert isinstance(chat_svc.TOOLS, list)
        assert len(chat_svc.TOOLS) > 0

    def test_all_tools_have_required_fields(self):
        for tool in chat_svc.TOOLS:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool
            assert tool["input_schema"]["type"] == "object"

    def test_tool_names_unique(self):
        names = [t["name"] for t in chat_svc.TOOLS]
        assert len(names) == len(set(names))

    def test_expected_tools_present(self):
        names = {t["name"] for t in chat_svc.TOOLS}
        assert "list_contacts" in names
        assert "send_sms" in names
        assert "list_pipelines" in names
        assert "run_workflow" in names


class TestExecuteTool:
    @pytest.mark.asyncio
    async def test_unknown_tool(self):
        result = await chat_svc.execute_tool("nonexistent_tool", {})
        assert "error" in result
        assert "Unknown tool" in result["error"]

    @pytest.mark.asyncio
    async def test_list_contacts_dispatches(self):
        mock_client = MagicMock()
        mock_client.contacts = MagicMock()
        mock_client.contacts.list = AsyncMock(return_value={"contacts": []})
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.object(chat_svc, "_get_ghl_client", return_value=mock_client):
            result = await chat_svc.execute_tool("list_contacts", {"query": "John"})

        mock_client.contacts.list.assert_called_once_with(query="John", limit=20)
        assert result == {"contacts": []}

    @pytest.mark.asyncio
    async def test_add_tag_dispatches(self):
        mock_client = MagicMock()
        mock_client.contacts = MagicMock()
        mock_client.contacts.add_tag = AsyncMock(return_value={"success": True})
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.object(chat_svc, "_get_ghl_client", return_value=mock_client):
            result = await chat_svc.execute_tool(
                "add_tag", {"contact_id": "c1", "tag": "VIP"}
            )

        mock_client.contacts.add_tag.assert_called_once_with("c1", "VIP")

    @pytest.mark.asyncio
    async def test_send_sms_dispatches(self):
        mock_client = MagicMock()
        mock_client.conversations = MagicMock()
        mock_client.conversations.send_sms = AsyncMock(return_value={"sent": True})
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.object(chat_svc, "_get_ghl_client", return_value=mock_client):
            result = await chat_svc.execute_tool(
                "send_sms", {"contact_id": "c1", "message": "Hello!"}
            )

        mock_client.conversations.send_sms.assert_called_once_with("c1", "Hello!")

    @pytest.mark.asyncio
    async def test_execute_tool_catches_exceptions(self):
        with patch.object(
            chat_svc, "_get_ghl_client",
            side_effect=RuntimeError("Connection failed"),
        ):
            result = await chat_svc.execute_tool("list_contacts", {})

        assert "error" in result
        assert "Connection failed" in result["error"]

    @pytest.mark.asyncio
    async def test_list_workflows_returns_local(self, db):
        from workflows.services import workflow_svc
        await workflow_svc.create_workflow(db, name="Test WF")

        mock_session_ctx = MagicMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=db)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("workflows.database.async_session_factory", return_value=mock_session_ctx):
            result = await chat_svc.execute_tool("list_workflows", {})

        assert "workflows" in result
        assert len(result["workflows"]) == 1
        assert result["workflows"][0]["name"] == "Test WF"


class TestStreamChat:
    @pytest.mark.asyncio
    async def test_stream_missing_api_key(self):
        with patch.object(chat_svc.settings, "anthropic_api_key", ""):
            chunks = []
            async for chunk in chat_svc.stream_chat([{"role": "user", "content": "hi"}]):
                chunks.append(chunk)
            assert any(c["type"] == "error" for c in chunks)

    @pytest.mark.asyncio
    async def test_stream_missing_anthropic_package(self):
        import sys
        with patch.dict(sys.modules, {"anthropic": None}):
            with patch.object(chat_svc.settings, "anthropic_api_key", "sk-test"):
                chunks = []
                async for chunk in chat_svc.stream_chat([{"role": "user", "content": "hi"}]):
                    chunks.append(chunk)
                assert any(c["type"] == "error" for c in chunks)


@pytest.mark.asyncio
async def test_chat_send_endpoint(client: AsyncClient):
    """Test the POST /chat/send endpoint returns SSE stream."""
    # Mock the stream_chat to yield a simple response
    async def mock_stream(messages, system=None):
        yield {"type": "text", "content": "Hello!"}
        yield {"type": "done"}

    with patch.object(chat_svc, "stream_chat", side_effect=mock_stream):
        resp = await client.post(
            "/chat/send",
            json={"messages": [{"role": "user", "content": "hi"}]},
        )

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    assert 'data: {"type": "text", "content": "Hello!"}' in resp.text
    assert 'data: {"type": "done"}' in resp.text
