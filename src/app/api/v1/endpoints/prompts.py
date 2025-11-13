# Prompt API Endpoints
"""
FastAPI endpoints for prompt management, quality review, and Mochi integration.
Handles CRUD operations, batch updates, and quality metrics.
"""

import uuid
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_prompt_repository,
    get_prompt_generator_service,
    get_pagination_params,
    PaginationParams,
    APIResponse,
    validate_prompt_exists,
    validate_content_exists
)
from app.repositories.prompt import PromptRepository
from app.services.prompt_generator import PromptGeneratorService
from app.schemas.prompt import (
    PromptCreate,
    PromptUpdate,
    PromptResponse,
    PromptSummary,
    PromptWithQuality,
    PromptGenerationRequest,
    PromptGenerationResponse,
    PromptBatchUpdate,
    PromptBatchUpdateResponse,
    PromptSearchRequest,
    PromptSearchResponse,
    PromptStatistics,
    QualityMetricCreate,
    QualityMetricResponse,
    MochiCardRequest,
    MochiCardResponse,
    MochiBatchSyncRequest,
    MochiBatchSyncResponse
)
from app.db.models import PromptType, PromptStatus, QualityMetricType


router = APIRouter()


@router.post(
    "/",
    response_model=PromptResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Prompt",
    description="Create a new prompt manually"
)
async def create_prompt(
    prompt_data: PromptCreate,
    prompt_repo: PromptRepository = Depends(get_prompt_repository)
) -> PromptResponse:
    """Create a new prompt."""
    try:
        prompt = await prompt_repo.create(prompt_data)
        return PromptResponse.model_validate(prompt)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create prompt"
        )


@router.get(
    "/",
    response_model=List[PromptSummary],
    summary="List Prompts",
    description="Get paginated list of prompts with optional filtering"
)
async def list_prompts(
    pagination: PaginationParams = Depends(get_pagination_params),
    content_id: Optional[str] = Query(None, description="Filter by content ID"),
    prompt_type: Optional[PromptType] = Query(None, description="Filter by prompt type"),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum confidence score"),
    is_edited: Optional[bool] = Query(None, description="Filter by edit status"),
    has_mochi_card: Optional[bool] = Query(None, description="Filter by Mochi card status"),
    prompt_repo: PromptRepository = Depends(get_prompt_repository)
) -> List[PromptSummary]:
    """Get paginated list of prompts."""
    filters = {}

    if content_id:
        try:
            filters["content_id"] = uuid.UUID(content_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid content ID format"
            )

    if prompt_type:
        filters["prompt_type"] = prompt_type
    if is_edited is not None:
        filters["is_edited"] = is_edited

    prompts = await prompt_repo.get_multi_with_filters(
        skip=pagination.skip,
        limit=pagination.limit,
        min_confidence=min_confidence,
        has_mochi_card=has_mochi_card,
        **filters
    )

    return [PromptSummary.model_validate(prompt) for prompt in prompts]


@router.get(
    "/{prompt_id}",
    response_model=PromptWithQuality,
    summary="Get Prompt",
    description="Get prompt by ID with quality metrics"
)
async def get_prompt(
    prompt_id: str,
    include_quality: bool = Query(True, description="Include quality metrics"),
    prompt_repo: PromptRepository = Depends(get_prompt_repository)
) -> PromptWithQuality:
    """Get prompt by ID."""
    try:
        prompt_uuid = uuid.UUID(prompt_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid prompt ID format"
        )

    if include_quality:
        prompt = await prompt_repo.get_with_quality(prompt_uuid)
    else:
        prompt = await prompt_repo.get(prompt_uuid)

    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found"
        )

    return PromptWithQuality.model_validate(prompt)


@router.put(
    "/{prompt_id}",
    response_model=PromptResponse,
    summary="Update Prompt",
    description="Update prompt and mark as edited"
)
async def update_prompt(
    prompt_id: str,
    prompt_data: PromptUpdate,
    prompt_repo: PromptRepository = Depends(get_prompt_repository)
) -> PromptResponse:
    """Update prompt by ID."""
    try:
        prompt_uuid = uuid.UUID(prompt_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid prompt ID format"
        )

    updated_prompt = await prompt_repo.update_with_history(prompt_uuid, prompt_data)
    if not updated_prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found"
        )

    return PromptResponse.model_validate(updated_prompt)


@router.delete(
    "/{prompt_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Prompt",
    description="Soft delete prompt by setting status to rejected"
)
async def delete_prompt(
    prompt_id: str,
    prompt_repo: PromptRepository = Depends(get_prompt_repository)
):
    """Soft delete prompt by ID."""
    try:
        prompt_uuid = uuid.UUID(prompt_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid prompt ID format"
        )

    # Soft delete by rejecting the prompt
    deleted_prompt = await prompt_repo.reject_prompt(
        prompt_uuid,
        rejection_reason="Deleted by user"
    )

    if not deleted_prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found"
        )


# Generation endpoints
@router.post(
    "/generate",
    response_model=PromptGenerationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate Prompts",
    description="Generate prompts from content using AI agents"
)
async def generate_prompts(
    generation_request: PromptGenerationRequest,
    background_tasks: BackgroundTasks,
    generator_service: PromptGeneratorService = Depends(get_prompt_generator_service)
) -> PromptGenerationResponse:
    """Generate prompts from content."""
    try:
        result = await generator_service.generate_prompts(
            generation_request,
            background_tasks
        )
        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate prompts"
        )


@router.post(
    "/batch-update",
    response_model=PromptBatchUpdateResponse,
    summary="Batch Update Prompts",
    description="Update multiple prompts in a single operation"
)
async def batch_update_prompts(
    batch_update: PromptBatchUpdate,
    prompt_repo: PromptRepository = Depends(get_prompt_repository)
) -> PromptBatchUpdateResponse:
    """Update multiple prompts in batch."""
    try:
        result = await prompt_repo.batch_update(batch_update.prompt_updates)
        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update prompts"
        )


# Quality metrics endpoints
@router.post(
    "/{prompt_id}/quality-metrics",
    response_model=QualityMetricResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add Quality Metric",
    description="Add quality metric to prompt"
)
async def add_quality_metric(
    prompt_id: str,
    metric_data: QualityMetricCreate,
    prompt_repo: PromptRepository = Depends(get_prompt_repository)
) -> QualityMetricResponse:
    """Add quality metric to prompt."""
    try:
        prompt_uuid = uuid.UUID(prompt_id)
        metric_data.prompt_id = prompt_uuid
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid prompt ID format"
        )

    # Verify prompt exists
    prompt = await prompt_repo.get(prompt_uuid)
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found"
        )

    metric = await prompt_repo.add_quality_metric(metric_data)
    return QualityMetricResponse.model_validate(metric)


@router.get(
    "/{prompt_id}/quality-metrics",
    response_model=List[QualityMetricResponse],
    summary="Get Quality Metrics",
    description="Get all quality metrics for a prompt"
)
async def get_quality_metrics(
    prompt_id: str,
    prompt_repo: PromptRepository = Depends(get_prompt_repository)
) -> List[QualityMetricResponse]:
    """Get quality metrics for prompt."""
    try:
        prompt_uuid = uuid.UUID(prompt_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid prompt ID format"
        )

    metrics = await prompt_repo.get_quality_metrics(prompt_uuid)
    return [QualityMetricResponse.model_validate(metric) for metric in metrics]


# Mochi integration endpoints
@router.post(
    "/{prompt_id}/mochi-card",
    response_model=MochiCardResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Mochi Card",
    description="Create Mochi card from prompt"
)
async def create_mochi_card(
    prompt_id: str,
    card_request: MochiCardRequest,
    background_tasks: BackgroundTasks,
    generator_service: PromptGeneratorService = Depends(get_prompt_generator_service)
) -> MochiCardResponse:
    """Create Mochi card from prompt."""
    try:
        prompt_uuid = uuid.UUID(prompt_id)
        card_request.prompt_id = prompt_uuid
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid prompt ID format"
        )

    try:
        result = await generator_service.create_mochi_card(
            card_request,
            background_tasks
        )
        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create Mochi card"
        )


@router.post(
    "/mochi-sync/batch",
    response_model=MochiBatchSyncResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Batch Sync to Mochi",
    description="Sync multiple prompts to Mochi in batch"
)
async def batch_sync_to_mochi(
    sync_request: MochiBatchSyncRequest,
    background_tasks: BackgroundTasks,
    generator_service: PromptGeneratorService = Depends(get_prompt_generator_service)
) -> MochiBatchSyncResponse:
    """Sync multiple prompts to Mochi."""
    try:
        result = await generator_service.batch_sync_to_mochi(
            sync_request,
            background_tasks
        )
        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sync to Mochi"
        )


# Analytics and statistics
@router.get(
    "/statistics",
    response_model=PromptStatistics,
    summary="Get Prompt Statistics",
    description="Get overall prompt statistics and metrics"
)
async def get_prompt_statistics(
    prompt_repo: PromptRepository = Depends(get_prompt_repository)
) -> PromptStatistics:
    """Get prompt statistics."""
    stats = await prompt_repo.get_statistics()
    return PromptStatistics.model_validate(stats)


@router.get(
    "/quality/review-needed",
    response_model=List[PromptSummary],
    summary="Get Prompts Needing Review",
    description="Get prompts that need quality review"
)
async def get_prompts_needing_review(
    pagination: PaginationParams = Depends(get_pagination_params),
    quality_threshold: float = Query(0.7, ge=0.0, le=1.0, description="Quality threshold"),
    prompt_repo: PromptRepository = Depends(get_prompt_repository)
) -> List[PromptSummary]:
    """Get prompts needing quality review."""
    prompts = await prompt_repo.get_prompts_needing_review(
        skip=pagination.skip,
        limit=pagination.limit,
        quality_threshold=quality_threshold
    )

    return [PromptSummary.model_validate(prompt) for prompt in prompts]


# Approval/rejection endpoints
@router.post(
    "/{prompt_id}/approve",
    response_model=PromptResponse,
    summary="Approve Prompt",
    description="Approve prompt and optionally create Mochi card"
)
async def approve_prompt(
    prompt_id: str,
    background_tasks: BackgroundTasks,
    prompt_repo: PromptRepository = Depends(get_prompt_repository),
    create_mochi_card: bool = Query(False, description="Auto-create Mochi card")
) -> PromptResponse:
    """Approve a prompt."""
    try:
        prompt_uuid = uuid.UUID(prompt_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid prompt ID format"
        )

    approved_prompt = await prompt_repo.approve_prompt(
        prompt_uuid,
        create_mochi_card=create_mochi_card
    )

    if not approved_prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found"
        )

    # TODO: If create_mochi_card is True, trigger Mochi card creation in background
    if create_mochi_card:
        # background_tasks.add_task(create_mochi_card_task, approved_prompt.id)
        pass

    return PromptResponse.model_validate(approved_prompt)


@router.post(
    "/{prompt_id}/reject",
    response_model=PromptResponse,
    summary="Reject Prompt",
    description="Reject prompt with optional reason"
)
async def reject_prompt(
    prompt_id: str,
    rejection_reason: Optional[str] = Query(None, max_length=500, description="Reason for rejection"),
    prompt_repo: PromptRepository = Depends(get_prompt_repository)
) -> PromptResponse:
    """Reject a prompt."""
    try:
        prompt_uuid = uuid.UUID(prompt_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid prompt ID format"
        )

    rejected_prompt = await prompt_repo.reject_prompt(
        prompt_uuid,
        rejection_reason=rejection_reason
    )

    if not rejected_prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found"
        )

    return PromptResponse.model_validate(rejected_prompt)


# Bulk operations endpoint
@router.post(
    "/batch",
    response_model=Dict[str, Any],
    summary="Batch Operations",
    description="Perform bulk operations on multiple prompts (approve, reject, delete)"
)
async def batch_operations(
    prompt_ids: List[str] = Query(..., description="List of prompt IDs"),
    operation: str = Query(..., description="Operation to perform: approve, reject, or delete"),
    rejection_reason: Optional[str] = Query(None, max_length=500, description="Rejection reason (for reject/delete)"),
    create_mochi_card: bool = Query(False, description="Auto-create Mochi cards (for approve)"),
    prompt_repo: PromptRepository = Depends(get_prompt_repository)
) -> Dict[str, Any]:
    """Perform bulk operations on prompts."""
    # Validate operation
    valid_operations = ["approve", "reject", "delete"]
    if operation not in valid_operations:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid operation. Must be one of: {', '.join(valid_operations)}"
        )

    # Validate and convert prompt IDs
    prompt_uuids = []
    for prompt_id in prompt_ids:
        try:
            prompt_uuids.append(uuid.UUID(prompt_id))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid prompt ID format: {prompt_id}"
            )

    # Validate batch size
    if len(prompt_uuids) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Batch size cannot exceed 100 prompts"
        )

    if len(prompt_uuids) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one prompt ID is required"
        )

    # Perform bulk operation
    try:
        result = await prompt_repo.bulk_operations(
            prompt_uuids,
            operation,
            rejection_reason=rejection_reason,
            create_mochi_card=create_mochi_card
        )
        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bulk operation failed: {str(e)}"
        )


# Utility endpoints
@router.post(
    "/validate",
    response_model=Dict[str, Any],
    summary="Validate Prompt",
    description="Validate prompt data without creating a record"
)
async def validate_prompt_data(
    prompt_data: PromptCreate,
    prompt_repo: PromptRepository = Depends(get_prompt_repository)
) -> Dict[str, Any]:
    """Validate prompt data."""
    try:
        validation_result = await prompt_repo.validate_prompt(prompt_data)
        return APIResponse.success(
            data=validation_result,
            message="Prompt validation completed"
        )

    except ValueError as e:
        return APIResponse.error(
            message="Prompt validation failed",
            details={"validation_errors": [str(e)]}
        )