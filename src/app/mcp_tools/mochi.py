# ABOUTME: MCP tools for Mochi API integration
# ABOUTME: Creates flashcards and manages decks in Mochi spaced repetition app
"""MCP tools for Mochi API integration."""

import httpx
from claude_agent_sdk import tool
from typing import Dict, Any, List
import os

MOCHI_API_BASE = "https://app.mochi.cards/api"
MOCHI_API_KEY = os.getenv("MOCHI_API_KEY")


@tool(
    name="create_card",
    description="Create a flashcard in Mochi",
    input_schema={
        "deck_id": str,
        "question": str,
        "answer": str,
        "tags": list
    }
)
async def create_card(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a flashcard in Mochi.

    Args:
        args: {
            "deck_id": "deck-uuid",
            "question": "Front of card",
            "answer": "Back of card",
            "tags": ["tag1", "tag2"]
        }
    """
    try:
        if not MOCHI_API_KEY:
            return {
                "content": [{
                    "type": "text",
                    "text": "Error: MOCHI_API_KEY environment variable not set"
                }],
                "isError": True
            }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{MOCHI_API_BASE}/cards",
                headers={
                    "Authorization": f"Bearer {MOCHI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "deck-id": args["deck_id"],
                    "content": args["question"],
                    "fields": {
                        "answer": {"value": args["answer"]}
                    },
                    "tags": args.get("tags", [])
                }
            )
            response.raise_for_status()

            card = response.json()
            return {
                "content": [{
                    "type": "text",
                    "text": f"Created Mochi card: {card.get('id')}"
                }]
            }

    except httpx.HTTPError as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error creating Mochi card: {str(e)}"
            }],
            "isError": True
        }


@tool(
    name="list_decks",
    description="List all available Mochi decks",
    input_schema={}
)
async def list_decks(args: Dict[str, Any]) -> Dict[str, Any]:
    """List all Mochi decks for the user."""
    try:
        if not MOCHI_API_KEY:
            return {
                "content": [{
                    "type": "text",
                    "text": "Error: MOCHI_API_KEY environment variable not set"
                }],
                "isError": True
            }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{MOCHI_API_BASE}/decks",
                headers={"Authorization": f"Bearer {MOCHI_API_KEY}"}
            )
            response.raise_for_status()

            decks = response.json()
            deck_list = "\n".join([
                f"- {deck['name']} (ID: {deck['id']})"
                for deck in decks.get('docs', [])
            ])

            return {
                "content": [{
                    "type": "text",
                    "text": f"Available Mochi decks:\n{deck_list}"
                }]
            }

    except httpx.HTTPError as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error listing decks: {str(e)}"
            }],
            "isError": True
        }
