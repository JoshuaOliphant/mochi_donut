# API v1 Router
"""
Main router for API v1 endpoints. Includes all endpoint routers
and configures common middleware and dependencies.
"""

from fastapi import APIRouter

from src.app.api.v1.endpoints import content, prompts, search, analytics, monitoring, process

# Create main API router
api_router = APIRouter()

# Include endpoint routers with proper tags and prefixes
api_router.include_router(
    content.router,
    prefix="/content",
    tags=["content"],
)

api_router.include_router(
    prompts.router,
    prefix="/prompts",
    tags=["prompts"],
)

api_router.include_router(
    search.router,
    prefix="/search",
    tags=["search"],
)

api_router.include_router(
    analytics.router,
    prefix="/analytics",
    tags=["analytics"],
)

api_router.include_router(
    monitoring.router,
    prefix="",  # No prefix for monitoring endpoints (they're at root level)
    tags=["monitoring"],
)

api_router.include_router(
    process.router,
    # Note: process.router already has prefix="/process" defined in the router itself
    tags=["processing"],
)