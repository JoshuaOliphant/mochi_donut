# ABOUTME: MCP tool registration for Claude Agent SDK
# ABOUTME: Exports all MCP tools and provides unified tool collection interface
"""
MCP tool registration for Claude Agent SDK.

This module provides unified access to all MCP tools for JinaAI, Chroma,
Mochi, and database operations. Tools are organized by category for easy
discovery and use in Claude SDK agents.
"""

from claude_agent_sdk import create_sdk_mcp_server

from .jina import fetch_markdown
from .chroma import store_content, search_similar
from .mochi import create_card, list_decks
from .database import save_content, save_prompts, query_prompts, update_prompt_status


# Tool categories for documentation and discovery
TOOL_CATEGORIES = {
    "content_acquisition": [
        fetch_markdown,
    ],
    "vector_storage": [
        store_content,
        search_similar,
    ],
    "flashcard_creation": [
        create_card,
        list_decks,
    ],
    "database_operations": [
        save_content,
        save_prompts,
        query_prompts,
        update_prompt_status,
    ],
}


def get_all_tools():
    """
    Get all MCP tools organized by category.

    Returns:
        dict: Dictionary mapping category names to lists of tool functions
    """
    return TOOL_CATEGORIES


def get_flat_tool_list():
    """
    Get a flat list of all MCP tools.

    Returns:
        list: List of all tool functions
    """
    tools = []
    for category_tools in TOOL_CATEGORIES.values():
        tools.extend(category_tools)
    return tools


# Export all tools for convenient importing
__all__ = [
    # JinaAI tools
    "fetch_markdown",
    # Chroma tools
    "store_content",
    "search_similar",
    # Mochi tools
    "create_card",
    "list_decks",
    # Database tools
    "save_content",
    "save_prompts",
    "query_prompts",
    "update_prompt_status",
    # Utility functions
    "get_all_tools",
    "get_flat_tool_list",
    "TOOL_CATEGORIES",
]
