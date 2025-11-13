# Search API Endpoints
"""
FastAPI endpoints for semantic search functionality.
Provides search across content and prompts with vector similarity.
"""

from typing import List, Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_content_repository,
    get_prompt_repository,
    get_pagination_params,
    PaginationParams,
    APIResponse
)
from app.repositories.content import ContentRepository
from app.repositories.prompt import PromptRepository
from app.schemas.content import ContentSearchRequest, ContentSearchResponse, ContentSummary
from app.schemas.prompt import PromptSearchRequest, PromptSearchResponse, PromptSummary


router = APIRouter()


@router.post(
    "/content",
    response_model=ContentSearchResponse,
    summary="Search Content",
    description="Search content using text and semantic similarity"
)
async def search_content(
    search_request: ContentSearchRequest,
    content_repo: ContentRepository = Depends(get_content_repository)
) -> ContentSearchResponse:
    """Search content with text and semantic similarity."""
    try:
        # Perform search
        results, total_count, facets = await content_repo.search(search_request)

        # Convert results to summaries
        content_summaries = [
            ContentSummary.model_validate(content) for content in results
        ]

        return ContentSearchResponse(
            total_count=total_count,
            results=content_summaries,
            facets=facets
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed"
        )


@router.post(
    "/prompts",
    response_model=PromptSearchResponse,
    summary="Search Prompts",
    description="Search prompts using text and semantic similarity"
)
async def search_prompts(
    search_request: PromptSearchRequest,
    prompt_repo: PromptRepository = Depends(get_prompt_repository)
) -> PromptSearchResponse:
    """Search prompts with text and semantic similarity."""
    try:
        # Perform search
        results, total_count, facets = await prompt_repo.search(search_request)

        # Convert results to summaries
        prompt_summaries = [
            PromptSummary.model_validate(prompt) for prompt in results
        ]

        return PromptSearchResponse(
            total_count=total_count,
            results=prompt_summaries,
            facets=facets
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed"
        )


@router.get(
    "/similar/content/{content_id}",
    response_model=List[ContentSummary],
    summary="Find Similar Content",
    description="Find content similar to the specified content"
)
async def find_similar_content(
    content_id: str,
    limit: int = Query(10, ge=1, le=50, description="Number of similar items to return"),
    min_similarity: float = Query(0.5, ge=0.0, le=1.0, description="Minimum similarity score"),
    content_repo: ContentRepository = Depends(get_content_repository)
) -> List[ContentSummary]:
    """Find content similar to the specified content."""
    try:
        import uuid
        content_uuid = uuid.UUID(content_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid content ID format"
        )

    try:
        similar_content = await content_repo.find_similar(
            content_uuid,
            limit=limit,
            min_similarity=min_similarity
        )

        return [ContentSummary.model_validate(content) for content in similar_content]

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to find similar content"
        )


@router.get(
    "/similar/prompts/{prompt_id}",
    response_model=List[PromptSummary],
    summary="Find Similar Prompts",
    description="Find prompts similar to the specified prompt"
)
async def find_similar_prompts(
    prompt_id: str,
    limit: int = Query(10, ge=1, le=50, description="Number of similar items to return"),
    min_similarity: float = Query(0.5, ge=0.0, le=1.0, description="Minimum similarity score"),
    prompt_repo: PromptRepository = Depends(get_prompt_repository)
) -> List[PromptSummary]:
    """Find prompts similar to the specified prompt."""
    try:
        import uuid
        prompt_uuid = uuid.UUID(prompt_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid prompt ID format"
        )

    try:
        similar_prompts = await prompt_repo.find_similar(
            prompt_uuid,
            limit=limit,
            min_similarity=min_similarity
        )

        return [PromptSummary.model_validate(prompt) for prompt in similar_prompts]

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to find similar prompts"
        )


@router.get(
    "/suggestions",
    response_model=Dict[str, Any],
    summary="Get Search Suggestions",
    description="Get search suggestions based on query"
)
async def get_search_suggestions(
    query: str = Query(..., min_length=2, max_length=100, description="Search query"),
    limit: int = Query(10, ge=1, le=20, description="Number of suggestions"),
    content_repo: ContentRepository = Depends(get_content_repository),
    prompt_repo: PromptRepository = Depends(get_prompt_repository)
) -> Dict[str, Any]:
    """Get search suggestions for auto-completion."""
    try:
        # Get suggestions from both content and prompts
        content_suggestions = await content_repo.get_search_suggestions(query, limit // 2)
        prompt_suggestions = await prompt_repo.get_search_suggestions(query, limit // 2)

        return APIResponse.success(
            data={
                "query": query,
                "content_suggestions": content_suggestions,
                "prompt_suggestions": prompt_suggestions,
                "total_suggestions": len(content_suggestions) + len(prompt_suggestions)
            },
            message="Search suggestions retrieved"
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get search suggestions"
        )


@router.get(
    "/trending",
    response_model=Dict[str, Any],
    summary="Get Trending Searches",
    description="Get trending search terms and popular content"
)
async def get_trending_searches(
    limit: int = Query(10, ge=1, le=50, description="Number of trending items"),
    time_window: str = Query("7d", regex="^(1d|7d|30d)$", description="Time window for trending data"),
    content_repo: ContentRepository = Depends(get_content_repository),
    prompt_repo: PromptRepository = Depends(get_prompt_repository)
) -> Dict[str, Any]:
    """Get trending searches and popular content."""
    try:
        # Convert time window to days
        days_map = {"1d": 1, "7d": 7, "30d": 30}
        days = days_map[time_window]

        # Get trending data
        trending_content = await content_repo.get_trending(limit // 2, days)
        trending_prompts = await prompt_repo.get_trending(limit // 2, days)

        return APIResponse.success(
            data={
                "time_window": time_window,
                "trending_content": trending_content,
                "trending_prompts": trending_prompts,
                "generated_at": "now"  # TODO: Add actual timestamp
            },
            message="Trending data retrieved"
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get trending data"
        )


# Advanced search endpoints
@router.post(
    "/advanced",
    response_model=Dict[str, Any],
    summary="Advanced Search",
    description="Perform advanced search across all content types"
)
async def advanced_search(
    query: str = Query(..., min_length=1, max_length=500, description="Search query"),
    include_content: bool = Query(True, description="Include content in results"),
    include_prompts: bool = Query(True, description="Include prompts in results"),
    pagination: PaginationParams = Depends(get_pagination_params),
    content_repo: ContentRepository = Depends(get_content_repository),
    prompt_repo: PromptRepository = Depends(get_prompt_repository)
) -> Dict[str, Any]:
    """Perform advanced search across all content types."""
    try:
        results = {}
        total_results = 0

        if include_content:
            content_search = ContentSearchRequest(
                query=query,
                limit=pagination.limit // 2,
                offset=pagination.skip
            )
            content_results, content_count, content_facets = await content_repo.search(content_search)
            results["content"] = {
                "total_count": content_count,
                "results": [ContentSummary.model_validate(c) for c in content_results],
                "facets": content_facets
            }
            total_results += content_count

        if include_prompts:
            prompt_search = PromptSearchRequest(
                query=query,
                limit=pagination.limit // 2,
                offset=pagination.skip
            )
            prompt_results, prompt_count, prompt_facets = await prompt_repo.search(prompt_search)
            results["prompts"] = {
                "total_count": prompt_count,
                "results": [PromptSummary.model_validate(p) for p in prompt_results],
                "facets": prompt_facets
            }
            total_results += prompt_count

        return APIResponse.success(
            data={
                "query": query,
                "total_results": total_results,
                "results": results
            },
            message="Advanced search completed"
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Advanced search failed"
        )