# ABOUTME: Jina Reader service for extracting content from URLs
# ABOUTME: Wrapper around jina_client for content extraction and processing

import logging
from typing import Optional, Dict, Any
from app.integrations.jina_client import jina_client

logger = logging.getLogger(__name__)


class JinaReaderService:
    """Service for reading and extracting content from URLs using JinaAI."""

    def __init__(self):
        """Initialize the Jina reader service."""
        self.client = jina_client

    async def extract_content(
        self,
        url: str,
        include_links: bool = False,
        timeout: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Extract content from a URL using JinaAI.

        Args:
            url: The URL to extract content from
            include_links: Whether to include links in the extracted content
            timeout: Optional timeout for the request

        Returns:
            Dictionary with extracted content or None if extraction fails
        """
        try:
            logger.info(f"Extracting content from URL: {url}")
            content = await self.client.read_url(url)
            return {
                "url": url,
                "content": content,
                "include_links": include_links,
            }
        except Exception as e:
            logger.error(f"Failed to extract content from {url}: {e}")
            return None

    async def extract_multiple(
        self,
        urls: list[str],
        include_links: bool = False
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Extract content from multiple URLs.

        Args:
            urls: List of URLs to extract content from
            include_links: Whether to include links in extracted content

        Returns:
            Dictionary mapping URLs to extracted content
        """
        results = {}
        for url in urls:
            results[url] = await self.extract_content(url, include_links)
        return results
