# ABOUTME: Tests for Mochi Donut MCP server
# ABOUTME: Tests tools, resources, and prompts using respx for HTTP mocking
"""
Tests for the Mochi Donut MCP server.

Uses respx to mock HTTP requests to JinaAI and Mochi APIs.
Tests the core _impl functions directly since MCP tool decorators wrap them.
"""

import pytest
import respx
from httpx import Response

from mochi_donut.server import (
    mcp,
    MATUSCHAK_PRINCIPLES,
    SERVER_INSTRUCTIONS,
    _fetch_url_impl,
    _list_decks_impl,
    _create_cards_impl,
)


class TestResources:
    """Test MCP resources are properly defined."""

    def test_principles_resource_exists(self):
        """Verify the matuschak://principles resource is registered."""
        resources = mcp._resource_manager._resources
        assert "matuschak://principles" in resources

    def test_examples_resource_exists(self):
        """Verify the matuschak://examples resource is registered."""
        resources = mcp._resource_manager._resources
        assert "matuschak://examples" in resources

    def test_principles_content(self):
        """Verify principles resource contains key content."""
        assert "Focused" in MATUSCHAK_PRINCIPLES
        assert "Precise" in MATUSCHAK_PRINCIPLES
        assert "Tractable" in MATUSCHAK_PRINCIPLES
        assert "Effortful" in MATUSCHAK_PRINCIPLES
        assert "Consistent" in MATUSCHAK_PRINCIPLES


class TestPrompts:
    """Test MCP prompts are properly defined."""

    def test_generate_flashcards_prompt_exists(self):
        """Verify generate_flashcards prompt is registered."""
        prompts = mcp._prompt_manager._prompts
        assert "generate_flashcards" in prompts

    def test_review_flashcards_prompt_exists(self):
        """Verify review_flashcards prompt is registered."""
        prompts = mcp._prompt_manager._prompts
        assert "review_flashcards" in prompts


class TestFetchUrlTool:
    """Test the fetch_url tool implementation."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_url_success(self):
        """Test successful URL fetch."""
        mock_markdown = "# Test Article\n\nThis is test content."

        respx.get("https://r.jina.ai/https://example.com/article").mock(
            return_value=Response(200, text=mock_markdown)
        )

        result = await _fetch_url_impl("https://example.com/article")

        assert result == mock_markdown

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_url_concise_truncates(self):
        """Test that concise mode truncates long content."""
        long_content = "x" * 10000

        respx.get("https://r.jina.ai/https://example.com/long").mock(
            return_value=Response(200, text=long_content)
        )

        result = await _fetch_url_impl("https://example.com/long", format="concise")

        assert len(result) < len(long_content)
        assert "[Content truncated" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_url_full_mode(self):
        """Test that full mode returns complete content."""
        long_content = "x" * 10000

        respx.get("https://r.jina.ai/https://example.com/long").mock(
            return_value=Response(200, text=long_content)
        )

        result = await _fetch_url_impl("https://example.com/long", format="full")

        assert result == long_content

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_url_http_error(self):
        """Test handling of HTTP errors."""
        respx.get("https://r.jina.ai/https://example.com/404").mock(
            return_value=Response(404, text="Not found")
        )

        with pytest.raises(Exception):
            await _fetch_url_impl("https://example.com/404")


class TestListDecksTool:
    """Test the list_decks tool implementation."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_decks_success(self, monkeypatch):
        """Test successful deck listing."""
        monkeypatch.setenv("MOCHI_API_KEY", "test-key")

        mock_response = {
            "docs": [
                {"id": "deck-1", "name": "Python"},
                {"id": "deck-2", "name": "JavaScript"}
            ]
        }

        respx.get("https://app.mochi.cards/api/decks").mock(
            return_value=Response(200, json=mock_response)
        )

        result = await _list_decks_impl()

        assert "Python: deck-1" in result
        assert "JavaScript: deck-2" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_decks_empty(self, monkeypatch):
        """Test empty deck list."""
        monkeypatch.setenv("MOCHI_API_KEY", "test-key")

        respx.get("https://app.mochi.cards/api/decks").mock(
            return_value=Response(200, json={"docs": []})
        )

        result = await _list_decks_impl()

        assert "No decks found" in result

    @pytest.mark.asyncio
    async def test_list_decks_no_api_key(self, monkeypatch):
        """Test error when API key is not set."""
        monkeypatch.delenv("MOCHI_API_KEY", raising=False)

        with pytest.raises(ValueError, match="MOCHI_API_KEY"):
            await _list_decks_impl()


class TestCreateCardsTool:
    """Test the create_cards tool implementation."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_cards_success(self, monkeypatch):
        """Test successful card creation."""
        monkeypatch.setenv("MOCHI_API_KEY", "test-key")

        respx.post("https://app.mochi.cards/api/cards").mock(
            return_value=Response(200, json={"id": "card-123"})
        )

        cards = [
            {"question": "What is Python?", "answer": "A programming language"},
            {"question": "What is HTTP?", "answer": "HyperText Transfer Protocol"}
        ]

        result = await _create_cards_impl("deck-1", cards)

        assert "Created 2/2 cards" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_cards_with_tags(self, monkeypatch):
        """Test card creation with tags."""
        monkeypatch.setenv("MOCHI_API_KEY", "test-key")

        route = respx.post("https://app.mochi.cards/api/cards").mock(
            return_value=Response(200, json={"id": "card-123"})
        )

        cards = [
            {"question": "Q1", "answer": "A1", "tags": ["python", "basics"]}
        ]

        await _create_cards_impl("deck-1", cards)

        # Verify tags were included in request
        request = route.calls.last.request
        import json
        body = json.loads(request.content)
        assert body["tags"] == ["python", "basics"]

    @pytest.mark.asyncio
    async def test_create_cards_empty_list(self, monkeypatch):
        """Test handling of empty card list."""
        monkeypatch.setenv("MOCHI_API_KEY", "test-key")

        result = await _create_cards_impl("deck-1", [])

        assert "No cards provided" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_cards_partial_failure(self, monkeypatch):
        """Test handling when some cards fail."""
        monkeypatch.setenv("MOCHI_API_KEY", "test-key")

        # First card succeeds, second fails
        route = respx.post("https://app.mochi.cards/api/cards")
        route.side_effect = [
            Response(200, json={"id": "card-1"}),
            Response(400, text="Invalid card")
        ]

        cards = [
            {"question": "Q1", "answer": "A1"},
            {"question": "Q2", "answer": "A2"}
        ]

        result = await _create_cards_impl("deck-1", cards)

        assert "Created 1/2 cards" in result
        assert "Errors" in result

    @pytest.mark.asyncio
    async def test_create_cards_missing_fields(self, monkeypatch):
        """Test validation of card fields."""
        monkeypatch.setenv("MOCHI_API_KEY", "test-key")

        cards = [
            {"question": "Q1"},  # Missing answer
        ]

        result = await _create_cards_impl("deck-1", cards)

        assert "Missing question or answer" in result


class TestServerConfiguration:
    """Test server configuration."""

    def test_server_name(self):
        """Verify server name is set correctly."""
        assert mcp.name == "mochi-donut"

    def test_server_has_instructions(self):
        """Verify server has instructions for the agent."""
        assert SERVER_INSTRUCTIONS is not None
        assert "flashcard" in SERVER_INSTRUCTIONS.lower()
        assert "Matuschak" in SERVER_INSTRUCTIONS

    def test_tools_are_registered(self):
        """Verify all tools are registered."""
        tools = mcp._tool_manager._tools
        assert "fetch_url" in tools
        assert "list_decks" in tools
        assert "create_cards" in tools
