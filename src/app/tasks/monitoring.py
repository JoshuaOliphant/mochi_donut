"""
Task monitoring utilities for the Mochi Donut system.

Provides task status tracking, progress reporting, error notifications,
and performance metrics collection.
"""

import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from enum import Enum
import structlog

from celery import states
from celery.result import AsyncResult
from app.tasks.celery_app import celery_app
from app.services.cache import CacheService

logger = structlog.get_logger()


class TaskStatus(str, Enum):
    """Enhanced task status enumeration."""
    PENDING = "PENDING"
    RECEIVED = "RECEIVED"
    STARTED = "STARTED"
    PROGRESS = "PROGRESS"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    REVOKED = "REVOKED"
    RETRY = "RETRY"


class TaskMonitor:
    """Task monitoring and progress tracking service."""

    def __init__(self):
        self.cache_service = CacheService()

    async def track_task_progress(
        self,
        task_id: str,
        current: int,
        total: int,
        status: str = "PROGRESS",
        message: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Track task progress with detailed status information.

        Args:
            task_id: Task identifier
            current: Current progress count
            total: Total items to process
            status: Task status
            message: Status message
            metadata: Additional metadata
        """
        try:
            progress_data = {
                "task_id": task_id,
                "current": current,
                "total": total,
                "percentage": round((current / total) * 100, 2) if total > 0 else 0,
                "status": status,
                "message": message,
                "metadata": metadata or {},
                "updated_at": datetime.utcnow().isoformat(),
            }

            cache_key = f"task:progress:{task_id}"
            await self.cache_service.set(cache_key, json.dumps(progress_data), ttl=3600)

            logger.info(
                "Task progress updated",
                task_id=task_id,
                current=current,
                total=total,
                percentage=progress_data["percentage"],
                status=status
            )

        except Exception as e:
            logger.warning("Failed to track task progress", task_id=task_id, error=str(e))

    async def get_task_progress(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current task progress information.

        Args:
            task_id: Task identifier

        Returns:
            Dict with progress information or None if not found
        """
        try:
            cache_key = f"task:progress:{task_id}"
            progress_data = await self.cache_service.get(cache_key)

            if progress_data:
                return json.loads(progress_data)

            # Fallback to Celery result
            result = AsyncResult(task_id, app=celery_app)
            if result.state != states.PENDING:
                return {
                    "task_id": task_id,
                    "status": result.state,
                    "result": result.result if result.successful() else None,
                    "error": str(result.result) if result.failed() else None,
                    "updated_at": datetime.utcnow().isoformat(),
                }

        except Exception as e:
            logger.warning("Failed to get task progress", task_id=task_id, error=str(e))

        return None

    async def get_batch_progress(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """
        Get progress for a batch operation.

        Args:
            batch_id: Batch identifier

        Returns:
            Dict with batch progress information
        """
        try:
            cache_key = f"batch:progress:{batch_id}"
            batch_data = await self.cache_service.get(cache_key)

            if batch_data:
                return json.loads(batch_data)

        except Exception as e:
            logger.warning("Failed to get batch progress", batch_id=batch_id, error=str(e))

        return None

    async def track_task_metrics(
        self,
        task_name: str,
        execution_time: float,
        status: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Track task performance metrics.

        Args:
            task_name: Name of the task
            execution_time: Task execution time in seconds
            status: Final task status
            metadata: Additional metrics data
        """
        try:
            metrics_data = {
                "task_name": task_name,
                "execution_time": execution_time,
                "status": status,
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": metadata or {},
            }

            # Store individual metric
            metric_key = f"metrics:task:{task_name}:{datetime.utcnow().strftime('%Y-%m-%d')}"
            existing_metrics = await self.cache_service.get(metric_key)

            if existing_metrics:
                metrics_list = json.loads(existing_metrics)
            else:
                metrics_list = []

            metrics_list.append(metrics_data)

            # Keep only last 1000 metrics per task per day
            if len(metrics_list) > 1000:
                metrics_list = metrics_list[-1000:]

            await self.cache_service.set(metric_key, json.dumps(metrics_list), ttl=86400 * 7)  # 7 days

        except Exception as e:
            logger.warning("Failed to track task metrics", task_name=task_name, error=str(e))

    async def get_task_metrics(
        self,
        task_name: str,
        date: Optional[datetime] = None,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get task performance metrics.

        Args:
            task_name: Name of the task
            date: Specific date for metrics (defaults to today)
            hours: Number of hours of metrics to retrieve

        Returns:
            Dict with aggregated metrics
        """
        try:
            if not date:
                date = datetime.utcnow()

            metrics_summary = {
                "task_name": task_name,
                "period_start": (date - timedelta(hours=hours)).isoformat(),
                "period_end": date.isoformat(),
                "total_executions": 0,
                "successful_executions": 0,
                "failed_executions": 0,
                "average_execution_time": 0.0,
                "min_execution_time": None,
                "max_execution_time": None,
                "success_rate": 0.0,
            }

            # Collect metrics from multiple days if needed
            days_to_check = (hours // 24) + 1
            all_metrics = []

            for days_back in range(days_to_check):
                check_date = date - timedelta(days=days_back)
                metric_key = f"metrics:task:{task_name}:{check_date.strftime('%Y-%m-%d')}"
                day_metrics = await self.cache_service.get(metric_key)

                if day_metrics:
                    day_metrics_list = json.loads(day_metrics)

                    # Filter by time range
                    cutoff_time = date - timedelta(hours=hours)
                    filtered_metrics = [
                        m for m in day_metrics_list
                        if datetime.fromisoformat(m["timestamp"]) >= cutoff_time
                    ]
                    all_metrics.extend(filtered_metrics)

            # Calculate aggregated metrics
            if all_metrics:
                metrics_summary["total_executions"] = len(all_metrics)
                metrics_summary["successful_executions"] = sum(
                    1 for m in all_metrics if m["status"] in ["SUCCESS", "success"]
                )
                metrics_summary["failed_executions"] = (
                    metrics_summary["total_executions"] - metrics_summary["successful_executions"]
                )

                execution_times = [m["execution_time"] for m in all_metrics if m["execution_time"]]
                if execution_times:
                    metrics_summary["average_execution_time"] = sum(execution_times) / len(execution_times)
                    metrics_summary["min_execution_time"] = min(execution_times)
                    metrics_summary["max_execution_time"] = max(execution_times)

                metrics_summary["success_rate"] = (
                    metrics_summary["successful_executions"] / metrics_summary["total_executions"]
                ) * 100 if metrics_summary["total_executions"] > 0 else 0

            return metrics_summary

        except Exception as e:
            logger.warning("Failed to get task metrics", task_name=task_name, error=str(e))
            return metrics_summary

    async def get_active_tasks(self, task_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get information about currently active tasks.

        Args:
            task_types: Optional list of task types to filter by

        Returns:
            Dict with active task information
        """
        try:
            inspector = celery_app.control.inspect()

            # Get active tasks from all workers
            active_tasks = inspector.active()
            scheduled_tasks = inspector.scheduled()
            reserved_tasks = inspector.reserved()

            active_summary = {
                "timestamp": datetime.utcnow().isoformat(),
                "total_active": 0,
                "total_scheduled": 0,
                "total_reserved": 0,
                "workers": {},
                "by_task_type": {},
            }

            if active_tasks:
                for worker, tasks in active_tasks.items():
                    worker_info = {
                        "active_count": len(tasks),
                        "tasks": []
                    }

                    for task in tasks:
                        task_name = task.get("name", "unknown")
                        task_info = {
                            "id": task.get("id"),
                            "name": task_name,
                            "args": task.get("args", []),
                            "kwargs": task.get("kwargs", {}),
                            "time_start": task.get("time_start"),
                        }

                        # Filter by task types if specified
                        if not task_types or task_name in task_types:
                            worker_info["tasks"].append(task_info)

                            # Count by task type
                            if task_name not in active_summary["by_task_type"]:
                                active_summary["by_task_type"][task_name] = 0
                            active_summary["by_task_type"][task_name] += 1

                    active_summary["workers"][worker] = worker_info
                    active_summary["total_active"] += worker_info["active_count"]

            # Add scheduled and reserved task counts
            if scheduled_tasks:
                for worker, tasks in scheduled_tasks.items():
                    active_summary["total_scheduled"] += len(tasks)

            if reserved_tasks:
                for worker, tasks in reserved_tasks.items():
                    active_summary["total_reserved"] += len(tasks)

            return active_summary

        except Exception as e:
            logger.warning("Failed to get active tasks", error=str(e))
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "total_active": 0,
                "error": str(e),
            }

    async def get_task_history(
        self,
        task_types: Optional[List[str]] = None,
        limit: int = 100,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Get recent task execution history.

        Args:
            task_types: Optional list of task types to filter by
            limit: Maximum number of tasks to return
            hours: Number of hours of history to retrieve

        Returns:
            List of recent task executions
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            task_history = []

            # This would require more sophisticated storage of task history
            # For now, return a placeholder structure

            return task_history

        except Exception as e:
            logger.warning("Failed to get task history", error=str(e))
            return []

    async def send_error_notification(
        self,
        task_id: str,
        task_name: str,
        error: str,
        retries_remaining: int = 0
    ) -> None:
        """
        Send error notification for failed tasks.

        Args:
            task_id: Task identifier
            task_name: Name of the failed task
            error: Error message
            retries_remaining: Number of retries remaining
        """
        try:
            notification_data = {
                "task_id": task_id,
                "task_name": task_name,
                "error": error,
                "retries_remaining": retries_remaining,
                "timestamp": datetime.utcnow().isoformat(),
                "severity": "error" if retries_remaining == 0 else "warning",
            }

            # Store error for monitoring dashboard
            error_key = f"errors:task:{task_name}:{datetime.utcnow().strftime('%Y-%m-%d')}"
            existing_errors = await self.cache_service.get(error_key)

            if existing_errors:
                errors_list = json.loads(existing_errors)
            else:
                errors_list = []

            errors_list.append(notification_data)

            # Keep only last 100 errors per task per day
            if len(errors_list) > 100:
                errors_list = errors_list[-100:]

            await self.cache_service.set(error_key, json.dumps(errors_list), ttl=86400 * 7)  # 7 days

            logger.error(
                "Task error notification",
                task_id=task_id,
                task_name=task_name,
                error=error,
                retries_remaining=retries_remaining
            )

            # Here you could integrate with external notification services
            # (email, Slack, PagerDuty, etc.)

        except Exception as e:
            logger.error("Failed to send error notification", task_id=task_id, error=str(e))

    async def cleanup_old_monitoring_data(self, retention_days: int = 7) -> Dict[str, Any]:
        """
        Clean up old monitoring data.

        Args:
            retention_days: Number of days to retain monitoring data

        Returns:
            Dict with cleanup results
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            cleanup_results = {
                "retention_days": retention_days,
                "cutoff_date": cutoff_date.isoformat(),
                "deleted_progress_entries": 0,
                "deleted_metric_entries": 0,
                "deleted_error_entries": 0,
            }

            # This would implement actual cleanup logic
            # For now, return placeholder results

            logger.info(
                "Monitoring data cleanup completed",
                retention_days=retention_days,
                **cleanup_results
            )

            return cleanup_results

        except Exception as e:
            logger.error("Failed to cleanup monitoring data", error=str(e))
            return {"error": str(e)}


# Global task monitor instance
task_monitor = TaskMonitor()


# Convenience functions for common monitoring operations
async def track_progress(task_id: str, current: int, total: int, message: str = "") -> None:
    """Track task progress."""
    await task_monitor.track_task_progress(task_id, current, total, message=message)


async def get_progress(task_id: str) -> Optional[Dict[str, Any]]:
    """Get task progress."""
    return await task_monitor.get_task_progress(task_id)


async def track_metrics(task_name: str, execution_time: float, status: str) -> None:
    """Track task metrics."""
    await task_monitor.track_task_metrics(task_name, execution_time, status)


async def notify_error(task_id: str, task_name: str, error: str, retries: int = 0) -> None:
    """Send error notification."""
    await task_monitor.send_error_notification(task_id, task_name, error, retries)