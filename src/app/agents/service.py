# Agent Orchestrator Service
"""
High-level service for integrating the multi-agent AI system with the FastAPI application.
Provides a clean interface for prompt generation with cost tracking and monitoring.
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from .workflow import PromptGenerationWorkflow
from .orchestrator import OrchestratorAgent
from .base import CostTracker
from app.repositories.content import ContentRepository
from app.repositories.prompt import PromptRepository
from app.schemas.prompt import (
    PromptGenerationRequest,
    PromptGenerationResponse,
    PromptCreate,
    QualityMetricCreate
)
from app.db.models import PromptType, QualityMetricType
from app.core.config import settings


logger = logging.getLogger(__name__)


class AgentOrchestratorService:
    """
    High-level service for orchestrating AI agents for prompt generation.

    This service provides a clean interface between the FastAPI application
    and the multi-agent system, handling database integration, cost tracking,
    and progress monitoring.
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

        # Initialize workflow components
        self.workflow = PromptGenerationWorkflow(
            quality_threshold=getattr(settings, 'QUALITY_THRESHOLD', 0.7),
            max_iterations=getattr(settings, 'MAX_ITERATIONS', 3)
        )

        # Fallback orchestrator
        self.orchestrator = OrchestratorAgent(
            quality_threshold=getattr(settings, 'QUALITY_THRESHOLD', 0.7),
            max_iterations=getattr(settings, 'MAX_ITERATIONS', 3)
        )

    async def generate_prompts(
        self,
        request: PromptGenerationRequest
    ) -> PromptGenerationResponse:
        """
        Generate prompts for content using the multi-agent system.

        Args:
            request: Prompt generation request containing content ID and parameters

        Returns:
            PromptGenerationResponse with generated prompts and metadata
        """
        try:
            # Fetch content from database
            content = await self.content_repo.get_by_id(request.content_id)
            if not content:
                raise ValueError(f"Content with ID {request.content_id} not found")

            # Prepare content metadata
            content_metadata = {
                "title": content.title,
                "content_type": content.content_type,
                "source_url": content.source_url,
                "processing_metadata": content.metadata
            }

            # Execute workflow
            workflow_result = await self.workflow.execute(
                content_id=str(request.content_id),
                content_text=content.processed_content,
                content_metadata=content_metadata
            )

            # Process results
            if workflow_result["status"] == "failed":
                return PromptGenerationResponse(
                    success=False,
                    message="Prompt generation failed",
                    workflow_id=workflow_result["workflow_id"],
                    prompts=[],
                    metadata=workflow_result.get("metadata", {})
                )

            # Save prompts to database
            saved_prompts = await self._save_prompts_to_database(
                content_id=request.content_id,
                prompts=workflow_result["prompts"],
                workflow_metadata=workflow_result["metadata"]
            )

            # Save quality metrics if available
            if "quality_analysis" in workflow_result:
                await self._save_quality_metrics(
                    saved_prompts,
                    workflow_result["quality_analysis"]
                )

            return PromptGenerationResponse(
                success=True,
                message=f"Generated {len(saved_prompts)} prompts successfully",
                workflow_id=workflow_result["workflow_id"],
                prompts=[self._format_prompt_response(p) for p in saved_prompts],
                metadata={
                    **workflow_result.get("metadata", {}),
                    "cost_summary": workflow_result.get("metrics", {}).get("cost_summary", {}),
                    "quality_summary": workflow_result.get("quality_analysis", {}).get("overall_score")
                }
            )

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
        request: PromptGenerationRequest
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Generate prompts with streaming progress updates.

        Args:
            request: Prompt generation request

        Yields:
            Progress updates and final results
        """
        workflow_id = str(uuid.uuid4())

        try:
            yield {
                "type": "progress",
                "workflow_id": workflow_id,
                "stage": "initialization",
                "message": "Starting prompt generation workflow",
                "timestamp": datetime.now().isoformat()
            }

            # Fetch content
            yield {
                "type": "progress",
                "workflow_id": workflow_id,
                "stage": "content_loading",
                "message": "Loading content from database",
                "timestamp": datetime.now().isoformat()
            }

            content = await self.content_repo.get_by_id(request.content_id)
            if not content:
                yield {
                    "type": "error",
                    "workflow_id": workflow_id,
                    "message": f"Content with ID {request.content_id} not found",
                    "timestamp": datetime.now().isoformat()
                }
                return

            # This would integrate with a more sophisticated streaming workflow
            # For now, execute the workflow and provide updates
            yield {
                "type": "progress",
                "workflow_id": workflow_id,
                "stage": "content_analysis",
                "message": "Analyzing content for key concepts",
                "timestamp": datetime.now().isoformat()
            }

            # Execute workflow (in future, this could be made streaming)
            content_metadata = {
                "title": content.title,
                "content_type": content.content_type,
                "source_url": content.source_url
            }

            workflow_result = await self.workflow.execute(
                content_id=str(request.content_id),
                content_text=content.processed_content,
                content_metadata=content_metadata
            )

            if workflow_result["status"] == "failed":
                yield {
                    "type": "error",
                    "workflow_id": workflow_id,
                    "message": "Workflow execution failed",
                    "details": workflow_result.get("metadata", {}),
                    "timestamp": datetime.now().isoformat()
                }
                return

            yield {
                "type": "progress",
                "workflow_id": workflow_id,
                "stage": "saving_results",
                "message": f"Saving {len(workflow_result['prompts'])} prompts to database",
                "timestamp": datetime.now().isoformat()
            }

            # Save results
            saved_prompts = await self._save_prompts_to_database(
                content_id=request.content_id,
                prompts=workflow_result["prompts"],
                workflow_metadata=workflow_result["metadata"]
            )

            # Final result
            yield {
                "type": "completed",
                "workflow_id": workflow_id,
                "prompts": [self._format_prompt_response(p) for p in saved_prompts],
                "metadata": workflow_result.get("metadata", {}),
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Streaming prompt generation failed: {e}")
            yield {
                "type": "error",
                "workflow_id": workflow_id,
                "message": f"Prompt generation failed: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }

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
        try:
            # Fetch content
            content = await self.content_repo.get_by_id(content_id)
            if not content:
                return {"error": f"Content with ID {content_id} not found"}

            # Execute preview workflow
            preview_result = await self.workflow.execute_preview(
                content_text=content.processed_content,
                max_prompts=5
            )

            return preview_result

        except Exception as e:
            logger.error(f"Content preview failed: {e}")
            return {"error": str(e)}

    async def get_cost_estimate(
        self,
        content_id: uuid.UUID,
        target_prompts: int = None
    ) -> Dict[str, Any]:
        """
        Estimate costs for prompt generation.

        Args:
            content_id: ID of content to process
            target_prompts: Target number of prompts to generate

        Returns:
            Cost estimate breakdown
        """
        try:
            # Fetch content to analyze length
            content = await self.content_repo.get_by_id(content_id)
            if not content:
                return {"error": f"Content with ID {content_id} not found"}

            content_length = len(content.processed_content)
            estimated_prompts = target_prompts or min(content_length // 500, 20)  # Rough estimate

            # Estimate token usage and costs
            # These are rough estimates - actual costs depend on model responses
            estimated_input_tokens = {
                "content_analysis": content_length * 1.3,  # Content + prompts
                "prompt_generation": content_length * 0.5 + estimated_prompts * 100,
                "quality_review": estimated_prompts * 200,  # Review prompts
                "refinement": estimated_prompts * 150 * 0.3  # Assume 30% need refinement
            }

            estimated_output_tokens = {
                "content_analysis": 500,  # Analysis output
                "prompt_generation": estimated_prompts * 100,  # Generated prompts
                "quality_review": estimated_prompts * 150,  # Quality feedback
                "refinement": estimated_prompts * 100 * 0.3  # Refined prompts
            }

            # Calculate costs by model
            cost_breakdown = {}
            total_cost = 0.0

            # GPT-5-nano for content analysis
            nano_input = estimated_input_tokens["content_analysis"]
            nano_output = estimated_output_tokens["content_analysis"]
            nano_cost = (nano_input / 1_000_000) * 0.05 + (nano_output / 1_000_000) * 0.40
            cost_breakdown["content_analysis"] = {"model": "gpt-5-nano", "cost": nano_cost}
            total_cost += nano_cost

            # GPT-5-mini for generation and refinement
            mini_input = estimated_input_tokens["prompt_generation"] + estimated_input_tokens["refinement"]
            mini_output = estimated_output_tokens["prompt_generation"] + estimated_output_tokens["refinement"]
            mini_cost = (mini_input / 1_000_000) * 0.25 + (mini_output / 1_000_000) * 2.0
            cost_breakdown["generation_refinement"] = {"model": "gpt-5-mini", "cost": mini_cost}
            total_cost += mini_cost

            # GPT-5-standard for quality review
            standard_input = estimated_input_tokens["quality_review"]
            standard_output = estimated_output_tokens["quality_review"]
            standard_cost = (standard_input / 1_000_000) * 1.25 + (standard_output / 1_000_000) * 10.0
            cost_breakdown["quality_review"] = {"model": "gpt-5-standard", "cost": standard_cost}
            total_cost += standard_cost

            return {
                "estimated_total_cost": round(total_cost, 4),
                "estimated_prompts": estimated_prompts,
                "content_length": content_length,
                "cost_breakdown": cost_breakdown,
                "disclaimer": "This is an estimate. Actual costs may vary based on model responses and iterations."
            }

        except Exception as e:
            logger.error(f"Cost estimation failed: {e}")
            return {"error": str(e)}

    async def _save_prompts_to_database(
        self,
        content_id: uuid.UUID,
        prompts: List[Dict[str, Any]],
        workflow_metadata: Dict[str, Any]
    ) -> List[Any]:
        """Save generated prompts to the database."""
        saved_prompts = []

        for prompt_data in prompts:
            # Create prompt
            prompt_create = PromptCreate(
                content_id=content_id,
                question=prompt_data["question"],
                answer=prompt_data["answer"],
                prompt_type=prompt_data.get("prompt_type", PromptType.FACTUAL),
                confidence_score=prompt_data.get("confidence_score"),
                difficulty_level=prompt_data.get("difficulty_level"),
                source_context=prompt_data.get("source_context"),
                tags=prompt_data.get("tags", []),
                metadata={
                    **prompt_data.get("metadata", {}),
                    "workflow_metadata": workflow_metadata
                }
            )

            saved_prompt = await self.prompt_repo.create(prompt_create)
            saved_prompts.append(saved_prompt)

        return saved_prompts

    async def _save_quality_metrics(
        self,
        saved_prompts: List[Any],
        quality_analysis: Dict[str, Any]
    ) -> None:
        """Save quality metrics to the database."""
        quality_scores = quality_analysis.get("scores", [])

        for i, prompt in enumerate(saved_prompts):
            if i < len(quality_scores):
                score_data = quality_scores[i]

                # Create quality metrics for each dimension
                for dimension, score in score_data.get("dimensions", {}).items():
                    metric_create = QualityMetricCreate(
                        prompt_id=prompt.id,
                        metric_type=self._map_dimension_to_metric_type(dimension),
                        score=score,
                        weight=1.0,
                        evaluator_model=score_data.get("reviewer_model", "unknown"),
                        reasoning=score_data.get("feedback", {}).get(dimension, ""),
                        feedback={
                            "dimension": dimension,
                            "issues": score_data.get("key_issues", []),
                            "strengths": score_data.get("strengths", [])
                        },
                        metadata={
                            "overall_score": score_data.get("overall_score"),
                            "needs_revision": score_data.get("needs_revision")
                        }
                    )

                    await self.prompt_repo.create_quality_metric(metric_create)

    def _map_dimension_to_metric_type(self, dimension: str) -> QualityMetricType:
        """Map quality dimension to database metric type."""
        mapping = {
            "focused_and_specific": QualityMetricType.CLARITY,
            "precise_language": QualityMetricType.PRECISION,
            "appropriate_cognitive_load": QualityMetricType.COGNITIVE_LOAD,
            "meaningful_retrieval": QualityMetricType.RETRIEVAL_STRENGTH,
            "contextual_cues": QualityMetricType.CONTEXT_SUFFICIENCY,
            "factual_accuracy": QualityMetricType.ACCURACY,
            "difficulty_appropriateness": QualityMetricType.DIFFICULTY_MATCH,
            "answer_completeness": QualityMetricType.COMPLETENESS
        }

        return mapping.get(dimension, QualityMetricType.OVERALL)

    def _format_prompt_response(self, prompt: Any) -> Dict[str, Any]:
        """Format a database prompt for API response."""
        return {
            "id": str(prompt.id),
            "question": prompt.question,
            "answer": prompt.answer,
            "prompt_type": prompt.prompt_type,
            "confidence_score": prompt.confidence_score,
            "difficulty_level": prompt.difficulty_level,
            "source_context": prompt.source_context,
            "tags": prompt.tags,
            "metadata": prompt.metadata,
            "created_at": prompt.created_at.isoformat() if prompt.created_at else None
        }

    async def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """Get the status of a running workflow."""
        # This would integrate with a workflow tracking system
        # For now, return a placeholder
        return {
            "workflow_id": workflow_id,
            "status": "completed",  # Would track actual status
            "message": "Workflow status tracking not yet implemented"
        }