# ABOUTME: Tests for Mochi Donut MCP server
# ABOUTME: Tests tools, resources, and prompts using respx for HTTP mocking
"""
Tests for the Mochi Donut MCP server.

Uses respx to mock HTTP requests to JinaAI and Mochi APIs.
Tests the core _impl functions directly since MCP tool decorators wrap them.
"""

import runpy
from unittest.mock import patch

import httpx
import pytest
import respx
from httpx import Response

from mochi_donut.server import (
    mcp,
    EXAMPLE_FLASHCARDS,
    MATUSCHAK_PRINCIPLES,
    SERVER_INSTRUCTIONS,
    _fetch_url_impl,
    _list_decks_impl,
    _create_cards_impl,
    main,
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

    def test_principles_resource_returns_content(self):
        """Invoke the principles resource fn to cover its body."""
        principles = mcp._resource_manager._resources["matuschak://principles"]
        assert principles.fn() == MATUSCHAK_PRINCIPLES

    def test_examples_resource_returns_content(self):
        """Invoke the examples resource fn to cover its body."""
        examples = mcp._resource_manager._resources["matuschak://examples"]
        assert examples.fn() == EXAMPLE_FLASHCARDS


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

    def test_generate_flashcards_prompt_renders(self):
        """Invoke the generate_flashcards prompt fn to cover its body."""
        prompt = mcp._prompt_manager._prompts["generate_flashcards"]
        rendered = prompt.fn(content="hello world", topic="greetings")
        assert "hello world" in rendered
        assert "greetings" in rendered

    def test_generate_flashcards_prompt_default_topic(self):
        """Default topic should appear in the rendered prompt."""
        prompt = mcp._prompt_manager._prompts["generate_flashcards"]
        rendered = prompt.fn(content="body")
        assert "the article" in rendered

    def test_review_flashcards_prompt_renders(self):
        """Invoke the review_flashcards prompt fn to cover its body."""
        prompt = mcp._prompt_manager._prompts["review_flashcards"]
        rendered = prompt.fn(cards='[{"q": "a"}]')
        assert '[{"q": "a"}]' in rendered


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

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_cards_generic_exception(self, monkeypatch):
        """Non-HTTPStatusError exceptions are captured in the error list."""
        monkeypatch.setenv("MOCHI_API_KEY", "test-key")

        respx.post("https://app.mochi.cards/api/cards").mock(
            side_effect=httpx.ConnectError("boom")
        )

        result = await _create_cards_impl(
            "deck-1", [{"question": "Q1", "answer": "A1"}]
        )

        assert "Created 0/1 cards" in result
        assert "boom" in result

    @pytest.mark.asyncio
    async def test_create_cards_more_than_five_errors(self, monkeypatch):
        """When more than 5 cards fail, a summary line is appended."""
        monkeypatch.setenv("MOCHI_API_KEY", "test-key")

        # Seven cards all missing 'answer' triggers seven validation errors
        # without any HTTP traffic.
        cards = [{"question": f"Q{i}"} for i in range(7)]

        result = await _create_cards_impl("deck-1", cards)

        assert "Created 0/7 cards" in result
        assert "...and 2 more errors" in result


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


class TestToolWrappers:
    """Invoke the @mcp.tool wrapper functions directly to cover their bodies."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_url_tool_wrapper(self):
        respx.get("https://r.jina.ai/https://example.com/x").mock(
            return_value=Response(200, text="ok")
        )
        fetch_url = mcp._tool_manager._tools["fetch_url"].fn
        assert await fetch_url("https://example.com/x") == "ok"

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_decks_tool_wrapper(self, monkeypatch):
        monkeypatch.setenv("MOCHI_API_KEY", "test-key")
        respx.get("https://app.mochi.cards/api/decks").mock(
            return_value=Response(200, json={"docs": []})
        )
        list_decks = mcp._tool_manager._tools["list_decks"].fn
        assert "No decks found" in await list_decks()

    @pytest.mark.asyncio
    async def test_create_cards_tool_wrapper(self, monkeypatch):
        monkeypatch.setenv("MOCHI_API_KEY", "test-key")
        create_cards = mcp._tool_manager._tools["create_cards"].fn
        assert "No cards provided" in await create_cards("deck-1", [])


class TestEntryPoint:
    """Cover main() and the __main__ guard."""

    def test_main_invokes_mcp_run(self):
        with patch("mochi_donut.server.mcp.run") as run_mock:
            main()
        run_mock.assert_called_once_with()

    def test_module_run_as_main(self):
        """Executing the module as __main__ triggers main()."""
        # runpy re-executes the source, creating a fresh FastMCP instance,
        # so patch run() on the class to intercept any instance.
        from fastmcp import FastMCP
        with patch.object(FastMCP, "run") as run_mock:
            runpy.run_module("mochi_donut.server", run_name="__main__")
        run_mock.assert_called_once_with()
