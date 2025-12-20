# ABOUTME: FastAPI endpoints for background task management and monitoring
# ABOUTME: Uses native async/await with BackgroundTasks (replaces Celery)

import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, Field
import structlog

from app.background.tasks import (
    process_url,
    batch_process,
    generate_embeddings,
    detect_duplicates,
    generate_prompts,
    review_quality,
    refine_prompts,
    create_card,
    batch_sync,
    sync_decks,
    health_check,
    cleanup_old_data,
    aggregate_analytics,
)
from app.background.progress import get_progress_tracker

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
    content_text: str
    generation_options: Optional[Dict[str, Any]] = Field(default_factory=dict)


class MochiSyncRequest(BaseModel):
    """Request model for Mochi synchronization."""
    prompt_ids: List[str]
    deck_id: Optional[str] = None
    card_options: Optional[Dict[str, Any]] = Field(default_factory=dict)


def generate_task_id() -> str:
    """Generate a unique task ID."""
    return str(uuid.uuid4())


# Content Processing Endpoints
@router.post("/content/process-url", response_model=TaskTriggerResponse)
async def trigger_url_processing(
    request: ContentProcessingRequest,
    background_tasks: BackgroundTasks
):
    """Trigger background processing of a URL."""
    task_id = generate_task_id()
    tracker = get_progress_tracker()

    try:
        # Create progress entry
        tracker.create(task_id, "process_url", metadata={"url": request.url})

        # Add to background tasks
        background_tasks.add_task(
            process_url,
            url=request.url,
            task_id=task_id,
            user_id=request.user_id,
            options=request.options
        )

        logger.info("URL processing task triggered", task_id=task_id, url=request.url)

        return TaskTriggerResponse(
            task_id=task_id,
            task_name="process_url",
            estimated_duration=120
        )

    except Exception as e:
        logger.error("Failed to trigger URL processing", url=request.url, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to trigger task: {str(e)}")


@router.post("/content/batch-process", response_model=TaskTriggerResponse)
async def trigger_batch_processing(
    request: BatchTaskRequest,
    background_tasks: BackgroundTasks
):
    """Trigger batch processing of multiple URLs."""
    task_id = generate_task_id()
    tracker = get_progress_tracker()

    try:
        if len(request.items) > 50:
            raise HTTPException(status_code=400, detail="Batch size cannot exceed 50 items")

        tracker.create(task_id, "batch_process", total=len(request.items))

        background_tasks.add_task(
            batch_process,
            urls=request.items,
            task_id=task_id,
            batch_options={
                **request.batch_options,
                "processing_options": request.processing_options
            }
        )

        logger.info("Batch processing task triggered", task_id=task_id, item_count=len(request.items))

        return TaskTriggerResponse(
            task_id=task_id,
            task_name="batch_process",
            estimated_duration=len(request.items) * 30
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to trigger batch processing", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to trigger task: {str(e)}")


@router.post("/content/generate-embeddings/{content_id}", response_model=TaskTriggerResponse)
async def trigger_embedding_generation(
    content_id: str,
    background_tasks: BackgroundTasks
):
    """Trigger vector embedding generation for content."""
    task_id = generate_task_id()
    tracker = get_progress_tracker()

    try:
        tracker.create(task_id, "generate_embeddings", metadata={"content_id": content_id})

        # In a real implementation, fetch content from database first
        background_tasks.add_task(
            generate_embeddings,
            content_id=content_id,
            markdown_content="",  # Would be fetched from database
            title=""
        )

        logger.info("Embedding generation task triggered", task_id=task_id, content_id=content_id)

        return TaskTriggerResponse(
            task_id=task_id,
            task_name="generate_embeddings",
            estimated_duration=60
        )

    except Exception as e:
        logger.error("Failed to trigger embedding generation", content_id=content_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to trigger task: {str(e)}")


# AI Agent Endpoints
@router.post("/ai/generate-prompts", response_model=TaskTriggerResponse)
async def trigger_prompt_generation(
    request: PromptGenerationRequest,
    background_tasks: BackgroundTasks
):
    """Trigger AI prompt generation for content."""
    task_id = generate_task_id()
    tracker = get_progress_tracker()

    try:
        tracker.create(task_id, "generate_prompts", metadata={"content_id": request.content_id})

        background_tasks.add_task(
            generate_prompts,
            content_id=request.content_id,
            content_text=request.content_text,
            model=request.generation_options.get("model", "sonnet")
        )

        logger.info("Prompt generation task triggered", task_id=task_id, content_id=request.content_id)

        return TaskTriggerResponse(
            task_id=task_id,
            task_name="generate_prompts",
            estimated_duration=180
        )

    except Exception as e:
        logger.error("Failed to trigger prompt generation", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to trigger task: {str(e)}")


@router.post("/ai/review-quality", response_model=TaskTriggerResponse)
async def trigger_quality_review(
    prompt_id: str,
    prompt_text: str,
    background_tasks: BackgroundTasks
):
    """Trigger quality review for a generated prompt."""
    task_id = generate_task_id()
    tracker = get_progress_tracker()

    try:
        tracker.create(task_id, "review_quality", metadata={"prompt_id": prompt_id})

        background_tasks.add_task(
            review_quality,
            prompt_id=prompt_id,
            prompt_text=prompt_text
        )

        logger.info("Quality review task triggered", task_id=task_id, prompt_id=prompt_id)

        return TaskTriggerResponse(
            task_id=task_id,
            task_name="review_quality",
            estimated_duration=30
        )

    except Exception as e:
        logger.error("Failed to trigger quality review", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to trigger task: {str(e)}")


@router.post("/ai/refine-prompts", response_model=TaskTriggerResponse)
async def trigger_prompt_refinement(
    prompt_ids: List[str],
    feedback: str,
    background_tasks: BackgroundTasks
):
    """Trigger refinement of prompts based on feedback."""
    task_id = generate_task_id()
    tracker = get_progress_tracker()

    try:
        tracker.create(task_id, "refine_prompts", total=len(prompt_ids))

        background_tasks.add_task(
            refine_prompts,
            prompt_ids=prompt_ids,
            feedback=feedback
        )

        logger.info("Prompt refinement task triggered", task_id=task_id, count=len(prompt_ids))

        return TaskTriggerResponse(
            task_id=task_id,
            task_name="refine_prompts",
            estimated_duration=len(prompt_ids) * 20
        )

    except Exception as e:
        logger.error("Failed to trigger prompt refinement", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to trigger task: {str(e)}")


# Mochi Sync Endpoints
@router.post("/mochi/create-card/{prompt_id}", response_model=TaskTriggerResponse)
async def trigger_mochi_card_creation(
    prompt_id: str,
    background_tasks: BackgroundTasks,
    deck_id: Optional[str] = None,
    card_options: Optional[Dict[str, Any]] = None
):
    """Trigger creation of a Mochi card from a prompt."""
    task_id = generate_task_id()
    tracker = get_progress_tracker()

    try:
        tracker.create(task_id, "create_card", metadata={"prompt_id": prompt_id})

        background_tasks.add_task(
            create_card,
            prompt_id=prompt_id,
            deck_id=deck_id,
            card_options=card_options or {}
        )

        logger.info("Mochi card creation task triggered", task_id=task_id, prompt_id=prompt_id)

        return TaskTriggerResponse(
            task_id=task_id,
            task_name="create_card",
            estimated_duration=30
        )

    except Exception as e:
        logger.error("Failed to trigger Mochi card creation", prompt_id=prompt_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to trigger task: {str(e)}")


@router.post("/mochi/batch-sync", response_model=TaskTriggerResponse)
async def trigger_mochi_batch_sync(
    request: MochiSyncRequest,
    background_tasks: BackgroundTasks
):
    """Trigger batch synchronization to Mochi."""
    task_id = generate_task_id()
    tracker = get_progress_tracker()

    try:
        if len(request.prompt_ids) > 30:
            raise HTTPException(status_code=400, detail="Cannot sync more than 30 prompts at once")

        tracker.create(task_id, "batch_sync", total=len(request.prompt_ids))

        background_tasks.add_task(
            batch_sync,
            prompt_ids=request.prompt_ids,
            task_id=task_id,
            batch_options={
                "deck_id": request.deck_id,
                "card_options": request.card_options,
                "batch_size": 5,
            }
        )

        logger.info("Mochi batch sync task triggered", task_id=task_id, prompt_count=len(request.prompt_ids))

        return TaskTriggerResponse(
            task_id=task_id,
            task_name="batch_sync",
            estimated_duration=len(request.prompt_ids) * 10
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to trigger Mochi batch sync", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to trigger task: {str(e)}")


@router.post("/mochi/sync-decks", response_model=TaskTriggerResponse)
async def trigger_deck_sync(
    background_tasks: BackgroundTasks,
    deck_id: Optional[str] = None
):
    """Trigger synchronization of deck metadata."""
    task_id = generate_task_id()
    tracker = get_progress_tracker()

    try:
        tracker.create(task_id, "sync_decks")

        background_tasks.add_task(sync_decks, deck_id=deck_id)

        logger.info("Deck sync task triggered", task_id=task_id, deck_id=deck_id)

        return TaskTriggerResponse(
            task_id=task_id,
            task_name="sync_decks",
            estimated_duration=60
        )

    except Exception as e:
        logger.error("Failed to trigger deck sync", deck_id=deck_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to trigger task: {str(e)}")


# Task Status and Monitoring Endpoints
@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """Get the current status and progress of a task."""
    try:
        tracker = get_progress_tracker()
        progress = tracker.get_dict(task_id)

        if not progress:
            raise HTTPException(status_code=404, detail="Task not found")

        return TaskStatusResponse(
            task_id=task_id,
            status=progress.get("status", "UNKNOWN"),
            progress=progress,
            result=progress.get("result"),
            error=progress.get("error"),
            created_at=progress.get("started_at"),
            completed_at=progress.get("completed_at")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get task status", task_id=task_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get task status: {str(e)}")


@router.get("/active")
async def get_active_tasks(
    task_types: Optional[List[str]] = Query(None, description="Filter by task types")
):
    """Get information about currently active tasks."""
    try:
        tracker = get_progress_tracker()
        active_tasks = tracker.list_active()

        if task_types:
            active_tasks = [t for t in active_tasks if t.task_type in task_types]

        return {
            "active_count": len(active_tasks),
            "tasks": [t.to_dict() for t in active_tasks],
        }

    except Exception as e:
        logger.error("Failed to get active tasks", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get active tasks: {str(e)}")


# Maintenance Endpoints
@router.post("/maintenance/health-check", response_model=TaskTriggerResponse)
async def trigger_health_check_task(
    background_tasks: BackgroundTasks,
    check_external: bool = Query(True)
):
    """Trigger a comprehensive system health check."""
    task_id = generate_task_id()
    tracker = get_progress_tracker()

    try:
        tracker.create(task_id, "health_check")

        background_tasks.add_task(health_check, check_external=check_external)

        logger.info("Health check task triggered", task_id=task_id)

        return TaskTriggerResponse(
            task_id=task_id,
            task_name="health_check",
            estimated_duration=30
        )

    except Exception as e:
        logger.error("Failed to trigger health check", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to trigger task: {str(e)}")


@router.post("/maintenance/cleanup", response_model=TaskTriggerResponse)
async def trigger_data_cleanup(
    background_tasks: BackgroundTasks,
    retention_days: int = Query(30, ge=1, le=365)
):
    """Trigger cleanup of old data."""
    task_id = generate_task_id()
    tracker = get_progress_tracker()

    try:
        tracker.create(task_id, "cleanup_old_data", metadata={"retention_days": retention_days})

        background_tasks.add_task(cleanup_old_data, retention_days=retention_days)

        logger.info("Data cleanup task triggered", task_id=task_id, retention_days=retention_days)

        return TaskTriggerResponse(
            task_id=task_id,
            task_name="cleanup_old_data",
            estimated_duration=300
        )

    except Exception as e:
        logger.error("Failed to trigger data cleanup", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to trigger task: {str(e)}")


@router.post("/maintenance/analytics", response_model=TaskTriggerResponse)
async def trigger_analytics_aggregation(
    background_tasks: BackgroundTasks,
    period: str = Query("daily", pattern="^(daily|weekly|monthly)$")
):
    """Trigger analytics data aggregation."""
    task_id = generate_task_id()
    tracker = get_progress_tracker()

    try:
        tracker.create(task_id, "aggregate_analytics", metadata={"period": period})

        background_tasks.add_task(aggregate_analytics, period=period)

        logger.info("Analytics aggregation task triggered", task_id=task_id, period=period)

        return TaskTriggerResponse(
            task_id=task_id,
            task_name="aggregate_analytics",
            estimated_duration=120
        )

    except Exception as e:
        logger.error("Failed to trigger analytics aggregation", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to trigger task: {str(e)}")


# Dashboard endpoint for task overview
@router.get("/dashboard")
async def get_task_dashboard():
    """Get comprehensive task dashboard information."""
    try:
        tracker = get_progress_tracker()
        active_tasks = tracker.list_active()

        dashboard_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "active_tasks": {
                "count": len(active_tasks),
                "tasks": [t.to_dict() for t in active_tasks],
            },
            "system_health": {
                "status": "healthy",
                "last_check": datetime.utcnow().isoformat(),
            }
        }

        return dashboard_data

    except Exception as e:
        logger.error("Failed to get task dashboard", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard: {str(e)}")
