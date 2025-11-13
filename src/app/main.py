# Main FastAPI Application
"""
Mochi Donut - Spaced Repetition Learning Integration System

A production-ready FastAPI application for converting content from various sources
into high-quality flashcards following Andy Matuschak's principles. Features
multi-agent AI processing and integrates with Mochi for flashcard review.
"""

import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import uvicorn

from src.app.core.config import settings
from src.app.core.database import db
from src.app.api.v1.router import api_router


# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting Mochi Donut application...")

    try:
        # Initialize database if in development
        if settings.is_development:
            await db.init_db()
            logger.info("Database initialized")

        # Health check
        if await db.health_check():
            logger.info("Database connection verified")
        else:
            logger.error("Database connection failed")

        logger.info("Application startup complete")
        yield

    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise

    finally:
        # Shutdown
        logger.info("Shutting down Mochi Donut application...")
        await db.close()
        logger.info("Application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=__doc__,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    # Security headers
    swagger_ui_parameters={
        "persistAuthorization": True,
        "displayRequestDuration": True,
    }
)


# Security Middleware
if not settings.is_development:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["localhost", "127.0.0.1", "*.fly.dev"]
    )


# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
)


# Custom exception handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions with consistent JSON responses."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "status_code": exc.status_code,
            "timestamp": request.state.__dict__.get("timestamp"),
            "path": str(request.url)
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors with detailed information."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Request validation failed",
            "errors": exc.errors(),
            "status_code": 422,
            "timestamp": request.state.__dict__.get("timestamp"),
            "path": str(request.url)
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(f"Unexpected error: {exc}", exc_info=True)

    # Don't expose internal errors in production
    detail = str(exc) if settings.is_development else "Internal server error"

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": detail,
            "status_code": 500,
            "timestamp": request.state.__dict__.get("timestamp"),
            "path": str(request.url)
        }
    )


# Add timestamp to request state for consistent error responses
@app.middleware("http")
async def add_timestamp_middleware(request: Request, call_next):
    """Add timestamp to request state."""
    import time
    request.state.timestamp = int(time.time())

    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time

    response.headers["X-Process-Time"] = str(process_time)
    return response


# Rate limiting middleware (placeholder for production implementation)
if settings.RATE_LIMIT_ENABLED:
    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        """Basic rate limiting middleware - enhance for production."""
        # TODO: Implement Redis-based rate limiting
        response = await call_next(request)
        return response


# Health check endpoints
@app.get("/health", tags=["Health"])
async def health_check() -> Dict[str, Any]:
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": app.state.__dict__.get("timestamp"),
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT
    }


@app.get("/health/detailed", tags=["Health"])
async def detailed_health_check() -> Dict[str, Any]:
    """Detailed health check including database connectivity."""
    db_healthy = await db.health_check()

    return {
        "status": "healthy" if db_healthy else "unhealthy",
        "timestamp": app.state.__dict__.get("timestamp"),
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "services": {
            "database": "healthy" if db_healthy else "unhealthy",
            "redis": "not_implemented",  # TODO: Add Redis health check
            "chroma": "not_implemented",  # TODO: Add Chroma health check
        }
    }


# API routers
app.include_router(api_router, prefix=settings.API_V1_STR)


# Root endpoint
@app.get("/", tags=["Root"])
async def root() -> Dict[str, Any]:
    """Root endpoint with API information."""
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "description": "Spaced repetition learning integration system",
        "docs_url": "/docs",
        "api_v1": settings.API_V1_STR,
        "health": "/health"
    }


if __name__ == "__main__":
    # Development server
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.is_development,
        log_level=settings.LOG_LEVEL.lower()
    )