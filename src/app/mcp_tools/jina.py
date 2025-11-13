# ABOUTME: MCP tools for JinaAI Reader API integration
# ABOUTME: Converts URLs to clean markdown using JinaAI Reader service
"""MCP tools for JinaAI Reader API integration."""

import httpx
from claude_agent_sdk import tool
from typing import Dict, Any

JINA_READER_BASE = "https://r.jina.ai"


@tool(
    name="fetch_markdown",
    description="Convert a URL to clean markdown using JinaAI Reader API",
    input_schema={"url": str}
)
async def fetch_markdown(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch a URL and convert it to markdown using JinaAI Reader.

    Args:
        args: {"url": "https://example.com/article"}

    Returns:
        {"content": [{"type": "text", "text": "markdown content"}]}
    """
    url = args["url"]

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{JINA_READER_BASE}/{url}",
                headers={
                    "Accept": "text/markdown",
                    "X-Return-Format": "markdown"
                }
            )
            response.raise_for_status()

            markdown = response.text

            return {
                "content": [{
                    "type": "text",
                    "text": f"Successfully fetched and converted to markdown:\n\n{markdown}"
                }]
            }

    except httpx.HTTPError as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error fetching URL: {str(e)}"
            }],
            "isError": True
        }
