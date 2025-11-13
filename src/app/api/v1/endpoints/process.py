# ABOUTME: API endpoints for Claude SDK-based content processing workflow
# ABOUTME: Handles URL processing requests and workflow status queries
"""
Content Processing API Endpoints

FastAPI endpoints for Claude Agent SDK-based content processing.
Handles URL processing requests with multi-agent orchestration and
workflow status tracking.
"""

import uuid
import logging
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.api.dependencies import get_database_session
from src.app.services.content_processor import ContentProcessorService
from src.app.schemas.claude_workflow import (
    ContentProcessRequest,
    ContentProcessResponse,
    WorkflowStatusResponse,
    WorkflowMetrics,
    SubagentResult,
    PromptSummary
)
from src.app.db.models import Content, Prompt, ProcessingStatus, PromptStatus
from sqlalchemy import select


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/process", tags=["Processing"])


# Singleton service instance
# Note: In production, consider using dependency injection with proper lifecycle management
_processor_service: ContentProcessorService = None


def get_processor_service() -> ContentProcessorService:
    """Get or create ContentProcessorService singleton instance."""
    global _processor_service
    if _processor_service is None:
        _processor_service = ContentProcessorService(
            quality_threshold=0.7,
            max_iterations=3
        )
    return _processor_service


@router.post(
    "/url",
    response_model=ContentProcessResponse,
    status_code=status.HTTP_200_OK,
    summary="Process URL Content",
    description="Process URL into flashcards using Claude Agent SDK multi-agent workflow"
)
async def process_url(
    request: ContentProcessRequest,
    db: AsyncSession = Depends(get_database_session),
    processor: ContentProcessorService = Depends(get_processor_service)
) -> ContentProcessResponse:
    """
    Process a URL into flashcards using Claude Agent SDK.

    This endpoint orchestrates a multi-agent workflow:
    1. Fetch content from URL (via JinaAI)
    2. Analyze content for key concepts
    3. Generate prompts following Andy Matuschak's principles
    4. Review quality and refine if needed
    5. Save approved prompts to database
    6. Optionally create cards in Mochi

    Args:
        request: Content processing request with URL and parameters
        db: Database session
        processor: Content processor service instance

    Returns:
        ContentProcessResponse with workflow results, metrics, and generated prompts

    Raises:
        HTTPException: If processing fails or URL is invalid
    """
    logger.info(f"Processing URL: {request.url}")

    try:
        # Update processor configuration from request
        processor.quality_threshold = request.quality_threshold
        processor.max_iterations = request.max_iterations

        # Execute the workflow
        workflow_result = await processor.process_url(
            url=request.url,
            auto_approve=request.auto_approve
        )

        if workflow_result.get("status") == "failed":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Workflow failed: {workflow_result.get('error', 'Unknown error')}"
            )

        # Query database for the created content and prompts
        content_id = uuid.UUID(workflow_result["content_id"])

        # Get content record
        content_stmt = select(Content).where(Content.id == content_id)
        content_result = await db.execute(content_stmt)
        content = content_result.scalar_one_or_none()

        if not content:
            logger.warning(f"Content {content_id} not found in database after processing")
            # Continue anyway - the workflow completed but DB save may have failed

        # Get prompts for this content
        prompts_stmt = select(Prompt).where(Prompt.content_id == content_id)
        prompts_result = await db.execute(prompts_stmt)
        prompts = prompts_result.scalars().all()

        # Build response
        # Extract metrics from workflow result
        result_data = workflow_result.get("result", {}) or {}

        # Calculate metrics
        prompts_generated = len(prompts)
        prompts_approved = sum(1 for p in prompts if p.status == PromptStatus.APPROVED)
        avg_quality = sum(p.quality_score or 0.0 for p in prompts) / prompts_generated if prompts_generated > 0 else None

        # Build workflow metrics
        workflow_metrics = WorkflowMetrics(
            total_execution_time_seconds=workflow_result.get("duration_seconds", 0.0),
            total_input_tokens=0,  # TODO: Extract from result_data
            total_output_tokens=0,  # TODO: Extract from result_data
            total_cost_usd=workflow_result.get("cost_usd", 0.0),
            subagent_count=0,  # TODO: Extract from result_data
            successful_subagents=0,  # TODO: Extract from result_data
            failed_subagents=0,  # TODO: Extract from result_data
            iteration_count=1,  # TODO: Track iterations
            average_quality_score=avg_quality,
            quality_scores=[p.quality_score for p in prompts if p.quality_score is not None]
        )

        # Build prompt summaries
        prompt_summaries = [
            PromptSummary(
                id=p.id,
                front_content=p.front_content[:200] if p.front_content else "",
                back_content=p.back_content[:200] if p.back_content else "",
                quality_score=p.quality_score,
                status=p.status,
                iteration=1  # TODO: Track iteration in Prompt model
            )
            for p in prompts
        ]

        response = ContentProcessResponse(
            content_id=content_id,
            workflow_id=workflow_result["workflow_id"],
            status="completed",
            prompts_generated=prompts_generated,
            prompts_approved=prompts_approved,
            avg_quality_score=avg_quality,
            cost_usd=workflow_result.get("cost_usd", 0.0),
            processing_time_seconds=workflow_result.get("duration_seconds", 0.0),
            workflow_metrics=workflow_metrics,
            subagent_results=[],  # TODO: Extract from result_data
            prompts=prompt_summaries,
            error=None,
            metadata={
                "source_url": request.url,
                "auto_approve": request.auto_approve,
                "quality_threshold": request.quality_threshold,
                "max_iterations": request.max_iterations
            }
        )

        logger.info(f"Successfully processed URL. Content ID: {content_id}, Prompts: {prompts_generated}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing URL {request.url}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process URL: {str(e)}"
        )


@router.get(
    "/status/{workflow_id}",
    response_model=WorkflowStatusResponse,
    summary="Get Workflow Status",
    description="Query the status of a content processing workflow"
)
async def get_workflow_status(
    workflow_id: str,
    db: AsyncSession = Depends(get_database_session)
) -> WorkflowStatusResponse:
    """
    Get the current status of a content processing workflow.

    Queries the database for content records with the given workflow_id
    in their metadata and returns the current processing status.

    Args:
        workflow_id: Unique workflow identifier
        db: Database session

    Returns:
        WorkflowStatusResponse with current status and progress

    Raises:
        HTTPException: If workflow not found or query fails
    """
    logger.info(f"Querying workflow status: {workflow_id}")

    try:
        # Query for content with this workflow_id in metadata
        # Note: This is a simplified implementation. For production, consider
        # a dedicated Workflow table with proper indexing.
        stmt = select(Content).where(
            Content.content_metadata['workflow_id'].astext == workflow_id
        )
        result = await db.execute(stmt)
        content = result.scalar_one_or_none()

        if not content:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow {workflow_id} not found"
            )

        # Map processing status to workflow status
        status_map = {
            ProcessingStatus.PENDING: "pending",
            ProcessingStatus.PROCESSING: "running",
            ProcessingStatus.COMPLETED: "completed",
            ProcessingStatus.FAILED: "failed",
            ProcessingStatus.SKIPPED: "failed"
        }

        workflow_status = status_map.get(content.processing_status, "unknown")

        # Calculate progress based on status
        progress_map = {
            "pending": 0.0,
            "running": 0.5,  # Midpoint - could be more granular
            "completed": 1.0,
            "failed": 0.0
        }
        progress = progress_map.get(workflow_status, 0.0)

        # Calculate elapsed time
        elapsed = (content.updated_at - content.created_at).total_seconds()

        # Estimate remaining time (simplified - could be improved with actual stage tracking)
        estimated_remaining = None
        if workflow_status == "running" and elapsed > 0:
            estimated_remaining = elapsed  # Rough estimate: same time remaining as elapsed

        response = WorkflowStatusResponse(
            workflow_id=workflow_id,
            status=workflow_status,
            progress=progress,
            current_stage=content.processing_status.value if content.processing_status else None,
            started_at=content.created_at,
            completed_at=content.processed_at,
            elapsed_seconds=elapsed,
            estimated_remaining_seconds=estimated_remaining
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying workflow status {workflow_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query workflow status: {str(e)}"
        )
