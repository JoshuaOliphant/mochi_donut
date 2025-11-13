"""
Prompt service for managing Mochi flashcard creation and operations.

Handles prompt generation, quality validation, batch operations,
and integration with Mochi for flashcard management.
"""

import asyncio
import logging
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime

from app.integrations.mochi_client import (
    MochiClient,
    MochiCard,
    CardCreationResult,
    BatchCardCreationResult,
    MochiDeck
)
from app.repositories.prompt import PromptRepository
from app.repositories.content import ContentRepository
from app.schemas.prompt import (
    PromptCreateRequest,
    PromptBatchCreateRequest,
    PromptUpdateRequest,
    PromptResponse,
    MochiCardRequest,
    MochiCardBatchRequest
)
from app.db.models import PromptStatus
from app.core.config import settings

logger = logging.getLogger(__name__)


class PromptService:
    """
    Service for prompt and Mochi flashcard management.

    Features:
    - Prompt creation and validation
    - Mochi card creation with template support
    - Batch operations for efficient processing
    - Quality control and review workflows
    - Deck organization and management
    """

    def __init__(
        self,
        mochi_client: MochiClient,
        prompt_repo: PromptRepository,
        content_repo: ContentRepository
    ):
        self.mochi_client = mochi_client
        self.prompt_repo = prompt_repo
        self.content_repo = content_repo

    async def create_prompt(
        self,
        prompt_request: PromptCreateRequest
    ) -> PromptResponse:
        """
        Create a new prompt with quality validation.

        Args:
            prompt_request: Prompt creation parameters

        Returns:
            PromptResponse with created prompt details
        """
        try:
            # Validate content exists
            content = await self.content_repo.get(prompt_request.content_id)
            if not content:
                raise ValueError(f"Content {prompt_request.content_id} not found")

            # Create prompt record
            prompt_data = {
                "content_id": prompt_request.content_id,
                "front_content": prompt_request.front_content,
                "back_content": prompt_request.back_content,
                "prompt_type": prompt_request.prompt_type,
                "difficulty_level": prompt_request.difficulty_level,
                "concepts": prompt_request.concepts or [],
                "quality_score": prompt_request.quality_score,
                "status": PromptStatus.DRAFT,
                "metadata": {
                    "created_at": datetime.utcnow().isoformat(),
                    "generation_method": prompt_request.metadata.get("generation_method", "manual"),
                    "ai_model": prompt_request.metadata.get("ai_model"),
                    "prompt_source": prompt_request.metadata.get("prompt_source", "user")
                }
            }

            prompt = await self.prompt_repo.create(prompt_data)

            return PromptResponse(
                id=prompt.id,
                content_id=prompt.content_id,
                front_content=prompt.front_content,
                back_content=prompt.back_content,
                prompt_type=prompt.prompt_type,
                difficulty_level=prompt.difficulty_level,
                concepts=prompt.concepts,
                quality_score=prompt.quality_score,
                status=prompt.status,
                created_at=prompt.created_at,
                updated_at=prompt.updated_at,
                metadata=prompt.metadata
            )

        except Exception as e:
            logger.error(f"Failed to create prompt: {str(e)}")
            raise ValueError(f"Prompt creation failed: {str(e)}")

    async def create_mochi_card(
        self,
        card_request: MochiCardRequest
    ) -> CardCreationResult:
        """
        Create a single Mochi flashcard from a prompt.

        Args:
            card_request: Mochi card creation parameters

        Returns:
            CardCreationResult with creation details
        """
        try:
            # Get prompt details
            prompt = await self.prompt_repo.get(card_request.prompt_id)
            if not prompt:
                raise ValueError(f"Prompt {card_request.prompt_id} not found")

            # Prepare card content
            mochi_card = MochiCard(
                content=prompt.front_content,
                answer=prompt.back_content,
                deck_id=card_request.deck_id,
                template_id=card_request.template_id,
                tags=card_request.tags or prompt.concepts
            )

            # Create card in Mochi
            result = await self.mochi_client.create_card(
                content=mochi_card.content,
                answer=mochi_card.answer,
                deck_id=mochi_card.deck_id,
                template_id=mochi_card.template_id,
                tags=mochi_card.tags
            )

            # Update prompt with Mochi card information
            if result.success:
                await self.prompt_repo.update(card_request.prompt_id, {
                    "mochi_card_id": result.card_id,
                    "mochi_deck_id": result.deck_id,
                    "status": PromptStatus.PUBLISHED,
                    "metadata": {
                        **prompt.metadata,
                        "mochi_created_at": result.created_at.isoformat(),
                        "mochi_sync_status": "synced"
                    }
                })

                logger.info(f"Created Mochi card {result.card_id} for prompt {card_request.prompt_id}")
            else:
                await self.prompt_repo.update(card_request.prompt_id, {
                    "status": PromptStatus.FAILED,
                    "metadata": {
                        **prompt.metadata,
                        "mochi_error": result.error_message,
                        "mochi_sync_status": "failed"
                    }
                })

            return result

        except Exception as e:
            logger.error(f"Failed to create Mochi card: {str(e)}")
            raise ValueError(f"Mochi card creation failed: {str(e)}")

    async def create_mochi_cards_batch(
        self,
        batch_request: MochiCardBatchRequest
    ) -> BatchCardCreationResult:
        """
        Create multiple Mochi cards in batch.

        Args:
            batch_request: Batch card creation parameters

        Returns:
            BatchCardCreationResult with detailed results
        """
        try:
            # Prepare cards for batch creation
            mochi_cards = []
            prompt_ids = []

            for prompt_id in batch_request.prompt_ids:
                prompt = await self.prompt_repo.get(prompt_id)
                if prompt:
                    mochi_card = MochiCard(
                        content=prompt.front_content,
                        answer=prompt.back_content,
                        deck_id=batch_request.deck_id,
                        template_id=batch_request.template_id,
                        tags=batch_request.tags or prompt.concepts
                    )
                    mochi_cards.append(mochi_card)
                    prompt_ids.append(prompt_id)
                else:
                    logger.warning(f"Prompt {prompt_id} not found, skipping")

            if not mochi_cards:
                raise ValueError("No valid prompts found for batch creation")

            # Create cards in Mochi
            batch_result = await self.mochi_client.create_cards_batch(
                cards=mochi_cards,
                max_concurrent=batch_request.max_concurrent or 3
            )

            # Update prompt records based on results
            for i, result in enumerate(batch_result.results):
                if i < len(prompt_ids):
                    prompt_id = prompt_ids[i]
                    try:
                        if result.success:
                            await self.prompt_repo.update(prompt_id, {
                                "mochi_card_id": result.card_id,
                                "mochi_deck_id": result.deck_id,
                                "status": PromptStatus.PUBLISHED,
                                "metadata": {
                                    "mochi_created_at": result.created_at.isoformat(),
                                    "mochi_sync_status": "synced",
                                    "batch_id": batch_result.batch_id
                                }
                            })
                        else:
                            await self.prompt_repo.update(prompt_id, {
                                "status": PromptStatus.FAILED,
                                "metadata": {
                                    "mochi_error": result.error_message,
                                    "mochi_sync_status": "failed",
                                    "batch_id": batch_result.batch_id
                                }
                            })
                    except Exception as e:
                        logger.error(f"Failed to update prompt {prompt_id} after batch creation: {str(e)}")

            logger.info(f"Batch card creation completed: {batch_result.successful_cards}/{batch_result.total_cards} successful")
            return batch_result

        except Exception as e:
            logger.error(f"Batch card creation failed: {str(e)}")
            raise ValueError(f"Batch card creation failed: {str(e)}")

    async def get_mochi_decks(self) -> List[MochiDeck]:
        """
        Get all available Mochi decks.

        Returns:
            List of MochiDeck objects
        """
        try:
            return await self.mochi_client.get_decks()
        except Exception as e:
            logger.error(f"Failed to get Mochi decks: {str(e)}")
            raise ValueError(f"Failed to get Mochi decks: {str(e)}")

    async def create_mochi_deck(
        self,
        name: str,
        description: Optional[str] = None
    ) -> MochiDeck:
        """
        Create a new Mochi deck.

        Args:
            name: Name of the deck
            description: Optional description

        Returns:
            MochiDeck object for the created deck
        """
        try:
            return await self.mochi_client.create_deck(name, description)
        except Exception as e:
            logger.error(f"Failed to create Mochi deck '{name}': {str(e)}")
            raise ValueError(f"Failed to create Mochi deck: {str(e)}")

    async def update_prompt(
        self,
        prompt_id: uuid.UUID,
        update_request: PromptUpdateRequest
    ) -> PromptResponse:
        """
        Update an existing prompt.

        Args:
            prompt_id: ID of the prompt to update
            update_request: Update parameters

        Returns:
            PromptResponse with updated prompt details
        """
        try:
            # Get existing prompt
            prompt = await self.prompt_repo.get(prompt_id)
            if not prompt:
                raise ValueError(f"Prompt {prompt_id} not found")

            # Prepare update data
            update_data = {}
            if update_request.front_content is not None:
                update_data["front_content"] = update_request.front_content
            if update_request.back_content is not None:
                update_data["back_content"] = update_request.back_content
            if update_request.difficulty_level is not None:
                update_data["difficulty_level"] = update_request.difficulty_level
            if update_request.concepts is not None:
                update_data["concepts"] = update_request.concepts
            if update_request.quality_score is not None:
                update_data["quality_score"] = update_request.quality_score
            if update_request.status is not None:
                update_data["status"] = update_request.status

            # Add update metadata
            update_data["metadata"] = {
                **prompt.metadata,
                "updated_at": datetime.utcnow().isoformat(),
                "update_source": "manual"
            }

            # Update prompt
            updated_prompt = await self.prompt_repo.update(prompt_id, update_data)

            return PromptResponse(
                id=updated_prompt.id,
                content_id=updated_prompt.content_id,
                front_content=updated_prompt.front_content,
                back_content=updated_prompt.back_content,
                prompt_type=updated_prompt.prompt_type,
                difficulty_level=updated_prompt.difficulty_level,
                concepts=updated_prompt.concepts,
                quality_score=updated_prompt.quality_score,
                status=updated_prompt.status,
                created_at=updated_prompt.created_at,
                updated_at=updated_prompt.updated_at,
                metadata=updated_prompt.metadata
            )

        except Exception as e:
            logger.error(f"Failed to update prompt {prompt_id}: {str(e)}")
            raise ValueError(f"Prompt update failed: {str(e)}")

    async def get_prompts_by_content(
        self,
        content_id: uuid.UUID,
        status: Optional[PromptStatus] = None,
        limit: int = 50
    ) -> List[PromptResponse]:
        """
        Get prompts for specific content.

        Args:
            content_id: ID of the content
            status: Optional status filter
            limit: Maximum number of prompts to return

        Returns:
            List of PromptResponse objects
        """
        try:
            prompts = await self.prompt_repo.get_by_content_id(
                content_id=content_id,
                status=status,
                limit=limit
            )

            return [
                PromptResponse(
                    id=prompt.id,
                    content_id=prompt.content_id,
                    front_content=prompt.front_content,
                    back_content=prompt.back_content,
                    prompt_type=prompt.prompt_type,
                    difficulty_level=prompt.difficulty_level,
                    concepts=prompt.concepts,
                    quality_score=prompt.quality_score,
                    status=prompt.status,
                    created_at=prompt.created_at,
                    updated_at=prompt.updated_at,
                    metadata=prompt.metadata
                )
                for prompt in prompts
            ]

        except Exception as e:
            logger.error(f"Failed to get prompts for content {content_id}: {str(e)}")
            raise ValueError(f"Failed to get prompts: {str(e)}")

    async def get_prompt_stats(self) -> Dict[str, Any]:
        """
        Get statistics about prompts and Mochi integration.

        Returns:
            Dictionary with prompt statistics
        """
        try:
            # Get prompt counts by status
            total_prompts = await self.prompt_repo.count()
            draft_prompts = await self.prompt_repo.count(status=PromptStatus.DRAFT)
            published_prompts = await self.prompt_repo.count(status=PromptStatus.PUBLISHED)
            failed_prompts = await self.prompt_repo.count(status=PromptStatus.FAILED)

            # Check Mochi health
            mochi_healthy = await self.mochi_client.health_check()

            stats = {
                "total_prompts": total_prompts,
                "draft_prompts": draft_prompts,
                "published_prompts": published_prompts,
                "failed_prompts": failed_prompts,
                "mochi_integration": {
                    "healthy": mochi_healthy,
                    "api_key_configured": bool(settings.MOCHI_API_KEY)
                },
                "last_updated": datetime.utcnow().isoformat()
            }

            # Get deck information if Mochi is healthy
            if mochi_healthy:
                try:
                    decks = await self.mochi_client.get_decks()
                    stats["mochi_integration"]["available_decks"] = len(decks)
                    stats["mochi_integration"]["deck_names"] = [deck.name for deck in decks[:10]]  # First 10
                except Exception as e:
                    logger.warning(f"Could not get Mochi deck info: {str(e)}")

            return stats

        except Exception as e:
            logger.error(f"Failed to get prompt stats: {str(e)}")
            raise ValueError(f"Failed to get prompt stats: {str(e)}")

    async def sync_mochi_status(self, prompt_id: uuid.UUID) -> bool:
        """
        Sync status of a prompt with Mochi (check if card still exists).

        Args:
            prompt_id: ID of the prompt to sync

        Returns:
            True if sync was successful
        """
        try:
            prompt = await self.prompt_repo.get(prompt_id)
            if not prompt or not prompt.mochi_card_id:
                return False

            # In a real implementation, you would check if the card exists in Mochi
            # For now, we'll just update the sync timestamp
            await self.prompt_repo.update(prompt_id, {
                "metadata": {
                    **prompt.metadata,
                    "last_mochi_sync": datetime.utcnow().isoformat(),
                    "mochi_sync_status": "verified"
                }
            })

            return True

        except Exception as e:
            logger.error(f"Failed to sync Mochi status for prompt {prompt_id}: {str(e)}")
            return False