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
    EXAMPLE_FLASHCARDS,
    MATUSCHAK_PRINCIPLES,
    SERVER_INSTRUCTIONS,
    _add_attachment_impl,
    _create_cards_impl,
    _create_deck_impl,
    _fetch_url_impl,
    _get_card_impl,
    _list_cards_impl,
    _list_decks_impl,
    _update_card_impl,
    _update_deck_impl,
    add_attachment,
    create_cards,
    create_deck,
    fetch_url,
    generate_flashcards,
    get_card,
    get_examples,
    get_principles,
    list_cards,
    list_decks,
    main,
    mcp,
    review_flashcards,
    update_card,
    update_deck,
)


class TestResources:
    """Test MCP resources are properly defined."""

    async def test_principles_resource_exists(self):
        """Verify the matuschak://principles resource is registered."""
        assert await mcp.get_resource("matuschak://principles") is not None

    async def test_examples_resource_exists(self):
        """Verify the matuschak://examples resource is registered."""
        assert await mcp.get_resource("matuschak://examples") is not None

    def test_principles_content(self):
        """Verify principles resource contains key content."""
        assert "Focused" in MATUSCHAK_PRINCIPLES
        assert "Precise" in MATUSCHAK_PRINCIPLES
        assert "Tractable" in MATUSCHAK_PRINCIPLES
        assert "Effortful" in MATUSCHAK_PRINCIPLES
        assert "Consistent" in MATUSCHAK_PRINCIPLES

    def test_principles_resource_returns_content(self):
        """Invoke the principles resource fn to cover its body.

        Under FastMCP 3.x the @mcp.resource decorator returns the original
        function unchanged, so it can be called directly.
        """
        assert get_principles() == MATUSCHAK_PRINCIPLES

    def test_examples_resource_returns_content(self):
        """Invoke the examples resource fn to cover its body."""
        assert get_examples() == EXAMPLE_FLASHCARDS


class TestPrompts:
    """Test MCP prompts are properly defined."""

    async def test_generate_flashcards_prompt_exists(self):
        """Verify generate_flashcards prompt is registered."""
        assert await mcp.get_prompt("generate_flashcards") is not None

    async def test_review_flashcards_prompt_exists(self):
        """Verify review_flashcards prompt is registered."""
        assert await mcp.get_prompt("review_flashcards") is not None

    def test_generate_flashcards_prompt_renders(self):
        """Invoke the generate_flashcards prompt fn to cover its body.

        Under FastMCP 3.x the @mcp.prompt decorator returns the original
        function unchanged, so it can be called directly.
        """
        rendered = generate_flashcards(content="hello world", topic="greetings")
        assert "hello world" in rendered
        assert "greetings" in rendered

    def test_generate_flashcards_prompt_default_topic(self):
        """Default topic should appear in the rendered prompt."""
        rendered = generate_flashcards(content="body")
        assert "the article" in rendered

    def test_review_flashcards_prompt_renders(self):
        """Invoke the review_flashcards prompt fn to cover its body."""
        rendered = review_flashcards(cards='[{"q": "a"}]')
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
            "docs": [{"id": "deck-1", "name": "Python"}, {"id": "deck-2", "name": "JavaScript"}]
        }

        # Mochi's router requires the trailing slash: /api/decks/ 200s while
        # /api/decks 404s even with a valid key.
        route = respx.get("https://app.mochi.cards/api/decks/").mock(
            return_value=Response(200, json=mock_response)
        )

        result = await _list_decks_impl()

        assert route.calls.last.request.url.path == "/api/decks/"
        assert "Python: deck-1" in result
        assert "JavaScript: deck-2" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_decks_empty(self, monkeypatch):
        """Test empty deck list."""
        monkeypatch.setenv("MOCHI_API_KEY", "test-key")

        respx.get("https://app.mochi.cards/api/decks/").mock(
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

        respx.post("https://app.mochi.cards/api/cards/").mock(
            return_value=Response(200, json={"id": "card-123"})
        )

        cards = [
            {"question": "What is Python?", "answer": "A programming language"},
            {"question": "What is HTTP?", "answer": "HyperText Transfer Protocol"},
        ]

        result = await _create_cards_impl("deck-1", cards)

        assert "Created 2/2 cards" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_cards_request_payload(self, monkeypatch):
        """Card creation sends the documented Mochi payload and Basic auth."""
        import base64
        import json

        monkeypatch.setenv("MOCHI_API_KEY", "test-key")

        route = respx.post("https://app.mochi.cards/api/cards/").mock(
            return_value=Response(200, json={"id": "card-123"})
        )

        cards = [{"question": "Q1", "answer": "A1", "tags": ["python", "basics"]}]

        await _create_cards_impl("deck-1", cards)

        request = route.calls.last.request
        body = json.loads(request.content)

        # Mochi's router requires the trailing slash on /api/cards/.
        assert request.url.path == "/api/cards/"

        # Tags use Mochi's "manual-tags" key.
        assert body["manual-tags"] == ["python", "basics"]
        # Two-sided cards encode front/back in a single markdown content field
        # separated by "---".
        assert body["content"] == "Q1\n---\nA1"
        assert body["deck-id"] == "deck-1"

        # Mochi uses HTTP Basic auth with the API key as the username.
        auth_header = request.headers["Authorization"]
        assert auth_header.startswith("Basic ")
        decoded = base64.b64decode(auth_header.split(" ", 1)[1]).decode()
        assert decoded == "test-key:"

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
        route = respx.post("https://app.mochi.cards/api/cards/")
        route.side_effect = [
            Response(200, json={"id": "card-1"}),
            Response(400, text="Invalid card"),
        ]

        cards = [{"question": "Q1", "answer": "A1"}, {"question": "Q2", "answer": "A2"}]

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

        respx.post("https://app.mochi.cards/api/cards/").mock(
            side_effect=httpx.ConnectError("boom")
        )

        result = await _create_cards_impl("deck-1", [{"question": "Q1", "answer": "A1"}])

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


class TestListCardsTool:
    """Test the list_cards tool implementation."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_cards_success(self, monkeypatch):
        """Test successful card listing with a bookmark for pagination."""
        monkeypatch.setenv("MOCHI_API_KEY", "test-key")

        mock_response = {
            "docs": [
                {"id": "card-1", "content": "What is Python?\n---\nA language"},
                {"id": "card-2", "content": "What is HTTP?\n---\nA protocol"},
            ],
            "bookmark": "next-page-token",
        }

        route = respx.get("https://app.mochi.cards/api/cards/").mock(
            return_value=Response(200, json=mock_response)
        )

        result = await _list_cards_impl()

        assert route.calls.last.request.url.path == "/api/cards/"
        assert "card-1: What is Python?" in result
        assert "card-2: What is HTTP?" in result
        assert "next-page-token" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_cards_no_bookmark_in_response(self, monkeypatch):
        """When the response has no bookmark, no pagination line is appended."""
        monkeypatch.setenv("MOCHI_API_KEY", "test-key")

        respx.get("https://app.mochi.cards/api/cards/").mock(
            return_value=Response(200, json={"docs": [{"id": "card-1", "content": "Q\n---\nA"}]})
        )

        result = await _list_cards_impl()

        assert "card-1: Q" in result
        assert "bookmark" not in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_cards_filters_and_pagination_params(self, monkeypatch):
        """deck_id, limit, and bookmark are sent as query params."""
        monkeypatch.setenv("MOCHI_API_KEY", "test-key")

        route = respx.get("https://app.mochi.cards/api/cards/").mock(
            return_value=Response(200, json={"docs": []})
        )

        await _list_cards_impl(deck_id="deck-1", limit=10, bookmark="cursor-1")

        request = route.calls.last.request
        assert request.url.params["deck-id"] == "deck-1"
        assert request.url.params["limit"] == "10"
        assert request.url.params["bookmark"] == "cursor-1"

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_cards_empty(self, monkeypatch):
        """Test empty card list."""
        monkeypatch.setenv("MOCHI_API_KEY", "test-key")

        respx.get("https://app.mochi.cards/api/cards/").mock(
            return_value=Response(200, json={"docs": []})
        )

        result = await _list_cards_impl()

        assert "No cards found" in result

    @pytest.mark.asyncio
    async def test_list_cards_no_api_key(self, monkeypatch):
        """Test error when API key is not set."""
        monkeypatch.delenv("MOCHI_API_KEY", raising=False)

        with pytest.raises(ValueError, match="MOCHI_API_KEY"):
            await _list_cards_impl()


class TestGetCardTool:
    """Test the get_card tool implementation."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_card_success(self, monkeypatch):
        """Test fetching a single card's full content, deck-id, and tags."""
        monkeypatch.setenv("MOCHI_API_KEY", "test-key")

        mock_card = {
            "id": "card-1",
            "content": "What is Python?\n---\nA language",
            "deck-id": "deck-1",
            "tags": ["python"],
            "manual-tags": ["basics"],
        }

        route = respx.get("https://app.mochi.cards/api/cards/card-1").mock(
            return_value=Response(200, json=mock_card)
        )

        result = await _get_card_impl("card-1")

        assert route.calls.last.request.url.path == "/api/cards/card-1"
        assert "card-1" in result
        assert "deck-1" in result
        assert "python" in result
        assert "basics" in result
        assert "What is Python?\n---\nA language" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_card_no_tags(self, monkeypatch):
        """Test a card with no tags at all."""
        monkeypatch.setenv("MOCHI_API_KEY", "test-key")

        mock_card = {"id": "card-1", "content": "Q\n---\nA", "deck-id": "deck-1"}

        respx.get("https://app.mochi.cards/api/cards/card-1").mock(
            return_value=Response(200, json=mock_card)
        )

        result = await _get_card_impl("card-1")

        assert "none" in result

    @pytest.mark.asyncio
    async def test_get_card_no_api_key(self, monkeypatch):
        """Test error when API key is not set."""
        monkeypatch.delenv("MOCHI_API_KEY", raising=False)

        with pytest.raises(ValueError, match="MOCHI_API_KEY"):
            await _get_card_impl("card-1")


class TestUpdateCardTool:
    """Test the update_card tool implementation."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_update_card_content(self, monkeypatch):
        """Only provided fields are sent, mapped to Mochi's kebab-case names."""
        monkeypatch.setenv("MOCHI_API_KEY", "test-key")

        route = respx.post("https://app.mochi.cards/api/cards/card-1").mock(
            return_value=Response(200, json={"id": "card-1"})
        )

        result = await _update_card_impl("card-1", content="New content")

        import json

        body = json.loads(route.calls.last.request.content)
        assert body == {"content": "New content"}
        assert "Updated card card-1" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_update_card_all_fields(self, monkeypatch):
        """All updatable fields map to Mochi's kebab-case field names."""
        monkeypatch.setenv("MOCHI_API_KEY", "test-key")

        route = respx.post("https://app.mochi.cards/api/cards/card-1").mock(
            return_value=Response(200, json={"id": "card-1"})
        )

        await _update_card_impl(
            "card-1",
            content="Q\n---\nA",
            deck_id="deck-2",
            manual_tags=["python"],
            archived=True,
        )

        import json

        body = json.loads(route.calls.last.request.content)
        assert body["content"] == "Q\n---\nA"
        assert body["deck-id"] == "deck-2"
        assert body["manual-tags"] == ["python"]
        assert body["archived?"] is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_update_card_trashed_true_sends_timestamp(self, monkeypatch):
        """trashed=True is sent as an ISO 8601 timestamp, not a boolean."""
        monkeypatch.setenv("MOCHI_API_KEY", "test-key")

        route = respx.post("https://app.mochi.cards/api/cards/card-1").mock(
            return_value=Response(200, json={"id": "card-1"})
        )

        await _update_card_impl("card-1", trashed=True)

        import json

        body = json.loads(route.calls.last.request.content)
        assert isinstance(body["trashed?"], str)
        assert body["trashed?"].endswith("Z")

    @respx.mock
    @pytest.mark.asyncio
    async def test_update_card_trashed_false_clears_timestamp(self, monkeypatch):
        """trashed=False untrashes the card by clearing the timestamp field."""
        monkeypatch.setenv("MOCHI_API_KEY", "test-key")

        route = respx.post("https://app.mochi.cards/api/cards/card-1").mock(
            return_value=Response(200, json={"id": "card-1"})
        )

        await _update_card_impl("card-1", trashed=False)

        import json

        body = json.loads(route.calls.last.request.content)
        assert body["trashed?"] is None

    @pytest.mark.asyncio
    async def test_update_card_no_fields(self, monkeypatch):
        """Calling with no fields to update is a no-op that reports back."""
        monkeypatch.setenv("MOCHI_API_KEY", "test-key")

        result = await _update_card_impl("card-1")

        assert "No fields provided" in result

    @pytest.mark.asyncio
    async def test_update_card_no_api_key(self, monkeypatch):
        """Test error when API key is not set."""
        monkeypatch.delenv("MOCHI_API_KEY", raising=False)

        with pytest.raises(ValueError, match="MOCHI_API_KEY"):
            await _update_card_impl("card-1", content="x")


class TestCreateDeckTool:
    """Test the create_deck tool implementation."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_deck_success(self, monkeypatch):
        """Test successful deck creation."""
        monkeypatch.setenv("MOCHI_API_KEY", "test-key")

        route = respx.post("https://app.mochi.cards/api/decks/").mock(
            return_value=Response(200, json={"id": "deck-1", "name": "Python"})
        )

        result = await _create_deck_impl("Python")

        assert route.calls.last.request.url.path == "/api/decks/"
        import json

        body = json.loads(route.calls.last.request.content)
        assert body == {"name": "Python"}
        assert "Python" in result
        assert "deck-1" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_deck_with_parent(self, monkeypatch):
        """parent_id maps to Mochi's parent-id field."""
        monkeypatch.setenv("MOCHI_API_KEY", "test-key")

        route = respx.post("https://app.mochi.cards/api/decks/").mock(
            return_value=Response(200, json={"id": "deck-2", "name": "Subdeck"})
        )

        await _create_deck_impl("Subdeck", parent_id="deck-1")

        import json

        body = json.loads(route.calls.last.request.content)
        assert body["parent-id"] == "deck-1"

    @pytest.mark.asyncio
    async def test_create_deck_no_api_key(self, monkeypatch):
        """Test error when API key is not set."""
        monkeypatch.delenv("MOCHI_API_KEY", raising=False)

        with pytest.raises(ValueError, match="MOCHI_API_KEY"):
            await _create_deck_impl("Python")


class TestUpdateDeckTool:
    """Test the update_deck tool implementation."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_update_deck_fields(self, monkeypatch):
        """Only provided fields are sent, mapped to Mochi's kebab-case names."""
        monkeypatch.setenv("MOCHI_API_KEY", "test-key")

        route = respx.post("https://app.mochi.cards/api/decks/deck-1").mock(
            return_value=Response(200, json={"id": "deck-1"})
        )

        result = await _update_deck_impl(
            "deck-1", name="Renamed", parent_id="deck-0", archived=True
        )

        import json

        body = json.loads(route.calls.last.request.content)
        assert body == {"name": "Renamed", "parent-id": "deck-0", "archived?": True}
        assert "Updated deck deck-1" in result

    @pytest.mark.asyncio
    async def test_update_deck_no_fields(self, monkeypatch):
        """Calling with no fields to update is a no-op that reports back."""
        monkeypatch.setenv("MOCHI_API_KEY", "test-key")

        result = await _update_deck_impl("deck-1")

        assert "No fields provided" in result

    @pytest.mark.asyncio
    async def test_update_deck_no_api_key(self, monkeypatch):
        """Test error when API key is not set."""
        monkeypatch.delenv("MOCHI_API_KEY", raising=False)

        with pytest.raises(ValueError, match="MOCHI_API_KEY"):
            await _update_deck_impl("deck-1", name="x")


class TestAddAttachmentTool:
    """Test the add_attachment tool implementation."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_add_attachment_success(self, monkeypatch, tmp_path):
        """Test successful attachment upload, inferring filename and content-type."""
        monkeypatch.setenv("MOCHI_API_KEY", "test-key")

        image_path = tmp_path / "diagram.png"
        image_path.write_bytes(b"fake-png-bytes")

        route = respx.post("https://app.mochi.cards/api/cards/card-1/attachments/diagram.png").mock(
            return_value=Response(200, json={})
        )

        result = await _add_attachment_impl("card-1", str(image_path))

        assert route.calls.last.request.url.path == ("/api/cards/card-1/attachments/diagram.png")
        assert "diagram.png" in result
        assert "@media/diagram.png" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_add_attachment_custom_filename(self, monkeypatch, tmp_path):
        """An explicit filename overrides the file's basename."""
        monkeypatch.setenv("MOCHI_API_KEY", "test-key")

        image_path = tmp_path / "source.jpg"
        image_path.write_bytes(b"fake-jpg-bytes")

        route = respx.post("https://app.mochi.cards/api/cards/card-1/attachments/renamed.jpg").mock(
            return_value=Response(200, json={})
        )

        result = await _add_attachment_impl("card-1", str(image_path), filename="renamed.jpg")

        assert route.calls.last.request.url.path == ("/api/cards/card-1/attachments/renamed.jpg")
        assert "renamed.jpg" in result

    @pytest.mark.asyncio
    async def test_add_attachment_file_not_found(self, monkeypatch, tmp_path):
        """Test validation error when the file doesn't exist."""
        monkeypatch.setenv("MOCHI_API_KEY", "test-key")

        missing_path = tmp_path / "missing.png"

        with pytest.raises(ValueError, match="File not found"):
            await _add_attachment_impl("card-1", str(missing_path))

    @pytest.mark.asyncio
    async def test_add_attachment_unsupported_extension(self, monkeypatch, tmp_path):
        """Test validation error for an unsupported file extension."""
        monkeypatch.setenv("MOCHI_API_KEY", "test-key")

        bad_path = tmp_path / "document.pdf"
        bad_path.write_bytes(b"fake-pdf-bytes")

        with pytest.raises(ValueError, match="Unsupported attachment extension"):
            await _add_attachment_impl("card-1", str(bad_path))

    @pytest.mark.asyncio
    async def test_add_attachment_no_api_key(self, monkeypatch, tmp_path):
        """Test error when API key is not set (validated after file checks)."""
        monkeypatch.delenv("MOCHI_API_KEY", raising=False)

        image_path = tmp_path / "diagram.png"
        image_path.write_bytes(b"fake-png-bytes")

        with pytest.raises(ValueError, match="MOCHI_API_KEY"):
            await _add_attachment_impl("card-1", str(image_path))


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

    def test_server_version_is_single_sourced_and_advertised(self):
        """The server advertises the package version from a single source.

        `__version__` is read from the installed package metadata
        (pyproject.toml) and passed to FastMCP, so the MCP handshake's
        serverInfo.version always matches the build.
        """
        from importlib.metadata import version as pkg_version

        from mochi_donut import __version__

        assert __version__ == pkg_version("mochi-donut")
        assert mcp.version == __version__

    async def test_tools_are_registered(self):
        """Verify all tools are registered."""
        assert await mcp.get_tool("fetch_url") is not None
        assert await mcp.get_tool("list_decks") is not None
        assert await mcp.get_tool("create_cards") is not None
        assert await mcp.get_tool("list_cards") is not None
        assert await mcp.get_tool("get_card") is not None
        assert await mcp.get_tool("update_card") is not None
        assert await mcp.get_tool("create_deck") is not None
        assert await mcp.get_tool("update_deck") is not None
        assert await mcp.get_tool("add_attachment") is not None


class TestToolWrappers:
    """Invoke the @mcp.tool wrapper functions directly to cover their bodies.

    Under FastMCP 3.x the @mcp.tool decorator returns the original function
    unchanged, so the wrappers imported from the module are directly callable.
    """

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_url_tool_wrapper(self):
        respx.get("https://r.jina.ai/https://example.com/x").mock(
            return_value=Response(200, text="ok")
        )
        assert await fetch_url("https://example.com/x") == "ok"

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_decks_tool_wrapper(self, monkeypatch):
        monkeypatch.setenv("MOCHI_API_KEY", "test-key")
        respx.get("https://app.mochi.cards/api/decks/").mock(
            return_value=Response(200, json={"docs": []})
        )
        assert "No decks found" in await list_decks()

    @pytest.mark.asyncio
    async def test_create_cards_tool_wrapper(self, monkeypatch):
        monkeypatch.setenv("MOCHI_API_KEY", "test-key")
        assert "No cards provided" in await create_cards("deck-1", [])

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_cards_tool_wrapper(self, monkeypatch):
        monkeypatch.setenv("MOCHI_API_KEY", "test-key")
        respx.get("https://app.mochi.cards/api/cards/").mock(
            return_value=Response(200, json={"docs": []})
        )
        assert "No cards found" in await list_cards()

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_card_tool_wrapper(self, monkeypatch):
        monkeypatch.setenv("MOCHI_API_KEY", "test-key")
        respx.get("https://app.mochi.cards/api/cards/card-1").mock(
            return_value=Response(
                200, json={"id": "card-1", "content": "Q\n---\nA", "deck-id": "d"}
            )
        )
        assert "card-1" in await get_card("card-1")

    @pytest.mark.asyncio
    async def test_update_card_tool_wrapper(self, monkeypatch):
        monkeypatch.setenv("MOCHI_API_KEY", "test-key")
        assert "No fields provided" in await update_card("card-1")

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_deck_tool_wrapper(self, monkeypatch):
        monkeypatch.setenv("MOCHI_API_KEY", "test-key")
        respx.post("https://app.mochi.cards/api/decks/").mock(
            return_value=Response(200, json={"id": "deck-1", "name": "Python"})
        )
        assert "deck-1" in await create_deck("Python")

    @pytest.mark.asyncio
    async def test_update_deck_tool_wrapper(self, monkeypatch):
        monkeypatch.setenv("MOCHI_API_KEY", "test-key")
        assert "No fields provided" in await update_deck("deck-1")

    @pytest.mark.asyncio
    async def test_add_attachment_tool_wrapper(self, monkeypatch, tmp_path):
        monkeypatch.delenv("MOCHI_API_KEY", raising=False)
        missing_path = tmp_path / "missing.png"
        with pytest.raises(ValueError, match="File not found"):
            await add_attachment("card-1", str(missing_path))


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
