"""
Mochi API client for flashcard creation and management.

Provides card creation, deck organization, batch operations,
and template support with comprehensive error handling.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urljoin

import httpx
from pydantic import BaseModel, Field

from app.core.config import settings

logger = logging.getLogger(__name__)


class MochiCard(BaseModel):
    """Mochi flashcard model."""
    content: str = Field(..., description="The front content of the card")
    answer: Optional[str] = Field(None, description="The back content of the card")
    deck_id: Optional[str] = Field(None, description="ID of the deck to add card to")
    template_id: Optional[str] = Field(None, description="Template ID for the card")
    tags: List[str] = Field(default_factory=list, description="Tags for the card")
    attachments: List[Dict[str, Any]] = Field(default_factory=list, description="Card attachments")


class MochiDeck(BaseModel):
    """Mochi deck model."""
    id: str
    name: str
    description: Optional[str] = None
    card_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class MochiTemplate(BaseModel):
    """Mochi template model."""
    id: str
    name: str
    fields: List[Dict[str, Any]]
    deck_id: Optional[str] = None


class CardCreationResult(BaseModel):
    """Result of card creation operation."""
    card_id: str
    deck_id: Optional[str]
    created_at: datetime
    success: bool = True
    error_message: Optional[str] = None


class BatchCardCreationResult(BaseModel):
    """Result of batch card creation operation."""
    total_cards: int
    successful_cards: int
    failed_cards: int
    results: List[CardCreationResult]
    batch_id: str
    processing_time_seconds: float


class MochiError(Exception):
    """Base exception for Mochi client errors."""
    pass


class MochiAuthenticationError(MochiError):
    """Raised when authentication with Mochi API fails."""
    pass


class MochiRateLimitError(MochiError):
    """Raised when Mochi API rate limit is exceeded."""
    pass


class MochiCardCreationError(MochiError):
    """Raised when card creation fails."""
    pass


class MochiClient:
    """
    Mochi API client for flashcard management.

    Features:
    - Card creation and management
    - Deck organization and listing
    - Batch card creation with error handling
    - Template support for structured prompts
    - Rate limiting and retry logic
    - Comprehensive error handling and logging
    """

    BASE_URL = "https://app.mochi.cards/api"

    def __init__(self):
        self.api_key = settings.MOCHI_API_KEY
        if not self.api_key:
            logger.warning("Mochi API key not provided - Mochi integration will be disabled")

        # Configure HTTP client
        self.client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_connections=5, max_keepalive_connections=2),
            headers={
                "User-Agent": "MochiDonut/0.1.0",
                "Content-Type": "application/json"
            }
        )

        # Rate limiting
        self.last_request_time: Optional[datetime] = None
        self.rate_limit_delay = 0.5  # seconds between requests

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        if not self.api_key:
            raise MochiAuthenticationError("Mochi API key not configured")

        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def _enforce_rate_limit(self):
        """Enforce rate limiting to respect API limits."""
        if self.last_request_time:
            elapsed = (datetime.utcnow() - self.last_request_time).total_seconds()
            if elapsed < self.rate_limit_delay:
                sleep_time = self.rate_limit_delay - elapsed
                await asyncio.sleep(sleep_time)

        self.last_request_time = datetime.utcnow()

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> httpx.Response:
        """Make authenticated request to Mochi API with error handling."""
        await self._enforce_rate_limit()

        url = urljoin(self.BASE_URL + "/", endpoint.lstrip("/"))
        headers = self._get_headers()

        try:
            response = await self.client.request(
                method=method,
                url=url,
                headers=headers,
                json=data,
                params=params
            )

            if response.status_code == 401:
                raise MochiAuthenticationError("Invalid Mochi API key")
            elif response.status_code == 429:
                raise MochiRateLimitError("Mochi API rate limit exceeded")
            elif response.status_code >= 400:
                error_text = response.text if response.text else f"HTTP {response.status_code}"
                raise MochiError(f"Mochi API error: {error_text}")

            return response

        except httpx.RequestError as e:
            raise MochiError(f"Network error connecting to Mochi: {str(e)}")

    async def create_card(
        self,
        content: str,
        answer: Optional[str] = None,
        deck_id: Optional[str] = None,
        template_id: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> CardCreationResult:
        """
        Create a new flashcard in Mochi.

        Args:
            content: Front content of the card
            answer: Back content of the card (optional for some templates)
            deck_id: ID of the deck to add the card to
            template_id: Template ID for structured cards
            tags: List of tags for the card

        Returns:
            CardCreationResult with creation details

        Raises:
            MochiCardCreationError: If card creation fails
            MochiAuthenticationError: If authentication fails
        """
        try:
            card_data = {
                "content": content,
                "deck-id": deck_id,
                "template-id": template_id,
                "tags": ",".join(tags) if tags else ""
            }

            # Add answer/back content if provided
            if answer:
                card_data["content"] += f"\n---\n{answer}"

            logger.info(f"Creating Mochi card in deck {deck_id}")

            response = await self._make_request("POST", "/cards", data=card_data)
            result_data = response.json()

            return CardCreationResult(
                card_id=result_data.get("id", ""),
                deck_id=deck_id,
                created_at=datetime.utcnow(),
                success=True
            )

        except MochiError:
            raise
        except Exception as e:
            error_msg = f"Failed to create Mochi card: {str(e)}"
            logger.error(error_msg)
            raise MochiCardCreationError(error_msg)

    async def create_cards_batch(
        self,
        cards: List[MochiCard],
        max_concurrent: int = 3
    ) -> BatchCardCreationResult:
        """
        Create multiple cards in batch with concurrency control.

        Args:
            cards: List of MochiCard objects to create
            max_concurrent: Maximum number of concurrent requests

        Returns:
            BatchCardCreationResult with detailed results
        """
        start_time = datetime.utcnow()
        batch_id = f"batch_{int(start_time.timestamp())}"
        results = []

        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(max_concurrent)

        async def create_single_card(card: MochiCard) -> CardCreationResult:
            async with semaphore:
                try:
                    return await self.create_card(
                        content=card.content,
                        answer=card.answer,
                        deck_id=card.deck_id,
                        template_id=card.template_id,
                        tags=card.tags
                    )
                except Exception as e:
                    return CardCreationResult(
                        card_id="",
                        deck_id=card.deck_id,
                        created_at=datetime.utcnow(),
                        success=False,
                        error_message=str(e)
                    )

        # Execute all card creations concurrently
        logger.info(f"Creating {len(cards)} cards in batch {batch_id}")
        tasks = [create_single_card(card) for card in cards]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        # Calculate statistics
        successful_cards = sum(1 for result in results if result.success)
        failed_cards = len(results) - successful_cards
        processing_time = (datetime.utcnow() - start_time).total_seconds()

        logger.info(f"Batch {batch_id} completed: {successful_cards}/{len(cards)} successful")

        return BatchCardCreationResult(
            total_cards=len(cards),
            successful_cards=successful_cards,
            failed_cards=failed_cards,
            results=results,
            batch_id=batch_id,
            processing_time_seconds=processing_time
        )

    async def get_decks(self) -> List[MochiDeck]:
        """
        Retrieve all available decks.

        Returns:
            List of MochiDeck objects

        Raises:
            MochiError: If deck retrieval fails
        """
        try:
            logger.info("Retrieving Mochi decks")

            response = await self._make_request("GET", "/decks")
            decks_data = response.json()

            decks = []
            for deck_data in decks_data.get("docs", []):
                deck = MochiDeck(
                    id=deck_data.get("id", ""),
                    name=deck_data.get("name", ""),
                    description=deck_data.get("description"),
                    card_count=deck_data.get("cards", 0),
                    created_at=self._parse_datetime(deck_data.get("created-at")),
                    updated_at=self._parse_datetime(deck_data.get("updated-at"))
                )
                decks.append(deck)

            logger.info(f"Retrieved {len(decks)} Mochi decks")
            return decks

        except MochiError:
            raise
        except Exception as e:
            error_msg = f"Failed to retrieve Mochi decks: {str(e)}"
            logger.error(error_msg)
            raise MochiError(error_msg)

    async def get_deck_by_name(self, deck_name: str) -> Optional[MochiDeck]:
        """
        Find a deck by name.

        Args:
            deck_name: Name of the deck to find

        Returns:
            MochiDeck if found, None otherwise
        """
        decks = await self.get_decks()
        for deck in decks:
            if deck.name.lower() == deck_name.lower():
                return deck
        return None

    async def create_deck(
        self,
        name: str,
        description: Optional[str] = None
    ) -> MochiDeck:
        """
        Create a new deck.

        Args:
            name: Name of the deck
            description: Optional description

        Returns:
            MochiDeck object for the created deck

        Raises:
            MochiError: If deck creation fails
        """
        try:
            deck_data = {
                "name": name,
                "description": description or ""
            }

            logger.info(f"Creating Mochi deck: {name}")

            response = await self._make_request("POST", "/decks", data=deck_data)
            result_data = response.json()

            return MochiDeck(
                id=result_data.get("id", ""),
                name=name,
                description=description,
                card_count=0,
                created_at=datetime.utcnow()
            )

        except MochiError:
            raise
        except Exception as e:
            error_msg = f"Failed to create Mochi deck '{name}': {str(e)}"
            logger.error(error_msg)
            raise MochiError(error_msg)

    async def get_templates(self, deck_id: Optional[str] = None) -> List[MochiTemplate]:
        """
        Retrieve available templates.

        Args:
            deck_id: Optional deck ID to filter templates

        Returns:
            List of MochiTemplate objects

        Raises:
            MochiError: If template retrieval fails
        """
        try:
            params = {"deck-id": deck_id} if deck_id else None
            logger.info(f"Retrieving Mochi templates for deck {deck_id}")

            response = await self._make_request("GET", "/templates", params=params)
            templates_data = response.json()

            templates = []
            for template_data in templates_data.get("docs", []):
                template = MochiTemplate(
                    id=template_data.get("id", ""),
                    name=template_data.get("name", ""),
                    fields=template_data.get("fields", []),
                    deck_id=template_data.get("deck-id")
                )
                templates.append(template)

            logger.info(f"Retrieved {len(templates)} Mochi templates")
            return templates

        except MochiError:
            raise
        except Exception as e:
            error_msg = f"Failed to retrieve Mochi templates: {str(e)}"
            logger.error(error_msg)
            raise MochiError(error_msg)

    async def health_check(self) -> bool:
        """
        Check if Mochi API is accessible.

        Returns:
            True if API is healthy, False otherwise
        """
        try:
            if not self.api_key:
                return False

            await self._make_request("GET", "/decks", params={"limit": 1})
            return True

        except Exception as e:
            logger.error(f"Mochi health check failed: {str(e)}")
            return False

    def _parse_datetime(self, date_string: Optional[str]) -> Optional[datetime]:
        """Parse datetime string from Mochi API."""
        if not date_string:
            return None

        try:
            # Mochi typically uses ISO format
            return datetime.fromisoformat(date_string.replace("Z", "+00:00"))
        except Exception:
            logger.warning(f"Failed to parse datetime: {date_string}")
            return None

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()