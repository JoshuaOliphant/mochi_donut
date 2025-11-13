# Enhanced Prompt Generator Service with Multi-Agent Integration
"""
Enhanced service layer for prompt generation using the multi-agent AI system.
Integrates the new LangGraph-based workflow with the existing FastAPI application.
"""

import uuid
import logging
from typing import Dict, Any, List, Optional, AsyncGenerator
from datetime import datetime

from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.content import ContentRepository
from app.repositories.prompt import PromptRepository
from app.schemas.prompt import (
    PromptGenerationRequest,
    PromptGenerationResponse,
    PromptCreate,
    PromptResponse,
    QualityMetricCreate,
    MochiCardRequest,
    MochiCardResponse,
    MochiBatchSyncRequest,
    MochiBatchSyncResponse
)
from app.db.models import PromptType, QualityMetricType
from app.core.config import settings
from app.agents.service import AgentOrchestratorService
from app.agents.config import agent_config, estimate_workflow_cost


logger = logging.getLogger(__name__)


class EnhancedPromptGeneratorService:
    """
    Enhanced service for prompt generation using multi-agent AI system.

    This service provides both synchronous and asynchronous prompt generation
    with comprehensive quality control, cost tracking, and Mochi integration.
    """

    def __init__(
        self,
        content_repo: ContentRepository,
        prompt_repo: PromptRepository,
        db_session: AsyncSession
    ):
        self.content_repo = content_repo
        self.prompt_repo = prompt_repo
        self.db_session = db_session

        # Initialize agent orchestrator
        self.agent_orchestrator = AgentOrchestratorService(
            content_repo=content_repo,
            prompt_repo=prompt_repo,
            db_session=db_session
        )

    async def generate_prompts(
        self,
        generation_request: PromptGenerationRequest,
        background_tasks: Optional[BackgroundTasks] = None
    ) -> PromptGenerationResponse:
        """
        Generate prompts using the multi-agent system.

        Args:
            generation_request: Request containing content ID and generation parameters
            background_tasks: Optional background tasks for async processing

        Returns:
            PromptGenerationResponse with generated prompts or task status
        """
        try:
            # Validate content exists
            content = await self.content_repo.get_by_id(generation_request.content_id)
            if not content:
                return PromptGenerationResponse(
                    success=False,
                    message="Content not found",
                    workflow_id=str(uuid.uuid4()),
                    prompts=[],
                    metadata={"error": "Content not found"}
                )

            # Get cost estimate
            cost_estimate = await self._get_cost_estimate(
                content=content,
                target_prompts=generation_request.target_count
            )

            # Check cost limits
            if cost_estimate["estimated_total_cost"] > agent_config.workflow.cost_limit_per_workflow:
                return PromptGenerationResponse(
                    success=False,
                    message=f"Estimated cost (${cost_estimate['estimated_total_cost']:.4f}) exceeds limit",
                    workflow_id=str(uuid.uuid4()),
                    prompts=[],
                    metadata={
                        "cost_estimate": cost_estimate,
                        "cost_limit": agent_config.workflow.cost_limit_per_workflow
                    }
                )

            # Execute workflow based on processing mode
            if generation_request.async_processing and background_tasks:
                # Asynchronous processing
                workflow_id = str(uuid.uuid4())
                background_tasks.add_task(
                    self._generate_prompts_background,
                    generation_request,
                    workflow_id
                )

                return PromptGenerationResponse(
                    success=True,
                    message="Prompt generation submitted for background processing",
                    workflow_id=workflow_id,
                    prompts=[],
                    metadata={
                        "status": "submitted",
                        "cost_estimate": cost_estimate,
                        "processing_mode": "async"
                    }
                )
            else:
                # Synchronous processing
                return await self.agent_orchestrator.generate_prompts(generation_request)

        except Exception as e:
            logger.error(f"Prompt generation failed: {e}")
            return PromptGenerationResponse(
                success=False,
                message=f"Prompt generation failed: {str(e)}",
                workflow_id=str(uuid.uuid4()),
                prompts=[],
                metadata={"error": str(e)}
            )

    async def generate_prompts_stream(
        self,
        generation_request: PromptGenerationRequest
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Generate prompts with streaming progress updates.

        Args:
            generation_request: Request containing content ID and generation parameters

        Yields:
            Progress updates and final results
        """
        async for update in self.agent_orchestrator.generate_prompts_stream(generation_request):
            yield update

    async def preview_content_analysis(
        self,
        content_id: uuid.UUID
    ) -> Dict[str, Any]:
        """
        Preview content analysis without generating prompts.

        Args:
            content_id: ID of content to analyze

        Returns:
            Analysis preview with key concepts and recommendations
        """
        return await self.agent_orchestrator.preview_content_analysis(content_id)

    async def get_cost_estimate(
        self,
        content_id: uuid.UUID,
        target_prompts: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get cost estimate for prompt generation.

        Args:
            content_id: ID of content to process
            target_prompts: Target number of prompts to generate

        Returns:
            Cost estimate breakdown
        """
        return await self.agent_orchestrator.get_cost_estimate(content_id, target_prompts)

    async def _generate_prompts_background(
        self,
        generation_request: PromptGenerationRequest,
        workflow_id: str
    ):
        """Background task for prompt generation."""
        try:
            logger.info(f"Starting background prompt generation for workflow {workflow_id}")

            # Execute the workflow
            result = await self.agent_orchestrator.generate_prompts(generation_request)

            # Log completion
            if result.success:
                logger.info(
                    f"Background prompt generation completed for workflow {workflow_id}. "
                    f"Generated {len(result.prompts)} prompts."
                )
            else:
                logger.error(
                    f"Background prompt generation failed for workflow {workflow_id}: "
                    f"{result.message}"
                )

            # Here you could add webhook notifications, database status updates, etc.

        except Exception as e:
            logger.error(f"Background prompt generation failed for workflow {workflow_id}: {e}")

    async def _get_cost_estimate(
        self,
        content: Any,
        target_prompts: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get cost estimate for content processing."""
        content_length = len(content.processed_content)
        estimated_prompts = target_prompts or min(content_length // 500, 20)

        return estimate_workflow_cost(
            content_length=content_length,
            target_prompts=estimated_prompts,
            config=agent_config
        )

    # Mochi Integration Methods (Enhanced with Quality Tracking)

    async def create_mochi_cards(
        self,
        card_request: MochiCardRequest
    ) -> MochiCardResponse:
        """
        Create cards in Mochi with enhanced quality tracking.

        Args:
            card_request: Request containing prompts to create in Mochi

        Returns:
            Response with created card information
        """
        try:
            created_cards = []
            failed_cards = []

            for prompt_id in card_request.prompt_ids:
                try:
                    # Get prompt with quality metrics
                    prompt = await self.prompt_repo.get_with_quality_metrics(prompt_id)
                    if not prompt:
                        failed_cards.append({
                            "prompt_id": str(prompt_id),
                            "error": "Prompt not found"
                        })
                        continue

                    # Check quality score before creating card
                    quality_scores = [m.score for m in prompt.quality_metrics]
                    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0

                    if avg_quality < agent_config.workflow.quality_threshold:
                        failed_cards.append({
                            "prompt_id": str(prompt_id),
                            "error": f"Quality score ({avg_quality:.2f}) below threshold",
                            "quality_score": avg_quality
                        })
                        continue

                    # Create Mochi card
                    mochi_card = await self._create_mochi_card(prompt, card_request.deck_id)
                    if mochi_card:
                        created_cards.append(mochi_card)

                        # Update prompt with Mochi information
                        await self.prompt_repo.update_mochi_info(
                            prompt_id=prompt_id,
                            mochi_card_id=mochi_card["id"],
                            mochi_deck_id=card_request.deck_id,
                            mochi_status="created"
                        )

                except Exception as e:
                    failed_cards.append({
                        "prompt_id": str(prompt_id),
                        "error": str(e)
                    })

            return MochiCardResponse(
                deck_id=card_request.deck_id,
                created_count=len(created_cards),
                failed_count=len(failed_cards),
                cards=created_cards,
                errors=failed_cards,
                success=len(created_cards) > 0
            )

        except Exception as e:
            logger.error(f"Mochi card creation failed: {e}")
            return MochiCardResponse(
                deck_id=card_request.deck_id,
                created_count=0,
                failed_count=len(card_request.prompt_ids),
                cards=[],
                errors=[{"error": str(e)}],
                success=False
            )

    async def _create_mochi_card(
        self,
        prompt: Any,
        deck_id: str
    ) -> Optional[Dict[str, Any]]:
        """Create a single card in Mochi."""
        try:
            # Prepare card data
            card_data = {
                "deck-id": deck_id,
                "fields": {
                    "Question": prompt.question,
                    "Answer": prompt.answer
                },
                "tags": prompt.tags or [],
                "archived?": False
            }

            # Add metadata if available
            if prompt.metadata:
                card_data["fields"]["Source"] = prompt.metadata.get("source", "")
                card_data["fields"]["Confidence"] = str(prompt.confidence_score or "")

            # Make API call to Mochi
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.MOCHI_API_BASE_URL}/cards",
                    headers={
                        "Authorization": f"Bearer {settings.MOCHI_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json=card_data,
                    timeout=30.0
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Mochi API error: {response.status_code} - {response.text}")
                    return None

        except Exception as e:
            logger.error(f"Failed to create Mochi card: {e}")
            return None

    async def batch_sync_mochi(
        self,
        sync_request: MochiBatchSyncRequest
    ) -> MochiBatchSyncResponse:
        """
        Batch synchronize prompts with Mochi.

        Args:
            sync_request: Request containing sync parameters

        Returns:
            Response with sync results
        """
        try:
            # Get prompts that meet quality criteria
            prompts = await self.prompt_repo.get_prompts_for_mochi_sync(
                content_id=sync_request.content_id,
                min_quality_score=agent_config.workflow.quality_threshold,
                limit=sync_request.batch_size
            )

            if not prompts:
                return MochiBatchSyncResponse(
                    content_id=sync_request.content_id,
                    total_processed=0,
                    successful_syncs=0,
                    failed_syncs=0,
                    cards=[],
                    errors=[],
                    success=True,
                    message="No prompts available for sync"
                )

            # Create cards in batches
            card_request = MochiCardRequest(
                deck_id=sync_request.deck_id,
                prompt_ids=[p.id for p in prompts],
                batch_size=sync_request.batch_size
            )

            card_response = await self.create_mochi_cards(card_request)

            return MochiBatchSyncResponse(
                content_id=sync_request.content_id,
                total_processed=len(prompts),
                successful_syncs=card_response.created_count,
                failed_syncs=card_response.failed_count,
                cards=card_response.cards,
                errors=card_response.errors,
                success=card_response.success,
                message=f"Synced {card_response.created_count} cards to Mochi"
            )

        except Exception as e:
            logger.error(f"Batch Mochi sync failed: {e}")
            return MochiBatchSyncResponse(
                content_id=sync_request.content_id,
                total_processed=0,
                successful_syncs=0,
                failed_syncs=0,
                cards=[],
                errors=[{"error": str(e)}],
                success=False,
                message=f"Batch sync failed: {str(e)}"
            )

    # Quality and Analytics Methods

    async def get_quality_analytics(
        self,
        content_id: uuid.UUID
    ) -> Dict[str, Any]:
        """Get quality analytics for prompts generated from content."""
        try:
            prompts = await self.prompt_repo.get_by_content_id(content_id)
            if not prompts:
                return {"error": "No prompts found for content"}

            # Calculate quality metrics
            total_prompts = len(prompts)
            quality_scores = []
            type_distribution = {}
            quality_by_type = {}

            for prompt in prompts:
                # Get quality scores
                if hasattr(prompt, 'quality_metrics') and prompt.quality_metrics:
                    scores = [m.score for m in prompt.quality_metrics]
                    avg_score = sum(scores) / len(scores)
                    quality_scores.append(avg_score)
                else:
                    quality_scores.append(prompt.confidence_score or 0.0)

                # Track type distribution
                prompt_type = str(prompt.prompt_type)
                type_distribution[prompt_type] = type_distribution.get(prompt_type, 0) + 1

                # Quality by type
                if prompt_type not in quality_by_type:
                    quality_by_type[prompt_type] = []
                quality_by_type[prompt_type].append(quality_scores[-1])

            # Calculate statistics
            analytics = {
                "total_prompts": total_prompts,
                "average_quality": sum(quality_scores) / len(quality_scores) if quality_scores else 0.0,
                "min_quality": min(quality_scores) if quality_scores else 0.0,
                "max_quality": max(quality_scores) if quality_scores else 0.0,
                "above_threshold": len([s for s in quality_scores if s >= agent_config.workflow.quality_threshold]),
                "type_distribution": type_distribution,
                "quality_by_type": {
                    ptype: sum(scores) / len(scores) for ptype, scores in quality_by_type.items()
                },
                "quality_threshold": agent_config.workflow.quality_threshold
            }

            return analytics

        except Exception as e:
            logger.error(f"Quality analytics failed: {e}")
            return {"error": str(e)}

    async def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """Get the status of a running workflow."""
        return await self.agent_orchestrator.get_workflow_status(workflow_id)