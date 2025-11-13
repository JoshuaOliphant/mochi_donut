# API Dependencies
"""
Common dependencies for API endpoints including database sessions,
repository instances, and common validation logic.
"""

from typing import AsyncGenerator, Optional
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories.content import ContentRepository
from app.repositories.prompt import PromptRepository
from app.services.content_processor import ContentProcessorService
from app.services.prompt_generator import PromptGeneratorService


# Database session dependency
async def get_database_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session for dependency injection."""
    async for session in get_db():
        yield session


# Repository dependencies
async def get_content_repository(
    db: AsyncSession = Depends(get_database_session)
) -> ContentRepository:
    """Get content repository instance."""
    return ContentRepository(db)


async def get_prompt_repository(
    db: AsyncSession = Depends(get_database_session)
) -> PromptRepository:
    """Get prompt repository instance."""
    return PromptRepository(db)


# Service dependencies
async def get_content_processor_service(
    content_repo: ContentRepository = Depends(get_content_repository),
    prompt_repo: PromptRepository = Depends(get_prompt_repository),
) -> ContentProcessorService:
    """Get content processor service instance."""
    return ContentProcessorService(content_repo, prompt_repo)


async def get_prompt_generator_service(
    content_repo: ContentRepository = Depends(get_content_repository),
    prompt_repo: PromptRepository = Depends(get_prompt_repository),
) -> PromptGeneratorService:
    """Get prompt generator service instance."""
    return PromptGeneratorService(content_repo, prompt_repo)


# Common validation dependencies
async def validate_content_exists(
    content_id: str,
    content_repo: ContentRepository = Depends(get_content_repository)
):
    """Validate that content exists by ID."""
    try:
        import uuid
        content_uuid = uuid.UUID(content_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid content ID format"
        )

    content = await content_repo.get(content_uuid)
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found"
        )
    return content


async def validate_prompt_exists(
    prompt_id: str,
    prompt_repo: PromptRepository = Depends(get_prompt_repository)
):
    """Validate that prompt exists by ID."""
    try:
        import uuid
        prompt_uuid = uuid.UUID(prompt_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid prompt ID format"
        )

    prompt = await prompt_repo.get(prompt_uuid)
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found"
        )
    return prompt


# Pagination dependency
class PaginationParams:
    """Pagination parameters for list endpoints."""

    def __init__(
        self,
        skip: int = 0,
        limit: int = 50,
        max_limit: int = 1000
    ):
        if skip < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Skip must be non-negative"
            )

        if limit <= 0 or limit > max_limit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Limit must be between 1 and {max_limit}"
            )

        self.skip = skip
        self.limit = limit


def get_pagination_params(
    skip: int = 0,
    limit: int = 50
) -> PaginationParams:
    """Get pagination parameters with validation."""
    return PaginationParams(skip=skip, limit=limit)


# Common response wrapper
class APIResponse:
    """Standard API response wrapper."""

    @staticmethod
    def success(data=None, message: str = "Success", meta: Optional[dict] = None):
        """Create successful response."""
        response = {
            "success": True,
            "message": message,
            "data": data
        }
        if meta:
            response["meta"] = meta
        return response

    @staticmethod
    def error(message: str, details: Optional[dict] = None):
        """Create error response."""
        response = {
            "success": False,
            "message": message,
        }
        if details:
            response["details"] = details
        return response