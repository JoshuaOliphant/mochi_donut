# ABOUTME: MCP server for Mochi Donut flashcard generation
# ABOUTME: Provides tools, resources, and prompts for URL→flashcard workflows
"""
Mochi Donut MCP Server

A focused MCP server for converting web content into high-quality Mochi flashcards
following Andy Matuschak's spaced repetition principles.

Components:
- Tools: fetch_url, list_decks, create_cards
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
from typing import Optional

import httpx
from fastmcp import FastMCP

# Configuration
JINA_READER_BASE = "https://r.jina.ai"
MOCHI_API_BASE = "https://app.mochi.cards/api"

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

Always prioritize understanding over memorization. Create focused, specific prompts."""

# Initialize the MCP server
mcp = FastMCP("mochi-donut", instructions=SERVER_INSTRUCTIONS)


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
            headers={
                "Accept": "text/markdown",
                "X-Return-Format": "markdown"
            }
        )
        response.raise_for_status()

        content = response.text

        # Token efficiency: truncate for concise mode
        if format == "concise" and len(content) > 8000:
            content = content[:8000] + "\n\n[Content truncated. Use format='full' for complete text.]"

        return content


async def _list_decks_impl() -> str:
    """
    Core implementation for listing Mochi decks.

    Returns:
        Formatted list of deck names and IDs
    """
    api_key = _get_mochi_api_key()

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{MOCHI_API_BASE}/decks",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        response.raise_for_status()

        decks = response.json()
        lines = [f"{deck['name']}: {deck['id']}"
                 for deck in decks.get('docs', [])]
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

    async with httpx.AsyncClient() as client:
        for i, card in enumerate(cards):
            if "question" not in card or "answer" not in card:
                errors.append(f"Card {i+1}: Missing question or answer")
                continue

            try:
                response = await client.post(
                    f"{MOCHI_API_BASE}/cards",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "deck-id": deck_id,
                        "content": card["question"],
                        "fields": {
                            "answer": {"value": card["answer"]}
                        },
                        "tags": card.get("tags", [])
                    }
                )
                response.raise_for_status()
                created_count += 1
            except httpx.HTTPStatusError as e:
                errors.append(f"Card {i+1}: {e.response.status_code} - {e.response.text[:100]}")
            except Exception as e:
                errors.append(f"Card {i+1}: {str(e)}")

    result = f"Created {created_count}/{len(cards)} cards"
    if errors:
        result += f"\nErrors:\n" + "\n".join(errors[:5])
        if len(errors) > 5:
            result += f"\n...and {len(errors) - 5} more errors"

    return result


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
    Returns deck names and IDs in a compact format.

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


# =============================================================================
# Entry Point
# =============================================================================

def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
