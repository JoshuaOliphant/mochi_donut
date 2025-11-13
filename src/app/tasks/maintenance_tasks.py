"""
Maintenance tasks for the Mochi Donut system.

Handles database cleanup, cache management, analytics aggregation,
and system health monitoring.
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import structlog

from app.tasks.celery_app import celery_app, TaskConfig
from app.services.cache import CacheService
from app.repositories.content import ContentRepository
from app.repositories.prompt import PromptRepository
from app.db.session import get_async_session

logger = structlog.get_logger()


class MaintenanceTask:
    """Base class for maintenance tasks with common utilities."""

    def __init__(self):
        self.cache_service = CacheService()
        self.content_repo = ContentRepository()
        self.prompt_repo = PromptRepository()


@celery_app.task(bind=True, base=MaintenanceTask, **TaskConfig.get_retry_config("maintenance"))
def cleanup_old_data(self, retention_days: int = 30) -> Dict[str, Any]:
    """
    Clean up old data based on retention policy.

    Args:
        retention_days: Number of days to retain data

    Returns:
        Dict with cleanup results
    """
    task_logger = TaskConfig.get_task_logger("cleanup_old_data")

    try:
        task_logger.info("Starting data cleanup", retention_days=retention_days, task_id=self.request.id)

        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        cleanup_results = {
            "cutoff_date": cutoff_date.isoformat(),
            "retention_days": retention_days,
            "deleted_content": 0,
            "deleted_prompts": 0,
            "deleted_cache_entries": 0,
            "deleted_temp_files": 0,
        }

        # Clean up old content records
        async def cleanup_content():
            async with get_async_session() as session:
                # Find content older than retention period with no associated prompts
                old_content = await self.content_repo.find_orphaned_before(session, cutoff_date)

                deleted_count = 0
                for content in old_content:
                    # Verify no recent prompts are associated
                    recent_prompts = await self.prompt_repo.find_by_content_id_after(
                        session, content.id, cutoff_date
                    )

                    if not recent_prompts:
                        # Safe to delete - remove from vector store first
                        if content.chroma_id:
                            try:
                                from app.services.vector_store import VectorStoreService
                                vector_service = VectorStoreService()
                                await vector_service.delete_document(content.chroma_id)
                            except Exception as e:
                                task_logger.warning(
                                    "Failed to delete vector document",
                                    content_id=content.id,
                                    chroma_id=content.chroma_id,
                                    error=str(e)
                                )

                        # Delete content record
                        await self.content_repo.delete(session, content.id)
                        deleted_count += 1

                await session.commit()
                return deleted_count

        cleanup_results["deleted_content"] = asyncio.run(cleanup_content())

        # Clean up orphaned prompts (prompts without valid content)
        async def cleanup_orphaned_prompts():
            async with get_async_session() as session:
                orphaned_prompts = await self.prompt_repo.find_orphaned_before(session, cutoff_date)

                deleted_count = 0
                for prompt in orphaned_prompts:
                    await self.prompt_repo.delete(session, prompt.id)
                    deleted_count += 1

                await session.commit()
                return deleted_count

        cleanup_results["deleted_prompts"] = asyncio.run(cleanup_orphaned_prompts())

        # Clean up expired cache entries
        cache_cleanup = asyncio.run(self.cleanup_expired_cache())
        cleanup_results["deleted_cache_entries"] = cache_cleanup.get("deleted_entries", 0)

        # Clean up temporary files (implementation depends on file storage strategy)
        cleanup_results["deleted_temp_files"] = asyncio.run(self.cleanup_temp_files(cutoff_date))

        task_logger.info(
            "Data cleanup completed",
            retention_days=retention_days,
            deleted_content=cleanup_results["deleted_content"],
            deleted_prompts=cleanup_results["deleted_prompts"],
            deleted_cache=cleanup_results["deleted_cache_entries"]
        )

        return {"success": True, **cleanup_results}

    except Exception as e:
        task_logger.error("Data cleanup failed", retention_days=retention_days, error=str(e))
        raise self.retry(countdown=300, max_retries=1, exc=e)


@celery_app.task(bind=True, base=MaintenanceTask, **TaskConfig.get_retry_config("maintenance"))
def invalidate_expired_cache(self, force_cleanup: bool = False) -> Dict[str, Any]:
    """
    Invalidate expired cache entries.

    Args:
        force_cleanup: Force cleanup of all cache entries

    Returns:
        Dict with cache cleanup results
    """
    task_logger = TaskConfig.get_task_logger("invalidate_expired_cache")

    try:
        task_logger.info("Starting cache cleanup", force_cleanup=force_cleanup, task_id=self.request.id)

        cleanup_result = asyncio.run(self.cleanup_expired_cache(force_cleanup))

        task_logger.info(
            "Cache cleanup completed",
            deleted_entries=cleanup_result.get("deleted_entries", 0),
            freed_memory=cleanup_result.get("freed_memory_mb", 0)
        )

        return {"success": True, **cleanup_result}

    except Exception as e:
        task_logger.error("Cache cleanup failed", error=str(e))
        raise self.retry(countdown=300, max_retries=1, exc=e)

    async def cleanup_expired_cache(self, force_cleanup: bool = False) -> Dict[str, Any]:
        """Internal cache cleanup method."""
        try:
            # This implementation depends on Redis cache service capabilities
            # For now, return placeholder results

            deleted_entries = 0
            freed_memory_mb = 0

            # In a real implementation, this would:
            # 1. Scan for expired keys
            # 2. Delete expired entries
            # 3. Calculate memory freed
            # 4. Optionally force cleanup of old entries

            return {
                "deleted_entries": deleted_entries,
                "freed_memory_mb": freed_memory_mb,
                "force_cleanup": force_cleanup,
                "cleanup_timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.warning("Cache cleanup error", error=str(e))
            return {"deleted_entries": 0, "freed_memory_mb": 0, "error": str(e)}

    async def cleanup_temp_files(self, cutoff_date: datetime) -> int:
        """Clean up temporary files older than cutoff date."""
        # Implementation depends on temporary file storage strategy
        # This is a placeholder for actual file cleanup logic
        return 0


@celery_app.task(bind=True, base=MaintenanceTask, **TaskConfig.get_retry_config("maintenance"))
def aggregate_analytics(self, period: str = "daily") -> Dict[str, Any]:
    """
    Aggregate analytics data for reporting.

    Args:
        period: Aggregation period (daily, weekly, monthly)

    Returns:
        Dict with analytics aggregation results
    """
    task_logger = TaskConfig.get_task_logger("aggregate_analytics")

    try:
        task_logger.info("Starting analytics aggregation", period=period, task_id=self.request.id)

        # Calculate date range for aggregation
        now = datetime.utcnow()
        if period == "daily":
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=1)
        elif period == "weekly":
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=now.weekday())
            end_date = start_date + timedelta(days=7)
        elif period == "monthly":
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            next_month = start_date.replace(month=start_date.month + 1) if start_date.month < 12 else start_date.replace(year=start_date.year + 1, month=1)
            end_date = next_month
        else:
            raise ValueError(f"Invalid period: {period}")

        # Aggregate content processing metrics
        content_metrics = asyncio.run(self.aggregate_content_metrics(start_date, end_date))

        # Aggregate prompt generation metrics
        prompt_metrics = asyncio.run(self.aggregate_prompt_metrics(start_date, end_date))

        # Aggregate Mochi sync metrics
        sync_metrics = asyncio.run(self.aggregate_sync_metrics(start_date, end_date))

        # Aggregate AI usage and cost metrics
        ai_metrics = asyncio.run(self.aggregate_ai_metrics(start_date, end_date))

        # Compile aggregated analytics
        analytics_data = {
            "period": period,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "content_processing": content_metrics,
            "prompt_generation": prompt_metrics,
            "mochi_sync": sync_metrics,
            "ai_usage": ai_metrics,
            "aggregated_at": datetime.utcnow().isoformat(),
        }

        # Store aggregated data in cache
        cache_key = f"analytics:{period}:{start_date.strftime('%Y-%m-%d')}"
        await self.cache_service.set(cache_key, json.dumps(analytics_data), ttl=86400 * 7)  # 7 days

        task_logger.info(
            "Analytics aggregation completed",
            period=period,
            content_items=content_metrics.get("total_processed", 0),
            prompts_generated=prompt_metrics.get("total_generated", 0),
            mochi_syncs=sync_metrics.get("total_synced", 0)
        )

        return {"success": True, **analytics_data}

    except Exception as e:
        task_logger.error("Analytics aggregation failed", period=period, error=str(e))
        raise self.retry(countdown=300, max_retries=1, exc=e)

    async def aggregate_content_metrics(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Aggregate content processing metrics."""
        async with get_async_session() as session:
            # This would query content processing stats from the database
            # Implementation depends on actual repository methods and data structure

            return {
                "total_processed": 0,
                "by_source_type": {},
                "processing_times": {"avg": 0, "min": 0, "max": 0},
                "success_rate": 0.0,
                "duplicate_rate": 0.0,
            }

    async def aggregate_prompt_metrics(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Aggregate prompt generation metrics."""
        async with get_async_session() as session:
            # This would query prompt generation stats

            return {
                "total_generated": 0,
                "by_type": {},
                "quality_scores": {"avg": 0, "distribution": {}},
                "refinement_rate": 0.0,
                "approval_rate": 0.0,
            }

    async def aggregate_sync_metrics(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Aggregate Mochi sync metrics."""
        async with get_async_session() as session:
            # This would query sync statistics

            return {
                "total_synced": 0,
                "sync_success_rate": 0.0,
                "sync_errors": 0,
                "by_deck": {},
                "average_sync_time": 0.0,
            }

    async def aggregate_ai_metrics(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Aggregate AI usage and cost metrics."""
        # This would aggregate AI usage from cached tracking data

        return {
            "total_requests": 0,
            "by_model": {},
            "token_usage": {"input": 0, "output": 0},
            "estimated_cost": 0.0,
            "operations": {},
        }


@celery_app.task(bind=True, base=MaintenanceTask, **TaskConfig.get_retry_config("maintenance"))
def health_check(self, check_external: bool = True) -> Dict[str, Any]:
    """
    Perform comprehensive system health check.

    Args:
        check_external: Whether to check external service health

    Returns:
        Dict with health check results
    """
    task_logger = TaskConfig.get_task_logger("health_check")

    try:
        task_logger.info("Starting system health check", check_external=check_external, task_id=self.request.id)

        health_results = {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_status": "healthy",
            "components": {},
            "warnings": [],
            "errors": [],
        }

        # Check database connectivity
        health_results["components"]["database"] = asyncio.run(self.check_database_health())

        # Check cache service
        health_results["components"]["cache"] = asyncio.run(self.check_cache_health())

        # Check Celery workers
        health_results["components"]["celery"] = self.check_celery_health()

        # Check external services if requested
        if check_external:
            health_results["components"]["mochi_api"] = asyncio.run(self.check_mochi_health())
            health_results["components"]["jina_api"] = asyncio.run(self.check_jina_health())

        # Check disk space and memory
        health_results["components"]["system_resources"] = self.check_system_resources()

        # Determine overall health status
        component_statuses = [comp.get("status", "unknown") for comp in health_results["components"].values()]

        if "error" in component_statuses:
            health_results["overall_status"] = "unhealthy"
        elif "warning" in component_statuses:
            health_results["overall_status"] = "degraded"

        # Collect warnings and errors
        for component_name, component_health in health_results["components"].items():
            if component_health.get("status") == "warning" and component_health.get("message"):
                health_results["warnings"].append(f"{component_name}: {component_health['message']}")
            elif component_health.get("status") == "error" and component_health.get("message"):
                health_results["errors"].append(f"{component_name}: {component_health['message']}")

        task_logger.info(
            "System health check completed",
            overall_status=health_results["overall_status"],
            warnings=len(health_results["warnings"]),
            errors=len(health_results["errors"])
        )

        return {"success": True, **health_results}

    except Exception as e:
        task_logger.error("Health check failed", error=str(e))
        return {
            "success": False,
            "overall_status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def check_database_health(self) -> Dict[str, Any]:
        """Check database connectivity and performance."""
        try:
            async with get_async_session() as session:
                # Simple query to test connectivity
                result = await session.execute("SELECT 1")
                result.fetchone()

                return {
                    "status": "healthy",
                    "response_time_ms": 0,  # Would measure actual response time
                    "connection_pool": "available",
                }

        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "response_time_ms": None,
            }

    async def check_cache_health(self) -> Dict[str, Any]:
        """Check cache service health."""
        try:
            # Test cache operations
            test_key = "health_check_test"
            test_value = datetime.utcnow().isoformat()

            await self.cache_service.set(test_key, test_value, ttl=60)
            retrieved_value = await self.cache_service.get(test_key)
            await self.cache_service.delete(test_key)

            if retrieved_value == test_value:
                return {
                    "status": "healthy",
                    "operations": "read/write/delete",
                }
            else:
                return {
                    "status": "warning",
                    "message": "Cache read/write mismatch",
                }

        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
            }

    def check_celery_health(self) -> Dict[str, Any]:
        """Check Celery worker health."""
        try:
            from app.tasks.celery_app import celery_app

            inspector = celery_app.control.inspect()
            stats = inspector.stats()

            if stats:
                active_workers = len(stats)
                return {
                    "status": "healthy",
                    "active_workers": active_workers,
                    "worker_details": stats,
                }
            else:
                return {
                    "status": "warning",
                    "message": "No active workers found",
                    "active_workers": 0,
                }

        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "active_workers": 0,
            }

    async def check_mochi_health(self) -> Dict[str, Any]:
        """Check Mochi API health."""
        try:
            from app.services.mochi_client import MochiClient
            mochi_client = MochiClient()

            # Simple API health check
            health_result = await mochi_client.health_check()

            if health_result.get("success"):
                return {
                    "status": "healthy",
                    "api_version": health_result.get("version"),
                    "response_time_ms": health_result.get("response_time", 0),
                }
            else:
                return {
                    "status": "warning",
                    "message": health_result.get("error", "API check failed"),
                }

        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
            }

    async def check_jina_health(self) -> Dict[str, Any]:
        """Check JinaAI API health."""
        try:
            from app.services.jina_reader import JinaReaderService
            jina_service = JinaReaderService()

            # Simple API health check
            health_result = await jina_service.health_check()

            if health_result.get("success"):
                return {
                    "status": "healthy",
                    "rate_limit_remaining": health_result.get("rate_limit_remaining"),
                    "response_time_ms": health_result.get("response_time", 0),
                }
            else:
                return {
                    "status": "warning",
                    "message": health_result.get("error", "API check failed"),
                }

        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
            }

    def check_system_resources(self) -> Dict[str, Any]:
        """Check system resource availability."""
        try:
            import psutil

            # Check disk space
            disk_usage = psutil.disk_usage('/')
            disk_percent = (disk_usage.used / disk_usage.total) * 100

            # Check memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent

            # Check CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)

            status = "healthy"
            warnings = []

            if disk_percent > 90:
                status = "error"
                warnings.append("Disk usage critical")
            elif disk_percent > 80:
                status = "warning"
                warnings.append("Disk usage high")

            if memory_percent > 90:
                status = "error"
                warnings.append("Memory usage critical")
            elif memory_percent > 80:
                status = "warning"
                warnings.append("Memory usage high")

            if cpu_percent > 90:
                status = "warning"
                warnings.append("CPU usage high")

            return {
                "status": status,
                "disk_usage_percent": round(disk_percent, 2),
                "memory_usage_percent": round(memory_percent, 2),
                "cpu_usage_percent": round(cpu_percent, 2),
                "warnings": warnings,
            }

        except ImportError:
            return {
                "status": "warning",
                "message": "psutil not available - cannot check system resources",
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
            }