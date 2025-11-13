"""
JinaAI Reader API client for content extraction.

Provides web content to markdown conversion and PDF content extraction
with rate limiting, caching, and comprehensive error handling.
"""

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, Any
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, HttpUrl

from app.core.config import settings

logger = logging.getLogger(__name__)


class ContentExtractionResult(BaseModel):
    """Result of content extraction operation."""
    content: str
    title: str
    word_count: int
    reading_time_minutes: int
    extraction_metadata: Dict[str, Any]


class ContentCache(BaseModel):
    """Cached content entry."""
    content: str
    title: str
    word_count: int
    reading_time_minutes: int
    cached_at: datetime
    extraction_metadata: Dict[str, Any]

    @property
    def is_expired(self) -> bool:
        """Check if cache entry is expired (24 hours)."""
        return datetime.utcnow() - self.cached_at > timedelta(hours=24)


class JinaAIError(Exception):
    """Base exception for JinaAI client errors."""
    pass


class JinaAIRateLimitError(JinaAIError):
    """Raised when rate limit is exceeded."""
    pass


class JinaAIAuthenticationError(JinaAIError):
    """Raised when authentication fails."""
    pass


class JinaAIClient:
    """
    JinaAI Reader API client with intelligent caching and rate limiting.

    Features:
    - Automatic retry with exponential backoff
    - Content caching to avoid re-processing
    - Rate limiting for free tier users
    - Support for both web URLs and PDF extraction
    - Comprehensive error handling and logging
    """

    BASE_URL = "https://r.jina.ai"

    def __init__(self):
        self.api_key = settings.JINA_API_KEY
        self.cache: Dict[str, ContentCache] = {}
        self.last_request_time: Optional[datetime] = None
        self.rate_limit_delay = 1.0  # seconds between requests for free tier

        # Configure HTTP client
        self.client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            headers={"User-Agent": "MochiDonut/0.1.0"}
        )

    async def extract_from_url(
        self,
        url: str,
        use_cache: bool = True,
        custom_headers: Optional[Dict[str, str]] = None
    ) -> ContentExtractionResult:
        """
        Extract content from a web URL using JinaAI Reader API.

        Args:
            url: The URL to extract content from
            use_cache: Whether to use cached content if available
            custom_headers: Additional headers to pass to JinaAI

        Returns:
            ContentExtractionResult with extracted content and metadata

        Raises:
            JinaAIError: If extraction fails
            JinaAIRateLimitError: If rate limit is exceeded
            JinaAIAuthenticationError: If authentication fails
        """
        if not url:
            raise JinaAIError("URL cannot be empty")

        # Validate URL format
        try:
            parsed_url = urlparse(url)
            if not parsed_url.scheme or not parsed_url.netloc:
                raise JinaAIError(f"Invalid URL format: {url}")
        except Exception as e:
            raise JinaAIError(f"Invalid URL: {str(e)}")

        # Check cache first
        cache_key = self._generate_cache_key(url)
        if use_cache and cache_key in self.cache:
            cached_entry = self.cache[cache_key]
            if not cached_entry.is_expired:
                logger.info(f"Using cached content for URL: {url}")
                return ContentExtractionResult(
                    content=cached_entry.content,
                    title=cached_entry.title,
                    word_count=cached_entry.word_count,
                    reading_time_minutes=cached_entry.reading_time_minutes,
                    extraction_metadata={
                        **cached_entry.extraction_metadata,
                        "from_cache": True,
                        "cached_at": cached_entry.cached_at.isoformat()
                    }
                )

        # Rate limiting for free tier
        if not self.api_key:
            await self._enforce_rate_limit()

        try:
            # Prepare request
            jina_url = f"{self.BASE_URL}/{url}"
            headers = {"Accept": "text/markdown"}

            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            if custom_headers:
                headers.update(custom_headers)

            logger.info(f"Extracting content from URL: {url}")

            # Make request with retry logic
            response = await self._make_request_with_retry(jina_url, headers)

            # Process response
            markdown_content = response.text.strip()
            if not markdown_content:
                raise JinaAIError("Empty content returned from JinaAI")

            # Extract title and calculate metrics
            title = self._extract_title(markdown_content)
            word_count = len(markdown_content.split())
            reading_time = max(1, word_count // 200)  # 200 WPM

            # Prepare result
            extraction_metadata = {
                "extracted_at": datetime.utcnow().isoformat(),
                "source_url": url,
                "content_length": len(markdown_content),
                "api_key_used": bool(self.api_key),
                "from_cache": False
            }

            result = ContentExtractionResult(
                content=markdown_content,
                title=title,
                word_count=word_count,
                reading_time_minutes=reading_time,
                extraction_metadata=extraction_metadata
            )

            # Cache the result
            if use_cache:
                self.cache[cache_key] = ContentCache(
                    content=markdown_content,
                    title=title,
                    word_count=word_count,
                    reading_time_minutes=reading_time,
                    cached_at=datetime.utcnow(),
                    extraction_metadata=extraction_metadata
                )

            logger.info(f"Successfully extracted {word_count} words from {url}")
            return result

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise JinaAIAuthenticationError("Invalid or missing API key")
            elif e.response.status_code == 429:
                raise JinaAIRateLimitError("Rate limit exceeded")
            elif e.response.status_code >= 400:
                raise JinaAIError(f"HTTP {e.response.status_code}: {e.response.text}")
            else:
                raise JinaAIError(f"Unexpected HTTP error: {str(e)}")
        except httpx.RequestError as e:
            raise JinaAIError(f"Network error: {str(e)}")
        except Exception as e:
            raise JinaAIError(f"Unexpected error during content extraction: {str(e)}")

    async def extract_from_pdf(
        self,
        pdf_url: str,
        use_cache: bool = True
    ) -> ContentExtractionResult:
        """
        Extract content from a PDF URL using JinaAI Reader API.

        Args:
            pdf_url: URL pointing to a PDF file
            use_cache: Whether to use cached content if available

        Returns:
            ContentExtractionResult with extracted PDF content

        Raises:
            JinaAIError: If extraction fails
        """
        if not pdf_url.lower().endswith('.pdf'):
            logger.warning(f"URL might not be a PDF: {pdf_url}")

        # Use the same extraction method with special headers for PDFs
        custom_headers = {
            "Accept": "text/markdown",
            "X-Return-Format": "markdown"
        }

        result = await self.extract_from_url(
            pdf_url,
            use_cache=use_cache,
            custom_headers=custom_headers
        )

        # Update metadata to indicate PDF extraction
        result.extraction_metadata.update({
            "content_type": "pdf",
            "is_pdf_extraction": True
        })

        return result

    async def _make_request_with_retry(
        self,
        url: str,
        headers: Dict[str, str],
        max_retries: int = 3
    ) -> httpx.Response:
        """Make HTTP request with exponential backoff retry."""
        last_exception = None

        for attempt in range(max_retries):
            try:
                response = await self.client.get(url, headers=headers)
                response.raise_for_status()
                return response

            except httpx.HTTPStatusError as e:
                last_exception = e

                # Don't retry on authentication or rate limit errors
                if e.response.status_code in [401, 403, 429]:
                    raise

                # Exponential backoff for server errors
                if e.response.status_code >= 500 and attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"Server error {e.response.status_code}, retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue

                raise

            except httpx.RequestError as e:
                last_exception = e

                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"Request error, retrying in {wait_time}s: {str(e)}")
                    await asyncio.sleep(wait_time)
                    continue

                raise

        # If we get here, all retries failed
        raise last_exception

    async def _enforce_rate_limit(self):
        """Enforce rate limiting for free tier usage."""
        if self.last_request_time:
            elapsed = (datetime.utcnow() - self.last_request_time).total_seconds()
            if elapsed < self.rate_limit_delay:
                sleep_time = self.rate_limit_delay - elapsed
                logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
                await asyncio.sleep(sleep_time)

        self.last_request_time = datetime.utcnow()

    def _generate_cache_key(self, url: str) -> str:
        """Generate cache key for URL."""
        return hashlib.md5(url.encode('utf-8')).hexdigest()

    def _extract_title(self, markdown_content: str) -> str:
        """Extract title from markdown content."""
        lines = markdown_content.split('\n')

        # Look for first H1 heading
        for line in lines[:10]:  # Check first 10 lines
            line = line.strip()
            if line.startswith('# '):
                return line[2:].strip()

        # Fallback to first non-empty line
        for line in lines[:5]:
            line = line.strip()
            if line and not line.startswith('#'):
                return line[:100] + ("..." if len(line) > 100 else "")

        return "Untitled Content"

    def clear_cache(self):
        """Clear the content cache."""
        self.cache.clear()
        logger.info("Content cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_entries = len(self.cache)
        expired_entries = sum(1 for entry in self.cache.values() if entry.is_expired)

        return {
            "total_entries": total_entries,
            "active_entries": total_entries - expired_entries,
            "expired_entries": expired_entries,
            "cache_size_mb": sum(
                len(entry.content.encode('utf-8'))
                for entry in self.cache.values()
            ) / (1024 * 1024)
        }

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()