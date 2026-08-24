# ABOUTME: MCP server for Mochi Donut flashcard generation
# ABOUTME: Provides tools, resources, and prompts for URL→flashcard workflows
"""
Mochi Donut MCP Server

A focused MCP server for converting web content into high-quality Mochi flashcards
following Andy Matuschak's spaced repetition principles.

Components:
- Tools: fetch_url, list_decks, create_cards, list_cards, get_card,
  update_card, create_deck, update_deck, add_attachment
- Resources: Matuschak's principles, example flashcards
- Prompts: Flashcard generation workflow

Installation in Claude Code:
    Add to ~/.claude/settings.json under mcpServers:
    {
        "mochi-donut": {
            "command": "uv",
            "args": ["run", "--directory", "/path/to/mochi_donut", "python", "-m", "mochi_donut.server"]
        }
    }

Or run directly: uv run python -m mochi_donut.server
"""

import os
import re
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import httpx
from fastmcp import FastMCP

# Single source of truth for the version: read it from the installed package
# metadata (defined in pyproject.toml) so it never drifts from the build.
__version__ = version("mochi-donut")

# Configuration
JINA_READER_BASE = "https://r.jina.ai"
MOCHI_API_BASE = "https://app.mochi.cards/api"

# Bounds the /decks/ pagination walk so a cursor that never resolves fails
# loudly instead of hanging the tool call.
MAX_DECK_PAGES = 100

# Attachment types this server accepts. Mochi itself takes more than these
# (its own docs example uploads an mp3); the narrowing is ours.
ATTACHMENT_CONTENT_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "svg": "image/svg+xml",
    "webp": "image/webp",
}

# Server instructions for the agent
SERVER_INSTRUCTIONS = """You are a flashcard generation assistant. Your goal is to help users
convert web content into high-quality Mochi flashcards following Andy Matuschak's principles.

Typical workflow:
1. User provides a URL
2. Use fetch_url to get the content as markdown
3. Read the matuschak://principles resource to understand good flashcard design
4. Generate flashcards following those principles
5. Use list_decks to find the target deck
6. Use create_cards to save the flashcards to Mochi

You can also manage existing cards and decks: list_cards and get_card to
browse and inspect, update_card to edit content/tags/deck/archived/trashed
status, create_deck and update_deck to manage decks, and add_attachment to
attach an image file to a card.

Always prioritize understanding over memorization. Create focused, specific prompts."""

# Initialize the MCP server
mcp = FastMCP("mochi-donut", instructions=SERVER_INSTRUCTIONS, version=__version__)


def _get_mochi_api_key() -> str:
    """Get Mochi API key from environment, raising if not set."""
    key = os.getenv("MOCHI_API_KEY")
    if not key:
        raise ValueError(
            "MOCHI_API_KEY not set. Get your API key from https://app.mochi.cards/settings/api"
        )
    return key


# =============================================================================
# RESOURCES - Static data for LLM context
# =============================================================================

MATUSCHAK_PRINCIPLES = """# Andy Matuschak's Principles for Effective Flashcards

## Core Philosophy
Spaced repetition systems work best when prompts are designed to reinforce understanding,
not just memorization. Each card should build genuine knowledge.

## The Five Properties of Effective Prompts

### 1. Focused
Each prompt should test ONE idea. If you find yourself writing "and" in a question,
split it into multiple cards.

Bad: "What is Python and when was it created?"
Good: "What programming paradigm is Python primarily designed for?"

### 2. Precise
Questions should have ONE unambiguous answer. Avoid vague questions that could have
multiple valid interpretations.

Bad: "What is important about HTTP?"
Good: "What does the 'S' in HTTPS stand for?"

### 3. Consistent
The same prompt should always retrieve the same knowledge. Avoid context-dependent
questions where the answer might vary.

Bad: "What should you do first?" (First in what context?)
Good: "What is the first step in the Git commit workflow?"

### 4. Tractable
You should be able to answer within a few seconds. If a prompt requires extensive
reasoning, break it into prerequisite cards.

Bad: "Derive the quadratic formula"
Good: "What is the quadratic formula for solving ax² + bx + c = 0?"

### 5. Effortful
Prompts should require genuine recall, not pattern matching. The answer shouldn't
be obvious from the question's structure.

Bad: "The ___ pattern separates data from presentation" (too easy to guess)
Good: "Which design pattern separates data storage from UI rendering?"

## Prompt Types to Use

1. **Conceptual**: Test understanding of ideas and relationships
   "Why does Python use indentation for code blocks?"

2. **Factual**: Test specific facts worth remembering
   "What HTTP status code indicates 'Not Found'?"

3. **Procedural**: Test sequences and processes
   "What command stages all modified files in Git?"

4. **Comparative**: Test distinctions between related concepts
   "How does a list differ from a tuple in Python?"

## Anti-Patterns to Avoid

- **Orphan cards**: Cards that don't connect to other knowledge
- **Leech cards**: Cards you consistently fail (indicates poor design)
- **Passive cards**: Cards you can answer without real understanding
- **Kitchen sink cards**: Cards trying to test too much at once

## Quantity Guidelines

- 5-15 cards per article/concept is typical
- Prefer more atomic cards over fewer complex ones
- Not everything needs a card—focus on what's worth remembering long-term
"""

EXAMPLE_FLASHCARDS = """# Example Flashcards: Good vs Bad

## Example 1: Python Basics

### Bad Card
Q: Tell me about Python lists
A: Lists are mutable sequences that can hold items of different types...
(Too vague, answer is too long)

### Good Cards
Q: Are Python lists mutable or immutable?
A: Mutable

Q: What method adds an item to the end of a Python list?
A: append()

Q: What happens when you access list[-1] in Python?
A: Returns the last element of the list

## Example 2: HTTP Protocol

### Bad Card
Q: Explain HTTP
A: HTTP is a protocol for transferring hypertext...
(Too broad, tests nothing specific)

### Good Cards
Q: What does HTTP stand for?
A: HyperText Transfer Protocol

Q: Is HTTP stateless or stateful?
A: Stateless

Q: What HTTP method is used to retrieve data without modifying it?
A: GET

## Example 3: Git Workflow

### Bad Card
Q: How do you use Git?
A: First you init, then add, commit, push...
(Too procedural, no real understanding tested)

### Good Cards
Q: What is the purpose of the Git staging area?
A: To prepare and review changes before committing them

Q: What's the difference between git pull and git fetch?
A: fetch downloads changes without merging; pull fetches AND merges

Q: Why might you use 'git stash'?
A: To temporarily save uncommitted changes when switching branches
"""


@mcp.resource("matuschak://principles")
def get_principles() -> str:
    """
    Andy Matuschak's principles for writing effective flashcards.
    Read this before generating any flashcards.
    """
    return MATUSCHAK_PRINCIPLES


@mcp.resource("matuschak://examples")
def get_examples() -> str:
    """
    Examples of good and bad flashcards to guide generation.
    """
    return EXAMPLE_FLASHCARDS


# =============================================================================
# PROMPTS - Reusable workflow templates
# =============================================================================


@mcp.prompt
def generate_flashcards(content: str, topic: str = "the article") -> str:
    """
    Generate flashcards from content following Matuschak's principles.

    Args:
        content: The markdown content to create flashcards from
        topic: Brief description of what the content is about
    """
    return f"""Please generate high-quality flashcards from the following content about {topic}.

Before generating, recall Andy Matuschak's principles:
- Each card should be FOCUSED (one idea), PRECISE (unambiguous), and TRACTABLE (answerable quickly)
- Prefer understanding over memorization
- Aim for 5-15 cards depending on content density

For each flashcard, provide:
- question: The prompt (front of card)
- answer: The response (back of card)
- tags: Relevant topic tags

Content to process:
---
{content}
---

Generate the flashcards now, formatted as a list I can pass to create_cards."""


@mcp.prompt
def review_flashcards(cards: str) -> str:
    """
    Review and improve draft flashcards before sending to Mochi.

    Args:
        cards: JSON string of draft flashcards to review
    """
    return f"""Please review these draft flashcards against Matuschak's principles.

For each card, check:
1. Is it FOCUSED? (Tests one idea only)
2. Is it PRECISE? (Has one clear answer)
3. Is it TRACTABLE? (Can be answered in seconds)
4. Does it test UNDERSTANDING, not just recall?

Draft cards:
---
{cards}
---

For any cards that need improvement:
1. Explain what's wrong
2. Provide a revised version

Then output the final approved list ready for create_cards."""


# =============================================================================
# CORE FUNCTIONS - Business logic (testable independently)
# =============================================================================


async def _fetch_url_impl(url: str, format: str = "concise") -> str:
    """
    Core implementation for fetching URL content.

    Args:
        url: The full URL to fetch
        format: Response format - "concise" (default) or "full"

    Returns:
        The article content as markdown
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{JINA_READER_BASE}/{url}",
            headers={"Accept": "text/markdown", "X-Return-Format": "markdown"},
        )
        response.raise_for_status()

        content = response.text

        # Token efficiency: truncate for concise mode
        if format == "concise" and len(content) > 8000:
            content = (
                content[:8000] + "\n\n[Content truncated. Use format='full' for complete text.]"
            )

        return content


async def _list_decks_impl() -> str:
    """
    Core implementation for listing Mochi decks.

    Returns every deck, following Mochi's bookmark cursor across pages.

    Returns:
        Formatted list of deck names and IDs
    """
    api_key = _get_mochi_api_key()

    lines: list[str] = []
    seen: set[str] = set()
    bookmark: str | None = None

    # Mochi uses HTTP Basic auth: API key as username, blank password.
    async with httpx.AsyncClient(auth=(api_key, "")) as client:
        for _ in range(MAX_DECK_PAGES):
            params = {"bookmark": bookmark} if bookmark is not None else {}
            # Mochi's router 404s without the trailing slash (observed 2026-07-17
            # in 5040ab5; their docs' own examples omit it and are wrong).
            response = await client.get(f"{MOCHI_API_BASE}/decks/", params=params)
            response.raise_for_status()

            page = response.json()
            if "docs" not in page:
                raise RuntimeError(
                    f"Mochi returned {response.status_code} for /decks/ with no 'docs' "
                    f"field, so the API contract may have changed. "
                    f"Body: {response.text[:500]}"
                )

            fresh = [deck for deck in page["docs"] if deck["id"] not in seen]
            seen.update(deck["id"] for deck in fresh)
            lines.extend(f"{deck['name']}: {deck['id']}" for deck in fresh)

            # Mochi: "Not every request that returns a bookmark has additional
            # pages", so the cursor alone cannot say when to stop. A page that
            # carries no deck we have not already seen ends the walk, which also
            # keeps a stalled or cycling cursor from repeating decks forever.
            next_bookmark = page.get("bookmark")
            if not fresh or not next_bookmark:
                break
            bookmark = next_bookmark
        else:
            raise RuntimeError(
                f"Gave up after {MAX_DECK_PAGES} pages of /decks/ without reaching the "
                f"end of Mochi's bookmark cursor, so the deck list would be incomplete "
                f"({len(lines)} decks collected)."
            )

    return "\n".join(lines) if lines else "No decks found. Create one at mochi.cards first."


async def _create_cards_impl(deck_id: str, cards: list[dict]) -> str:
    """
    Core implementation for creating cards in Mochi.

    Args:
        deck_id: The Mochi deck ID
        cards: List of card objects with question/answer/tags

    Returns:
        Summary of created cards
    """
    api_key = _get_mochi_api_key()

    if not cards:
        return "No cards provided. Generate some flashcards first."

    created_count = 0
    errors = []

    # Mochi uses HTTP Basic auth: API key as username, blank password.
    async with httpx.AsyncClient(auth=(api_key, "")) as client:
        for i, card in enumerate(cards):
            if "question" not in card or "answer" not in card:
                errors.append(f"Card {i + 1}: Missing question or answer")
                continue

            try:
                # Mochi renders a two-sided card from a single markdown `content`
                # field, with the "---" separator dividing front (question) from
                # back (answer). This works for any deck without needing a template.
                # Mochi's router 404s without the trailing slash.
                response = await client.post(
                    f"{MOCHI_API_BASE}/cards/",
                    json={
                        "deck-id": deck_id,
                        "content": f"{card['question']}\n---\n{card['answer']}",
                        "manual-tags": card.get("tags", []),
                    },
                )
                response.raise_for_status()
                created_count += 1
            except httpx.HTTPStatusError as e:
                errors.append(f"Card {i + 1}: {e.response.status_code} - {e.response.text[:100]}")
            except Exception as e:
                errors.append(f"Card {i + 1}: {str(e)}")

    result = f"Created {created_count}/{len(cards)} cards"
    if errors:
        result += "\nErrors:\n" + "\n".join(errors[:5])
        if len(errors) > 5:
            result += f"\n...and {len(errors) - 5} more errors"

    return result


async def _list_cards_impl(
    deck_id: str | None = None, limit: int = 100, bookmark: str | None = None
) -> str:
    """
    Core implementation for listing Mochi cards.

    Args:
        deck_id: Only return cards from this deck, if given
        limit: Maximum number of cards to return per page (1-100)
        bookmark: Pagination cursor returned by a previous call

    Returns:
        Formatted list of card IDs and first content line, plus a bookmark
        for the next page when more results are available
    """
    api_key = _get_mochi_api_key()

    params: dict[str, str | int] = {"limit": limit}
    if deck_id is not None:
        params["deck-id"] = deck_id
    if bookmark is not None:
        params["bookmark"] = bookmark

    # Mochi uses HTTP Basic auth: API key as username, blank password.
    async with httpx.AsyncClient(auth=(api_key, "")) as client:
        # Mochi's router 404s without the trailing slash.
        response = await client.get(f"{MOCHI_API_BASE}/cards/", params=params)
        response.raise_for_status()

        data = response.json()

    docs = data.get("docs", [])
    if not docs:
        return "No cards found."

    lines = [f"{card['id']}: {card.get('content', '').split(chr(10), 1)[0]}" for card in docs]
    result = "\n".join(lines)

    next_bookmark = data.get("bookmark")
    if next_bookmark:
        result += f"\n\nbookmark: {next_bookmark}"

    return result


async def _get_card_impl(card_id: str) -> str:
    """
    Core implementation for fetching a single Mochi card.

    Args:
        card_id: The Mochi card ID

    Returns:
        The card's deck-id, tags, and full markdown content
    """
    api_key = _get_mochi_api_key()

    # Mochi uses HTTP Basic auth: API key as username, blank password.
    async with httpx.AsyncClient(auth=(api_key, "")) as client:
        response = await client.get(f"{MOCHI_API_BASE}/cards/{card_id}")
        response.raise_for_status()

        card = response.json()

    tags = card.get("tags") or []
    manual_tags = card.get("manual-tags") or []

    lines = [
        f"id: {card['id']}",
        f"deck-id: {card.get('deck-id', '')}",
        f"tags: {', '.join(tags) if tags else 'none'}",
        f"manual-tags: {', '.join(manual_tags) if manual_tags else 'none'}",
        "",
        card.get("content", ""),
    ]
    return "\n".join(lines)


async def _update_card_impl(
    card_id: str,
    content: str | None = None,
    deck_id: str | None = None,
    manual_tags: list[str] | None = None,
    archived: bool | None = None,
    trashed: bool | None = None,
) -> str:
    """
    Core implementation for updating a Mochi card.

    Only the provided fields are sent to the API, mapped to Mochi's
    kebab-case field names.

    Args:
        card_id: The Mochi card ID
        content: New markdown content, if changing
        deck_id: Move the card to this deck, if given
        manual_tags: Replace the card's manual tags, if given
        archived: Set the card's archived status, if given
        trashed: Soft-delete (True) or restore (False) the card, if given.
            Mochi represents this as a timestamp, not a boolean: True stamps
            the current time, False clears it.

    Returns:
        Confirmation message, or a note that nothing was provided to update
    """
    api_key = _get_mochi_api_key()

    payload: dict[str, object] = {}
    if content is not None:
        payload["content"] = content
    if deck_id is not None:
        payload["deck-id"] = deck_id
    if manual_tags is not None:
        payload["manual-tags"] = manual_tags
    if archived is not None:
        payload["archived?"] = archived
    if trashed is not None:
        # Mochi's "trashed?" field is an ISO 8601 timestamp (soft delete),
        # not a boolean: stamp "now" to trash, send null to untrash.
        payload["trashed?"] = (
            datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z" if trashed else None
        )

    if not payload:
        return "No fields provided to update."

    # Mochi uses HTTP Basic auth: API key as username, blank password.
    async with httpx.AsyncClient(auth=(api_key, "")) as client:
        response = await client.post(f"{MOCHI_API_BASE}/cards/{card_id}", json=payload)
        response.raise_for_status()

    return f"Updated card {card_id}."


async def _create_deck_impl(name: str, parent_id: str | None = None) -> str:
    """
    Core implementation for creating a Mochi deck.

    Args:
        name: The deck name
        parent_id: Nest the new deck under this parent deck, if given

    Returns:
        Confirmation message with the created deck's name and ID
    """
    api_key = _get_mochi_api_key()

    payload: dict[str, str] = {"name": name}
    if parent_id is not None:
        payload["parent-id"] = parent_id

    # Mochi uses HTTP Basic auth: API key as username, blank password.
    async with httpx.AsyncClient(auth=(api_key, "")) as client:
        # Mochi's router 404s without the trailing slash.
        response = await client.post(f"{MOCHI_API_BASE}/decks/", json=payload)
        response.raise_for_status()

        deck = response.json()

    return f"Created deck '{deck['name']}': {deck['id']}"


async def _update_deck_impl(
    deck_id: str,
    name: str | None = None,
    parent_id: str | None = None,
    archived: bool | None = None,
) -> str:
    """
    Core implementation for updating a Mochi deck.

    Only the provided fields are sent to the API, mapped to Mochi's
    kebab-case field names.

    Args:
        deck_id: The Mochi deck ID
        name: New deck name, if changing
        parent_id: Move the deck under this parent deck, if given
        archived: Set the deck's archived status, if given

    Returns:
        Confirmation message, or a note that nothing was provided to update
    """
    api_key = _get_mochi_api_key()

    payload: dict[str, str | bool] = {}
    if name is not None:
        payload["name"] = name
    if parent_id is not None:
        payload["parent-id"] = parent_id
    if archived is not None:
        payload["archived?"] = archived

    if not payload:
        return "No fields provided to update."

    # Mochi uses HTTP Basic auth: API key as username, blank password.
    async with httpx.AsyncClient(auth=(api_key, "")) as client:
        response = await client.post(f"{MOCHI_API_BASE}/decks/{deck_id}", json=payload)
        response.raise_for_status()

    return f"Updated deck {deck_id}."


def _sanitize_attachment_stem(stem: str) -> str:
    """
    Reduce a filename stem to Mochi's required [0-9a-zA-Z]{4,16} form.

    Mochi rejects attachment filenames whose stem contains anything but
    alphanumerics or falls outside 4-16 characters, returning an opaque
    422. Strip the invalid characters, truncate to 16, and zero-pad up
    to the 4-character minimum.
    """
    sanitized = re.sub(r"[^0-9a-zA-Z]", "", stem)[:16]
    return sanitized.ljust(4, "0")


async def _add_attachment_impl(card_id: str, file_path: str, filename: str | None = None) -> str:
    """
    Core implementation for attaching a file to a Mochi card.

    Args:
        card_id: The Mochi card ID
        file_path: Path to the local file to upload
        filename: Name to store the attachment as (defaults to the file's
            basename); must end in a supported image extension. The stem is
            sanitized to Mochi's [0-9a-zA-Z]{4,16} contract before upload.

    Returns:
        Confirmation message reminding how to reference the attachment
        from card content
    """
    path = Path(file_path)
    if not path.is_file():
        raise ValueError(f"File not found: {file_path}")

    resolved_filename = filename or path.name
    extension = resolved_filename.rsplit(".", 1)[-1].lower() if "." in resolved_filename else ""
    content_type = ATTACHMENT_CONTENT_TYPES.get(extension)
    if content_type is None:
        raise ValueError(
            f"Unsupported attachment extension '{extension}'. Supported: "
            f"{', '.join(sorted(ATTACHMENT_CONTENT_TYPES))}"
        )

    stem = resolved_filename.rsplit(".", 1)[0]
    resolved_filename = f"{_sanitize_attachment_stem(stem)}.{extension}"

    api_key = _get_mochi_api_key()
    file_bytes = path.read_bytes()

    # Mochi uses HTTP Basic auth: API key as username, blank password.
    async with httpx.AsyncClient(auth=(api_key, "")) as client:
        response = await client.post(
            f"{MOCHI_API_BASE}/cards/{card_id}/attachments/{resolved_filename}",
            files={"file": (resolved_filename, file_bytes, content_type)},
        )
        response.raise_for_status()

    return (
        f"Attached {resolved_filename} to card {card_id}. "
        f"Reference it in card content as ![](@media/{resolved_filename})"
    )


# =============================================================================
# TOOLS - MCP tool wrappers (delegate to core functions)
# =============================================================================


@mcp.tool
async def fetch_url(url: str, format: str = "concise") -> str:
    """
    Fetch a URL and convert it to clean markdown using JinaAI Reader.

    Use this to extract article content before generating flashcards.
    The content is automatically cleaned and converted to markdown format.

    Args:
        url: The full URL to fetch (e.g., "https://example.com/article")
        format: Response format - "concise" (default, ~first 8000 chars) or "full"

    Returns:
        The article content as clean markdown, ready for flashcard generation
    """
    return await _fetch_url_impl(url, format)


@mcp.tool
async def list_decks() -> str:
    """
    List all available Mochi decks with their IDs.

    Use this to find the deck_id before creating cards.
    Returns deck names and IDs in a compact format. The list is complete;
    there is no pagination for the caller to handle.

    Returns:
        Formatted list of deck names and their IDs
    """
    return await _list_decks_impl()


@mcp.tool
async def create_cards(deck_id: str, cards: list[dict]) -> str:
    """
    Create flashcards in Mochi. Handles single or multiple cards.

    Each card should follow Matuschak's principles: focused, precise, tractable.

    Args:
        deck_id: The Mochi deck ID (use list_decks to find this)
        cards: List of card objects, each containing:
            - question (str): The front of the card
            - answer (str): The back of the card
            - tags (list[str], optional): Topic tags for organization

    Returns:
        Summary of created cards with count and any errors

    Example:
        create_cards(
            deck_id="abc123",
            cards=[
                {"question": "What does HTTP stand for?", "answer": "HyperText Transfer Protocol"},
                {"question": "Is HTTP stateless?", "answer": "Yes", "tags": ["http", "protocols"]}
            ]
        )
    """
    return await _create_cards_impl(deck_id, cards)


@mcp.tool
async def list_cards(
    deck_id: str | None = None, limit: int = 100, bookmark: str | None = None
) -> str:
    """
    List Mochi cards, optionally scoped to a deck.

    Use this to browse or search existing cards before editing them. Results
    are paginated: pass the returned bookmark back in to fetch the next page.

    Args:
        deck_id: Only return cards from this deck, if given
        limit: Maximum number of cards to return per page (1-100, default 100)
        bookmark: Pagination cursor returned by a previous call

    Returns:
        Formatted list of card IDs and their first content line, plus a
        bookmark for the next page when more results are available
    """
    return await _list_cards_impl(deck_id, limit, bookmark)


@mcp.tool
async def get_card(card_id: str) -> str:
    """
    Fetch a single Mochi card's full content, deck, and tags.

    Args:
        card_id: The Mochi card ID (use list_cards to find this)

    Returns:
        The card's deck-id, tags, and full markdown content
    """
    return await _get_card_impl(card_id)


@mcp.tool
async def update_card(
    card_id: str,
    content: str | None = None,
    deck_id: str | None = None,
    manual_tags: list[str] | None = None,
    archived: bool | None = None,
    trashed: bool | None = None,
) -> str:
    """
    Update a Mochi card. Only provided fields are changed.

    Args:
        card_id: The Mochi card ID (use list_cards to find this)
        content: New markdown content, if changing
        deck_id: Move the card to this deck, if given
        manual_tags: Replace the card's manual tags, if given
        archived: Set the card's archived status, if given
        trashed: Soft-delete (True) or restore (False) the card, if given

    Returns:
        Confirmation message, or a note that nothing was provided to update
    """
    return await _update_card_impl(card_id, content, deck_id, manual_tags, archived, trashed)


@mcp.tool
async def create_deck(name: str, parent_id: str | None = None) -> str:
    """
    Create a new Mochi deck.

    Args:
        name: The deck name
        parent_id: Nest the new deck under this parent deck, if given

    Returns:
        Confirmation message with the created deck's name and ID
    """
    return await _create_deck_impl(name, parent_id)


@mcp.tool
async def update_deck(
    deck_id: str,
    name: str | None = None,
    parent_id: str | None = None,
    archived: bool | None = None,
) -> str:
    """
    Update a Mochi deck. Only provided fields are changed.

    Args:
        deck_id: The Mochi deck ID (use list_decks to find this)
        name: New deck name, if changing
        parent_id: Move the deck under this parent deck, if given
        archived: Set the deck's archived status, if given

    Returns:
        Confirmation message, or a note that nothing was provided to update
    """
    return await _update_deck_impl(deck_id, name, parent_id, archived)


@mcp.tool
async def add_attachment(card_id: str, file_path: str, filename: str | None = None) -> str:
    """
    Attach a local image file to a Mochi card.

    Supported extensions: png, jpg, jpeg, gif, svg, webp.

    Mochi requires the filename stem to match [0-9a-zA-Z]{4,16}, so the
    stem is sanitized before upload (non-alphanumerics stripped, truncated
    to 16 chars, zero-padded to 4). The confirmation message reports the
    final stored name to reference from card content.

    Args:
        card_id: The Mochi card ID to attach the file to
        file_path: Path to the local file to upload
        filename: Name to store the attachment as (defaults to the file's
            basename)

    Returns:
        Confirmation message reminding how to reference the attachment
        from card content (![](@media/<filename>))
    """
    return await _add_attachment_impl(card_id, file_path, filename)


# =============================================================================
# Entry Point
# =============================================================================


def main():
    """Run the MCP server."""
    # Validate configuration at startup: booting without a key would let
    # the server start cleanly and then fail confusingly on every API call.
    _get_mochi_api_key()
    mcp.run()


if __name__ == "__main__":
    main()
