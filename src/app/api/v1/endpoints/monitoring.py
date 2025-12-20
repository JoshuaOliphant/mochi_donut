# ABOUTME: Monitoring and health check endpoints for Mochi Donut
# ABOUTME: Provides health checks, metrics, and monitoring for production deployment

import asyncio
import time
import psutil
from datetime import datetime, timezone
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from app.core.config import settings
from app.core.database import db
from app.integrations.chroma_client import chroma_client
from app.background.scheduler import get_scheduler, get_jobs
from app.background.progress import get_progress_tracker


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
    scheduler: Dict[str, Any]
    chroma: Dict[str, Any]


# Track application start time for uptime calculation
app_start_time = time.time()


async def check_database_health() -> Dict[str, Any]:
    """Check database connectivity and basic metrics."""
    try:
        is_healthy = await db.health_check()

        if not is_healthy:
            return {"status": "unhealthy", "error": "Connection failed"}

        stats = {
            "status": "healthy",
            "connection_pool_size": getattr(db.engine.pool, "size", "unknown"),
            "checked_in_connections": getattr(db.engine.pool, "checkedin", "unknown"),
            "checked_out_connections": getattr(db.engine.pool, "checkedout", "unknown"),
        }

        try:
            async with db.get_session() as session:
                result = await session.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = result.fetchall()
                stats["table_count"] = len(tables)
        except Exception as e:
            stats["table_count"] = f"Error: {str(e)}"

        return stats

    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


def check_scheduler_health() -> Dict[str, Any]:
    """Check APScheduler status and jobs."""
    try:
        scheduler = get_scheduler()
        if scheduler is None:
            return {"status": "not_initialized"}

        jobs = get_jobs()
        running = scheduler.running if scheduler else False

        return {
            "status": "healthy" if running else "stopped",
            "running": running,
            "scheduled_jobs": len(jobs),
            "jobs": [{"id": j["id"], "next_run": j["next_run_time"]} for j in jobs],
        }

    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


def check_progress_tracker() -> Dict[str, Any]:
    """Check in-memory progress tracker status."""
    try:
        tracker = get_progress_tracker()
        active_tasks = tracker.list_active()

        return {
            "status": "healthy",
            "active_tasks": len(active_tasks),
        }

    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


async def check_chroma_health() -> Dict[str, Any]:
    """Check Chroma vector database connectivity."""
    try:
        heartbeat = await chroma_client.heartbeat()

        if not heartbeat:
            return {"status": "unhealthy", "error": "Heartbeat failed"}

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
    """Basic health check endpoint."""
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
    """Detailed health check including all dependencies."""
    uptime = time.time() - app_start_time

    # Check services
    db_task = asyncio.create_task(check_database_health())
    chroma_task = asyncio.create_task(check_chroma_health())

    try:
        db_status, chroma_status = await asyncio.wait_for(
            asyncio.gather(db_task, chroma_task),
            timeout=10.0
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Health check timed out"
        )

    scheduler_status = check_scheduler_health()
    progress_status = check_progress_tracker()

    services = {
        "api": "healthy",
        "database": db_status.get("status", "unknown"),
        "scheduler": scheduler_status.get("status", "unknown"),
        "progress_tracker": progress_status.get("status", "unknown"),
        "chroma": chroma_status.get("status", "unknown"),
    }

    overall_status = "healthy" if all(
        s == "healthy" for s in services.values()
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
    """Kubernetes-style liveness probe."""
    return {"status": "alive", "timestamp": datetime.now(timezone.utc)}


@router.get("/health/ready")
async def readiness_probe():
    """Kubernetes-style readiness probe."""
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
    """Application metrics endpoint."""
    timestamp = datetime.now(timezone.utc)

    system_metrics = get_system_metrics()

    app_metrics = {
        "uptime_seconds": time.time() - app_start_time,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
    }

    db_metrics = await check_database_health()
    scheduler_metrics = check_scheduler_health()
    chroma_metrics = await check_chroma_health()

    return MetricsResponse(
        timestamp=timestamp,
        system=system_metrics,
        application=app_metrics,
        database=db_metrics,
        scheduler=scheduler_metrics,
        chroma=chroma_metrics
    )


@router.get("/metrics/prometheus", response_class=PlainTextResponse)
async def prometheus_metrics():
    """Prometheus-formatted metrics endpoint."""
    metrics = await get_metrics()

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

    # Scheduler metrics
    if metrics.scheduler.get("status") == "healthy":
        prometheus_output.append("mochi_donut_scheduler_healthy 1")
        prometheus_output.append(f"mochi_donut_scheduled_jobs {metrics.scheduler.get('scheduled_jobs', 0)}")
    else:
        prometheus_output.append("mochi_donut_scheduler_healthy 0")

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
    """Application status endpoint."""
    scheduler_info = check_scheduler_health()

    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "api_version": settings.API_V1_STR,
        "uptime_seconds": time.time() - app_start_time,
        "scheduler": {
            "running": scheduler_info.get("running", False),
            "scheduled_jobs": scheduler_info.get("scheduled_jobs", 0),
        },
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
    """Simulate application failure for testing."""
    if not settings.is_development:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Failure simulation only available in development"
        )

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Simulated failure for testing"
    )
