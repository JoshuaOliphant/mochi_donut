# Content API Endpoints
"""
FastAPI endpoints for content processing and management.
Handles content creation, retrieval, processing, and batch operations.
"""

import uuid
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_content_repository,
    get_content_processor_service,
    get_pagination_params,
    PaginationParams,
    APIResponse,
    validate_content_exists
)
from app.repositories.content import ContentRepository
from app.services.content_processor import ContentProcessorService
from app.schemas.content import (
    ContentCreate,
    ContentUpdate,
    ContentResponse,
    ContentSummary,
    ContentWithPrompts,
    ContentProcessingRequest,
    ContentProcessingResponse,
    ContentBatchProcessingRequest,
    ContentBatchProcessingResponse,
    ContentSearchRequest,
    ContentSearchResponse,
    ContentStatistics
)
from app.db.models import SourceType, ProcessingStatus


router = APIRouter()


@router.post(
    "/",
    response_model=ContentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Content",
    description="Create new content record from source data"
)
async def create_content(
    content_data: ContentCreate,
    content_repo: ContentRepository = Depends(get_content_repository)
) -> ContentResponse:
    """Create a new content record."""
    try:
        # Create content with hash generation
        content = await content_repo.create_with_hash(content_data)
        return ContentResponse.model_validate(content)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create content"
        )


@router.get(
    "/",
    response_model=List[ContentSummary],
    summary="List Content",
    description="Get paginated list of content with optional filtering"
)
async def list_content(
    pagination: PaginationParams = Depends(get_pagination_params),
    source_type: Optional[SourceType] = Query(None, description="Filter by source type"),
    processing_status: Optional[ProcessingStatus] = Query(None, description="Filter by processing status"),
    content_repo: ContentRepository = Depends(get_content_repository)
) -> List[ContentSummary]:
    """Get paginated list of content records."""
    filters = {}
    if source_type:
        filters["source_type"] = source_type
    if processing_status:
        filters["processing_status"] = processing_status

    content_list = await content_repo.get_multi(
        skip=pagination.skip,
        limit=pagination.limit,
        order_by="-created_at",
        **filters
    )

    return [ContentSummary.model_validate(content) for content in content_list]


@router.get(
    "/{content_id}",
    response_model=ContentResponse,
    summary="Get Content",
    description="Get content by ID with optional prompt count"
)
async def get_content(
    content_id: str,
    include_prompts: bool = Query(False, description="Include associated prompts"),
    content_repo: ContentRepository = Depends(get_content_repository)
) -> ContentResponse:
    """Get content by ID."""
    try:
        content_uuid = uuid.UUID(content_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid content ID format"
        )

    if include_prompts:
        content = await content_repo.get_with_prompts(content_uuid)
        if not content:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Content not found"
            )
        return ContentWithPrompts.model_validate(content)
    else:
        content = await content_repo.get_with_stats(content_uuid)
        if not content:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Content not found"
            )
        return ContentResponse.model_validate(content)


@router.put(
    "/{content_id}",
    response_model=ContentResponse,
    summary="Update Content",
    description="Update content record by ID"
)
async def update_content(
    content_id: str,
    content_data: ContentUpdate,
    content_repo: ContentRepository = Depends(get_content_repository)
) -> ContentResponse:
    """Update content by ID."""
    try:
        content_uuid = uuid.UUID(content_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid content ID format"
        )

    updated_content = await content_repo.update(content_uuid, content_data)
    if not updated_content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found"
        )

    return ContentResponse.model_validate(updated_content)


@router.delete(
    "/{content_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Content",
    description="Delete content and all associated prompts"
)
async def delete_content(
    content_id: str,
    content_repo: ContentRepository = Depends(get_content_repository)
):
    """Delete content by ID."""
    try:
        content_uuid = uuid.UUID(content_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid content ID format"
        )

    deleted = await content_repo.delete(content_uuid)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found"
        )


# Processing endpoints
@router.post(
    "/process",
    response_model=ContentProcessingResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Process Content",
    description="Submit content for AI processing and prompt generation"
)
async def process_content(
    processing_request: ContentProcessingRequest,
    background_tasks: BackgroundTasks,
    processor_service: ContentProcessorService = Depends(get_content_processor_service)
) -> ContentProcessingResponse:
    """Submit content for background processing."""
    try:
        # Create processing task
        result = await processor_service.submit_for_processing(
            processing_request,
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
            detail="Failed to submit content for processing"
        )


@router.post(
    "/process/batch",
    response_model=ContentBatchProcessingResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Batch Process Content",
    description="Submit multiple content items for batch processing"
)
async def batch_process_content(
    batch_request: ContentBatchProcessingRequest,
    background_tasks: BackgroundTasks,
    processor_service: ContentProcessorService = Depends(get_content_processor_service)
) -> ContentBatchProcessingResponse:
    """Submit multiple content items for batch processing."""
    try:
        result = await processor_service.submit_batch_for_processing(
            batch_request,
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
            detail="Failed to submit batch for processing"
        )


@router.get(
    "/{content_id}/processing-status",
    response_model=Dict[str, Any],
    summary="Get Processing Status",
    description="Get detailed processing status for content"
)
async def get_processing_status(
    content_id: str,
    content_repo: ContentRepository = Depends(get_content_repository)
) -> Dict[str, Any]:
    """Get processing status and details for content."""
    try:
        content_uuid = uuid.UUID(content_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid content ID format"
        )

    status_info = await content_repo.get_processing_status(content_uuid)
    if not status_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found"
        )

    return APIResponse.success(
        data=status_info,
        message="Processing status retrieved"
    )


# Analytics and statistics
@router.get(
    "/statistics",
    response_model=ContentStatistics,
    summary="Get Content Statistics",
    description="Get overall content statistics and metrics"
)
async def get_content_statistics(
    content_repo: ContentRepository = Depends(get_content_repository)
) -> ContentStatistics:
    """Get content statistics and metrics."""
    stats = await content_repo.get_statistics()
    return ContentStatistics.model_validate(stats)


@router.get(
    "/{content_id}/duplicates",
    response_model=List[ContentSummary],
    summary="Find Duplicate Content",
    description="Find potential duplicate content based on content hash"
)
async def find_duplicate_content(
    content_id: str,
    content_repo: ContentRepository = Depends(get_content_repository)
) -> List[ContentSummary]:
    """Find potential duplicate content."""
    try:
        content_uuid = uuid.UUID(content_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid content ID format"
        )

    duplicates = await content_repo.find_duplicates(content_uuid)
    return [ContentSummary.model_validate(content) for content in duplicates]


# Utility endpoints
@router.post(
    "/validate",
    response_model=Dict[str, Any],
    summary="Validate Content",
    description="Validate content data without creating a record"
)
async def validate_content_data(
    content_data: ContentCreate,
    content_repo: ContentRepository = Depends(get_content_repository)
) -> Dict[str, Any]:
    """Validate content data without creating a record."""
    try:
        validation_result = await content_repo.validate_content(content_data)
        return APIResponse.success(
            data=validation_result,
            message="Content validation completed"
        )

    except ValueError as e:
        return APIResponse.error(
            message="Content validation failed",
            details={"validation_errors": [str(e)]}
        )