"""
Monitoring and health check endpoints for Mochi Donut.

Provides comprehensive health checks, metrics, and monitoring endpoints
for production deployment with Prometheus integration and Logfire support.
"""

import asyncio
import json
import time
import psutil
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from src.app.core.config import settings
from src.app.core.database import db
from src.app.integrations.redis_client import redis_client
from src.app.integrations.chroma_client import chroma_client


router = APIRouter(tags=["Monitoring"])


class HealthStatus(BaseModel):
    """Health check response model."""
    status: str
    timestamp: datetime
    version: str
    environment: str
    uptime_seconds: float
    services: Dict[str, str]


class MetricsResponse(BaseModel):
    """Metrics response model."""
    timestamp: datetime
    system: Dict[str, Any]
    application: Dict[str, Any]
    database: Dict[str, Any]
    redis: Dict[str, Any]
    chroma: Dict[str, Any]


# Track application start time for uptime calculation
app_start_time = time.time()


async def check_database_health() -> Dict[str, Any]:
    """Check database connectivity and basic metrics."""
    try:
        # Basic connectivity test
        is_healthy = await db.health_check()

        if not is_healthy:
            return {"status": "unhealthy", "error": "Connection failed"}

        # Get database statistics
        stats = {
            "status": "healthy",
            "connection_pool_size": getattr(db.engine.pool, "size", "unknown"),
            "checked_in_connections": getattr(db.engine.pool, "checkedin", "unknown"),
            "checked_out_connections": getattr(db.engine.pool, "checkedout", "unknown"),
        }

        # Try to get table counts (if tables exist)
        try:
            async with db.get_session() as session:
                # This will be updated when actual models are implemented
                result = await session.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = result.fetchall()
                stats["table_count"] = len(tables)
        except Exception as e:
            stats["table_count"] = f"Error: {str(e)}"

        return stats

    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


async def check_redis_health() -> Dict[str, Any]:
    """Check Redis connectivity and metrics."""
    try:
        # Basic ping test
        await redis_client.ping()

        # Get Redis info
        info = await redis_client.info()

        return {
            "status": "healthy",
            "version": info.get("redis_version", "unknown"),
            "memory_used": info.get("used_memory_human", "unknown"),
            "connected_clients": info.get("connected_clients", "unknown"),
            "total_commands_processed": info.get("total_commands_processed", "unknown"),
            "keyspace_hits": info.get("keyspace_hits", "unknown"),
            "keyspace_misses": info.get("keyspace_misses", "unknown"),
        }

    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


async def check_chroma_health() -> Dict[str, Any]:
    """Check Chroma vector database connectivity."""
    try:
        # Basic connectivity test
        heartbeat = await chroma_client.heartbeat()

        if not heartbeat:
            return {"status": "unhealthy", "error": "Heartbeat failed"}

        # Get collection information
        collections = await chroma_client.list_collections()

        return {
            "status": "healthy",
            "collections_count": len(collections),
            "collections": [col.name for col in collections] if collections else [],
        }

    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


def get_system_metrics() -> Dict[str, Any]:
    """Get system-level metrics."""
    try:
        return {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "memory_available_mb": psutil.virtual_memory().available // 1024 // 1024,
            "disk_usage_percent": psutil.disk_usage("/").percent,
            "load_average": psutil.getloadavg() if hasattr(psutil, "getloadavg") else "not_available",
            "process_count": len(psutil.pids()),
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/health", response_model=HealthStatus)
async def basic_health_check():
    """
    Basic health check endpoint.

    Returns application status and basic information.
    Used by load balancers and Fly.io health checks.
    """
    uptime = time.time() - app_start_time

    return HealthStatus(
        status="healthy",
        timestamp=datetime.now(timezone.utc),
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        uptime_seconds=uptime,
        services={"api": "healthy"}
    )


@router.get("/health/detailed", response_model=HealthStatus)
async def detailed_health_check():
    """
    Detailed health check including all dependencies.

    Checks database, Redis, and Chroma connectivity.
    May take longer to respond due to dependency checks.
    """
    uptime = time.time() - app_start_time

    # Check all services in parallel
    db_task = asyncio.create_task(check_database_health())
    redis_task = asyncio.create_task(check_redis_health())
    chroma_task = asyncio.create_task(check_chroma_health())

    # Wait for all checks with timeout
    try:
        db_status, redis_status, chroma_status = await asyncio.wait_for(
            asyncio.gather(db_task, redis_task, chroma_task),
            timeout=10.0
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Health check timed out"
        )

    services = {
        "api": "healthy",
        "database": db_status.get("status", "unknown"),
        "redis": redis_status.get("status", "unknown"),
        "chroma": chroma_status.get("status", "unknown"),
    }

    # Determine overall status
    overall_status = "healthy" if all(
        status == "healthy" for status in services.values()
    ) else "degraded"

    return HealthStatus(
        status=overall_status,
        timestamp=datetime.now(timezone.utc),
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        uptime_seconds=uptime,
        services=services
    )


@router.get("/health/live")
async def liveness_probe():
    """
    Kubernetes-style liveness probe.

    Returns 200 if the application is running.
    Used to determine if the container should be restarted.
    """
    return {"status": "alive", "timestamp": datetime.now(timezone.utc)}


@router.get("/health/ready")
async def readiness_probe():
    """
    Kubernetes-style readiness probe.

    Returns 200 if the application is ready to serve traffic.
    Checks critical dependencies.
    """
    # Check critical services
    try:
        db_healthy = await db.health_check()
        if not db_healthy:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not ready"
            )

        return {"status": "ready", "timestamp": datetime.now(timezone.utc)}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Not ready: {str(e)}"
        )


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics():
    """
    Application metrics endpoint.

    Returns detailed metrics for monitoring and alerting.
    Compatible with Prometheus scraping.
    """
    timestamp = datetime.now(timezone.utc)

    # Gather metrics from all services
    system_metrics = get_system_metrics()

    # Application metrics
    app_metrics = {
        "uptime_seconds": time.time() - app_start_time,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "python_version": f"{psutil.PYTHON_VERSION_INFO.major}.{psutil.PYTHON_VERSION_INFO.minor}.{psutil.PYTHON_VERSION_INFO.micro}",
    }

    # Service metrics
    db_metrics = await check_database_health()
    redis_metrics = await check_redis_health()
    chroma_metrics = await check_chroma_health()

    return MetricsResponse(
        timestamp=timestamp,
        system=system_metrics,
        application=app_metrics,
        database=db_metrics,
        redis=redis_metrics,
        chroma=chroma_metrics
    )


@router.get("/metrics/prometheus", response_class=PlainTextResponse)
async def prometheus_metrics():
    """
    Prometheus-formatted metrics endpoint.

    Returns metrics in Prometheus exposition format.
    """
    metrics = await get_metrics()

    # Convert to Prometheus format
    prometheus_output = []

    # System metrics
    if "cpu_percent" in metrics.system:
        prometheus_output.append(f"mochi_donut_cpu_percent {metrics.system['cpu_percent']}")

    if "memory_percent" in metrics.system:
        prometheus_output.append(f"mochi_donut_memory_percent {metrics.system['memory_percent']}")

    # Application metrics
    prometheus_output.append(f"mochi_donut_uptime_seconds {metrics.application['uptime_seconds']}")

    # Database metrics
    if metrics.database.get("status") == "healthy":
        prometheus_output.append("mochi_donut_database_healthy 1")
    else:
        prometheus_output.append("mochi_donut_database_healthy 0")

    # Redis metrics
    if metrics.redis.get("status") == "healthy":
        prometheus_output.append("mochi_donut_redis_healthy 1")
        if "connected_clients" in metrics.redis:
            try:
                clients = int(metrics.redis["connected_clients"])
                prometheus_output.append(f"mochi_donut_redis_connected_clients {clients}")
            except (ValueError, TypeError):
                pass
    else:
        prometheus_output.append("mochi_donut_redis_healthy 0")

    # Chroma metrics
    if metrics.chroma.get("status") == "healthy":
        prometheus_output.append("mochi_donut_chroma_healthy 1")
        if "collections_count" in metrics.chroma:
            prometheus_output.append(f"mochi_donut_chroma_collections {metrics.chroma['collections_count']}")
    else:
        prometheus_output.append("mochi_donut_chroma_healthy 0")

    return "\n".join(prometheus_output) + "\n"


@router.get("/status")
async def application_status():
    """
    Application status endpoint.

    Returns current application status and configuration.
    """
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "api_version": settings.API_V1_STR,
        "uptime_seconds": time.time() - app_start_time,
        "configuration": {
            "ai_caching_enabled": settings.AI_CACHING_ENABLED,
            "default_ai_model": settings.DEFAULT_AI_MODEL,
            "quality_review_model": settings.QUALITY_REVIEW_MODEL,
            "rate_limit_enabled": settings.RATE_LIMIT_ENABLED,
            "cors_origins_count": len(settings.CORS_ORIGINS),
        },
        "timestamp": datetime.now(timezone.utc),
    }


@router.post("/health/simulate-failure")
async def simulate_failure():
    """
    Simulate application failure for testing.

    Only available in development environment.
    """
    if not settings.is_development:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Failure simulation only available in development"
        )

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Simulated failure for testing"
    )