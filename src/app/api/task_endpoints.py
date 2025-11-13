"""
FastAPI endpoints for Celery task management and monitoring.

Provides REST API endpoints for triggering background tasks,
monitoring progress, and retrieving task results.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query
from pydantic import BaseModel, Field
import structlog

from app.tasks.content_tasks import (
    process_url_content,
    batch_process_content,
    generate_embeddings,
    detect_duplicates
)
from app.tasks.agent_tasks import (
    generate_prompts,
    review_prompt_quality,
    refine_prompts,
    orchestrate_content_pipeline
)
from app.tasks.sync_tasks import (
    create_mochi_card,
    batch_sync_cards,
    sync_deck_metadata
)
from app.tasks.maintenance_tasks import (
    health_check,
    cleanup_old_data,
    aggregate_analytics
)
from app.tasks.monitoring import task_monitor
from app.tasks.task_utils import wait_for_task_completion

logger = structlog.get_logger()

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


# Pydantic models for request/response
class TaskTriggerResponse(BaseModel):
    """Response model for task triggers."""
    task_id: str
    task_name: str
    status: str = "PENDING"
    message: str = "Task has been queued for processing"
    estimated_duration: Optional[int] = Field(None, description="Estimated duration in seconds")


class TaskStatusResponse(BaseModel):
    """Response model for task status."""
    task_id: str
    status: str
    progress: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None


class BatchTaskRequest(BaseModel):
    """Request model for batch operations."""
    items: List[str]
    batch_options: Optional[Dict[str, Any]] = Field(default_factory=dict)
    processing_options: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ContentProcessingRequest(BaseModel):
    """Request model for content processing."""
    url: str
    options: Optional[Dict[str, Any]] = Field(default_factory=dict)
    user_id: Optional[str] = None


class PromptGenerationRequest(BaseModel):
    """Request model for prompt generation."""
    content_id: str
    generation_options: Optional[Dict[str, Any]] = Field(default_factory=dict)


class MochiSyncRequest(BaseModel):
    """Request model for Mochi synchronization."""
    prompt_ids: List[str]
    deck_id: Optional[str] = None
    card_options: Optional[Dict[str, Any]] = Field(default_factory=dict)


# Content Processing Endpoints
@router.post("/content/process-url", response_model=TaskTriggerResponse)
async def trigger_url_processing(request: ContentProcessingRequest):
    """Trigger background processing of a URL."""
    try:
        task = process_url_content.delay(
            url=request.url,
            user_id=request.user_id,
            options=request.options
        )

        logger.info("URL processing task triggered", task_id=task.id, url=request.url)

        return TaskTriggerResponse(
            task_id=task.id,
            task_name="process_url_content",
            estimated_duration=120  # 2 minutes estimate
        )

    except Exception as e:
        logger.error("Failed to trigger URL processing", url=request.url, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to trigger task: {str(e)}")


@router.post("/content/batch-process", response_model=TaskTriggerResponse)
async def trigger_batch_processing(request: BatchTaskRequest):
    """Trigger batch processing of multiple URLs."""
    try:
        if len(request.items) > 50:  # Limit batch size
            raise HTTPException(status_code=400, detail="Batch size cannot exceed 50 items")

        task = batch_process_content.delay(
            urls=request.items,
            batch_options={
                **request.batch_options,
                "processing_options": request.processing_options
            }
        )

        logger.info(
            "Batch processing task triggered",
            task_id=task.id,
            item_count=len(request.items)
        )

        return TaskTriggerResponse(
            task_id=task.id,
            task_name="batch_process_content",
            estimated_duration=len(request.items) * 30  # 30 seconds per item estimate
        )

    except Exception as e:
        logger.error("Failed to trigger batch processing", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to trigger task: {str(e)}")


@router.post("/content/generate-embeddings/{content_id}", response_model=TaskTriggerResponse)
async def trigger_embedding_generation(content_id: str):
    """Trigger vector embedding generation for content."""
    try:
        # This would typically get content from database first
        task = generate_embeddings.delay(
            content_id=content_id,
            markdown_content="",  # Would be fetched from database
            title=""
        )

        logger.info("Embedding generation task triggered", task_id=task.id, content_id=content_id)

        return TaskTriggerResponse(
            task_id=task.id,
            task_name="generate_embeddings",
            estimated_duration=60  # 1 minute estimate
        )

    except Exception as e:
        logger.error("Failed to trigger embedding generation", content_id=content_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to trigger task: {str(e)}")


# AI Agent Endpoints
@router.post("/ai/generate-prompts", response_model=TaskTriggerResponse)
async def trigger_prompt_generation(request: PromptGenerationRequest):
    """Trigger AI prompt generation for content."""
    try:
        task = generate_prompts.delay(
            content_id=request.content_id,
            generation_options=request.generation_options
        )

        logger.info(
            "Prompt generation task triggered",
            task_id=task.id,
            content_id=request.content_id
        )

        return TaskTriggerResponse(
            task_id=task.id,
            task_name="generate_prompts",
            estimated_duration=180  # 3 minutes estimate
        )

    except Exception as e:
        logger.error("Failed to trigger prompt generation", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to trigger task: {str(e)}")


@router.post("/ai/review-quality", response_model=TaskTriggerResponse)
async def trigger_quality_review(
    prompt_ids: List[str],
    review_options: Optional[Dict[str, Any]] = None
):
    """Trigger quality review for generated prompts."""
    try:
        if len(prompt_ids) > 20:  # Limit review batch size
            raise HTTPException(status_code=400, detail="Cannot review more than 20 prompts at once")

        task = review_prompt_quality.delay(
            prompt_ids=prompt_ids,
            review_options=review_options or {}
        )

        logger.info(
            "Quality review task triggered",
            task_id=task.id,
            prompt_count=len(prompt_ids)
        )

        return TaskTriggerResponse(
            task_id=task.id,
            task_name="review_prompt_quality",
            estimated_duration=len(prompt_ids) * 15  # 15 seconds per prompt estimate
        )

    except Exception as e:
        logger.error("Failed to trigger quality review", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to trigger task: {str(e)}")


@router.post("/ai/orchestrate-pipeline", response_model=TaskTriggerResponse)
async def trigger_content_pipeline(
    content_id: str,
    pipeline_options: Optional[Dict[str, Any]] = None
):
    """Trigger the complete AI processing pipeline for content."""
    try:
        task = orchestrate_content_pipeline.delay(
            content_id=content_id,
            pipeline_options=pipeline_options or {}
        )

        logger.info(
            "Content pipeline task triggered",
            task_id=task.id,
            content_id=content_id
        )

        return TaskTriggerResponse(
            task_id=task.id,
            task_name="orchestrate_content_pipeline",
            estimated_duration=600  # 10 minutes estimate
        )

    except Exception as e:
        logger.error("Failed to trigger content pipeline", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to trigger task: {str(e)}")


# Mochi Sync Endpoints
@router.post("/mochi/create-card/{prompt_id}", response_model=TaskTriggerResponse)
async def trigger_mochi_card_creation(
    prompt_id: str,
    deck_id: Optional[str] = None,
    card_options: Optional[Dict[str, Any]] = None
):
    """Trigger creation of a Mochi card from a prompt."""
    try:
        task = create_mochi_card.delay(
            prompt_id=prompt_id,
            deck_id=deck_id,
            card_options=card_options or {}
        )

        logger.info("Mochi card creation task triggered", task_id=task.id, prompt_id=prompt_id)

        return TaskTriggerResponse(
            task_id=task.id,
            task_name="create_mochi_card",
            estimated_duration=30  # 30 seconds estimate
        )

    except Exception as e:
        logger.error("Failed to trigger Mochi card creation", prompt_id=prompt_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to trigger task: {str(e)}")


@router.post("/mochi/batch-sync", response_model=TaskTriggerResponse)
async def trigger_mochi_batch_sync(request: MochiSyncRequest):
    """Trigger batch synchronization to Mochi."""
    try:
        if len(request.prompt_ids) > 30:  # Limit batch size
            raise HTTPException(status_code=400, detail="Cannot sync more than 30 prompts at once")

        task = batch_sync_cards.delay(
            prompt_ids=request.prompt_ids,
            batch_options={
                "deck_id": request.deck_id,
                "card_options": request.card_options,
                "batch_size": 5,  # Conservative batch size for API limits
            }
        )

        logger.info(
            "Mochi batch sync task triggered",
            task_id=task.id,
            prompt_count=len(request.prompt_ids)
        )

        return TaskTriggerResponse(
            task_id=task.id,
            task_name="batch_sync_cards",
            estimated_duration=len(request.prompt_ids) * 10  # 10 seconds per card estimate
        )

    except Exception as e:
        logger.error("Failed to trigger Mochi batch sync", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to trigger task: {str(e)}")


@router.post("/mochi/sync-decks", response_model=TaskTriggerResponse)
async def trigger_deck_sync(deck_id: Optional[str] = None):
    """Trigger synchronization of deck metadata."""
    try:
        task = sync_deck_metadata.delay(deck_id=deck_id)

        logger.info("Deck sync task triggered", task_id=task.id, deck_id=deck_id)

        return TaskTriggerResponse(
            task_id=task.id,
            task_name="sync_deck_metadata",
            estimated_duration=60  # 1 minute estimate
        )

    except Exception as e:
        logger.error("Failed to trigger deck sync", deck_id=deck_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to trigger task: {str(e)}")


# Task Status and Monitoring Endpoints
@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """Get the current status and progress of a task."""
    try:
        # Get progress from monitoring system
        progress = await task_monitor.get_task_progress(task_id)

        if not progress:
            raise HTTPException(status_code=404, detail="Task not found")

        return TaskStatusResponse(
            task_id=task_id,
            status=progress.get("status", "UNKNOWN"),
            progress=progress,
            result=progress.get("result"),
            error=progress.get("error"),
            created_at=progress.get("created_at"),
            completed_at=progress.get("completed_at")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get task status", task_id=task_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get task status: {str(e)}")


@router.get("/batch-status/{batch_id}")
async def get_batch_status(batch_id: str):
    """Get the status of a batch operation."""
    try:
        batch_progress = await task_monitor.get_batch_progress(batch_id)

        if not batch_progress:
            raise HTTPException(status_code=404, detail="Batch not found")

        return batch_progress

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get batch status", batch_id=batch_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get batch status: {str(e)}")


@router.get("/active")
async def get_active_tasks(
    task_types: Optional[List[str]] = Query(None, description="Filter by task types")
):
    """Get information about currently active tasks."""
    try:
        active_tasks = await task_monitor.get_active_tasks(task_types=task_types)
        return active_tasks

    except Exception as e:
        logger.error("Failed to get active tasks", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get active tasks: {str(e)}")


@router.get("/metrics/{task_name}")
async def get_task_metrics(
    task_name: str,
    hours: int = Query(24, description="Hours of metrics to retrieve")
):
    """Get performance metrics for a specific task type."""
    try:
        metrics = await task_monitor.get_task_metrics(task_name=task_name, hours=hours)
        return metrics

    except Exception as e:
        logger.error("Failed to get task metrics", task_name=task_name, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get task metrics: {str(e)}")


# Maintenance Endpoints
@router.post("/maintenance/health-check", response_model=TaskTriggerResponse)
async def trigger_health_check(check_external: bool = Query(True)):
    """Trigger a comprehensive system health check."""
    try:
        task = health_check.delay(check_external=check_external)

        logger.info("Health check task triggered", task_id=task.id)

        return TaskTriggerResponse(
            task_id=task.id,
            task_name="health_check",
            estimated_duration=30  # 30 seconds estimate
        )

    except Exception as e:
        logger.error("Failed to trigger health check", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to trigger task: {str(e)}")


@router.post("/maintenance/cleanup", response_model=TaskTriggerResponse)
async def trigger_data_cleanup(retention_days: int = Query(30, ge=1, le=365)):
    """Trigger cleanup of old data."""
    try:
        task = cleanup_old_data.delay(retention_days=retention_days)

        logger.info("Data cleanup task triggered", task_id=task.id, retention_days=retention_days)

        return TaskTriggerResponse(
            task_id=task.id,
            task_name="cleanup_old_data",
            estimated_duration=300  # 5 minutes estimate
        )

    except Exception as e:
        logger.error("Failed to trigger data cleanup", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to trigger task: {str(e)}")


@router.post("/maintenance/analytics", response_model=TaskTriggerResponse)
async def trigger_analytics_aggregation(period: str = Query("daily", regex="^(daily|weekly|monthly)$")):
    """Trigger analytics data aggregation."""
    try:
        task = aggregate_analytics.delay(period=period)

        logger.info("Analytics aggregation task triggered", task_id=task.id, period=period)

        return TaskTriggerResponse(
            task_id=task.id,
            task_name="aggregate_analytics",
            estimated_duration=120  # 2 minutes estimate
        )

    except Exception as e:
        logger.error("Failed to trigger analytics aggregation", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to trigger task: {str(e)}")


# Utility Endpoints
@router.post("/wait/{task_id}")
async def wait_for_task(
    task_id: str,
    timeout: int = Query(300, ge=5, le=1800, description="Timeout in seconds")
):
    """Wait for a task to complete (with timeout)."""
    try:
        result = await wait_for_task_completion(
            task_id=task_id,
            timeout_seconds=timeout
        )

        if not result.get("completed"):
            raise HTTPException(status_code=408, detail="Task did not complete within timeout")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to wait for task", task_id=task_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to wait for task: {str(e)}")


@router.delete("/cancel/{task_id}")
async def cancel_task(task_id: str):
    """Cancel a running task."""
    try:
        from app.tasks.celery_app import celery_app

        # Revoke the task
        celery_app.control.revoke(task_id, terminate=True)

        logger.info("Task cancellation requested", task_id=task_id)

        return {"task_id": task_id, "status": "REVOKED", "message": "Task cancellation requested"}

    except Exception as e:
        logger.error("Failed to cancel task", task_id=task_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to cancel task: {str(e)}")


# Dashboard endpoint for task overview
@router.get("/dashboard")
async def get_task_dashboard():
    """Get comprehensive task dashboard information."""
    try:
        # Get various task statistics
        active_tasks = await task_monitor.get_active_tasks()

        # Get recent metrics for key task types
        key_tasks = [
            "process_url_content",
            "generate_prompts",
            "create_mochi_card",
            "batch_process_content"
        ]

        task_metrics = {}
        for task_name in key_tasks:
            try:
                metrics = await task_monitor.get_task_metrics(task_name, hours=24)
                task_metrics[task_name] = metrics
            except Exception as e:
                logger.warning("Failed to get metrics for task", task_name=task_name, error=str(e))
                task_metrics[task_name] = {"error": str(e)}

        dashboard_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "active_tasks": active_tasks,
            "task_metrics": task_metrics,
            "system_health": {
                "status": "healthy",  # Would be determined by health checks
                "last_check": datetime.utcnow().isoformat(),
            }
        }

        return dashboard_data

    except Exception as e:
        logger.error("Failed to get task dashboard", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard: {str(e)}")