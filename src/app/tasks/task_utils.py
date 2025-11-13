"""
Task utilities and helper functions for the Mochi Donut system.

Provides common utilities, decorators, and helper functions used across
all task modules.
"""

import asyncio
import functools
import time
from datetime import datetime
from typing import Any, Callable, Dict, Optional, TypeVar, Union
from celery import Task
from celery.exceptions import Retry
import structlog

from app.tasks.monitoring import task_monitor

logger = structlog.get_logger()

T = TypeVar('T')


def with_task_monitoring(func: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator to add automatic task monitoring and metrics collection.

    Usage:
        @celery_app.task(bind=True)
        @with_task_monitoring
        def my_task(self, ...):
            ...
    """
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        task_id = self.request.id
        task_name = self.name
        start_time = time.time()

        try:
            # Track task start
            asyncio.run(task_monitor.track_task_progress(
                task_id=task_id,
                current=0,
                total=1,
                status="STARTED",
                message=f"Starting {task_name}"
            ))

            # Execute the task
            result = func(self, *args, **kwargs)

            # Calculate execution time
            execution_time = time.time() - start_time

            # Track successful completion
            asyncio.run(task_monitor.track_task_progress(
                task_id=task_id,
                current=1,
                total=1,
                status="SUCCESS",
                message="Task completed successfully"
            ))

            # Track metrics
            asyncio.run(task_monitor.track_task_metrics(
                task_name=task_name,
                execution_time=execution_time,
                status="SUCCESS"
            ))

            return result

        except Exception as e:
            execution_time = time.time() - start_time

            # Track failure
            asyncio.run(task_monitor.track_task_progress(
                task_id=task_id,
                current=0,
                total=1,
                status="FAILURE",
                message=f"Task failed: {str(e)}"
            ))

            # Track error metrics
            asyncio.run(task_monitor.track_task_metrics(
                task_name=task_name,
                execution_time=execution_time,
                status="FAILURE",
                metadata={"error": str(e)}
            ))

            # Send error notification
            retries_remaining = getattr(self, 'max_retries', 0) - getattr(self.request, 'retries', 0)
            asyncio.run(task_monitor.send_error_notification(
                task_id=task_id,
                task_name=task_name,
                error=str(e),
                retries_remaining=retries_remaining
            ))

            raise

    return wrapper


def with_progress_tracking(total_items_key: str = "total", current_key: str = "current"):
    """
    Decorator to automatically track progress for tasks that process multiple items.

    Args:
        total_items_key: Key in kwargs that contains total item count
        current_key: Key to use for tracking current progress

    Usage:
        @celery_app.task(bind=True)
        @with_progress_tracking(total_items_key="url_count")
        def process_urls(self, urls, **kwargs):
            for i, url in enumerate(urls):
                # Process url
                self.update_progress(current=i+1)  # Auto-injected method
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            task_id = self.request.id

            # Extract total from kwargs or count items
            total = kwargs.get(total_items_key)
            if total is None and args:
                # Try to infer total from first argument if it's a list
                first_arg = args[0]
                if isinstance(first_arg, (list, tuple)):
                    total = len(first_arg)

            if total is None:
                total = 1  # Default fallback

            # Inject progress tracking method
            def update_progress(current: int, message: str = "", metadata: Optional[Dict] = None):
                asyncio.run(task_monitor.track_task_progress(
                    task_id=task_id,
                    current=current,
                    total=total,
                    status="PROGRESS",
                    message=message,
                    metadata=metadata
                ))

            # Add method to task instance
            self.update_progress = update_progress

            # Initial progress
            update_progress(0, f"Starting {self.name}")

            return func(self, *args, **kwargs)

        return wrapper
    return decorator


class TaskTimer:
    """Context manager for timing operations within tasks."""

    def __init__(self, task_id: str, operation_name: str):
        self.task_id = task_id
        self.operation_name = operation_name
        self.start_time = None
        self.end_time = None

    def __enter__(self):
        self.start_time = time.time()
        logger.debug("Operation started", task_id=self.task_id, operation=self.operation_name)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        execution_time = self.end_time - self.start_time

        if exc_type is None:
            logger.debug(
                "Operation completed",
                task_id=self.task_id,
                operation=self.operation_name,
                execution_time=execution_time
            )
        else:
            logger.warning(
                "Operation failed",
                task_id=self.task_id,
                operation=self.operation_name,
                execution_time=execution_time,
                error=str(exc_val)
            )

    @property
    def execution_time(self) -> Optional[float]:
        """Get execution time if operation has completed."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None


def batch_processor(batch_size: int = 10, delay_seconds: float = 1.0):
    """
    Decorator for processing items in batches with delays.

    Args:
        batch_size: Number of items to process in each batch
        delay_seconds: Delay between batches

    Usage:
        @batch_processor(batch_size=5, delay_seconds=2.0)
        def process_items(task_instance, items, process_func):
            # Will automatically batch items and add delays
            pass
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(self, items, process_func, *args, **kwargs):
            task_id = self.request.id
            total_items = len(items)
            processed_count = 0

            logger.info(
                "Starting batch processing",
                task_id=task_id,
                total_items=total_items,
                batch_size=batch_size,
                delay_seconds=delay_seconds
            )

            results = []
            errors = []

            for i in range(0, len(items), batch_size):
                batch_items = items[i:i + batch_size]
                batch_number = (i // batch_size) + 1
                total_batches = (total_items + batch_size - 1) // batch_size

                logger.debug(
                    "Processing batch",
                    task_id=task_id,
                    batch_number=batch_number,
                    total_batches=total_batches,
                    batch_size=len(batch_items)
                )

                # Process batch
                for item in batch_items:
                    try:
                        result = process_func(item)
                        results.append({"item": item, "result": result, "success": True})
                    except Exception as e:
                        logger.warning(
                            "Batch item failed",
                            task_id=task_id,
                            item=str(item)[:100],
                            error=str(e)
                        )
                        errors.append({"item": item, "error": str(e)})

                    processed_count += 1

                    # Update progress
                    if hasattr(self, 'update_progress'):
                        self.update_progress(
                            current=processed_count,
                            message=f"Processed {processed_count}/{total_items} items"
                        )

                # Delay between batches (except for last batch)
                if i + batch_size < len(items) and delay_seconds > 0:
                    time.sleep(delay_seconds)

            return {
                "total_items": total_items,
                "successful": len(results),
                "failed": len(errors),
                "results": results,
                "errors": errors,
            }

        return wrapper
    return decorator


async def wait_for_task_completion(
    task_id: str,
    timeout_seconds: int = 300,
    polling_interval: float = 1.0
) -> Dict[str, Any]:
    """
    Wait for a task to complete with progress monitoring.

    Args:
        task_id: Task ID to wait for
        timeout_seconds: Maximum time to wait
        polling_interval: How often to check status

    Returns:
        Dict with final task status and result
    """
    from celery.result import AsyncResult

    start_time = time.time()
    task_result = AsyncResult(task_id)

    while time.time() - start_time < timeout_seconds:
        # Check Celery status
        if task_result.ready():
            return {
                "task_id": task_id,
                "status": task_result.status,
                "result": task_result.result if task_result.successful() else None,
                "error": str(task_result.result) if task_result.failed() else None,
                "completed": True,
                "execution_time": time.time() - start_time,
            }

        # Check progress information
        progress = await task_monitor.get_task_progress(task_id)
        if progress:
            logger.debug(
                "Task progress",
                task_id=task_id,
                status=progress.get("status"),
                percentage=progress.get("percentage", 0)
            )

        await asyncio.sleep(polling_interval)

    # Timeout reached
    return {
        "task_id": task_id,
        "status": "TIMEOUT",
        "completed": False,
        "timeout_seconds": timeout_seconds,
        "execution_time": time.time() - start_time,
    }


def create_task_chain(*tasks):
    """
    Create a chain of tasks with error handling.

    Args:
        *tasks: Task signatures to chain

    Returns:
        Chained task group
    """
    if not tasks:
        raise ValueError("At least one task is required for a chain")

    # Create a proper Celery chain
    from celery import chain
    return chain(*tasks)


def create_task_group(tasks, timeout_seconds: int = 300):
    """
    Create a group of parallel tasks.

    Args:
        tasks: List of task signatures to run in parallel
        timeout_seconds: Timeout for the group

    Returns:
        Task group result
    """
    from celery import group

    if not tasks:
        raise ValueError("At least one task is required for a group")

    return group(tasks).apply_async()


class TaskExecutionContext:
    """Context manager for task execution with automatic resource cleanup."""

    def __init__(self, task_id: str, task_name: str):
        self.task_id = task_id
        self.task_name = task_name
        self.start_time = None
        self.resources = {}

    def __enter__(self):
        self.start_time = time.time()
        logger.info("Task execution started", task_id=self.task_id, task_name=self.task_name)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        execution_time = time.time() - self.start_time

        # Clean up any registered resources
        for resource_name, cleanup_func in self.resources.items():
            try:
                cleanup_func()
                logger.debug("Resource cleaned up", resource=resource_name)
            except Exception as e:
                logger.warning("Failed to clean up resource", resource=resource_name, error=str(e))

        if exc_type is None:
            logger.info(
                "Task execution completed",
                task_id=self.task_id,
                task_name=self.task_name,
                execution_time=execution_time
            )
        else:
            logger.error(
                "Task execution failed",
                task_id=self.task_id,
                task_name=self.task_name,
                execution_time=execution_time,
                error=str(exc_val)
            )

    def register_cleanup(self, resource_name: str, cleanup_func: Callable):
        """Register a cleanup function for a resource."""
        self.resources[resource_name] = cleanup_func


def retry_with_exponential_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True
):
    """
    Decorator for implementing exponential backoff retry logic.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential calculation
        jitter: Whether to add random jitter to delays
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            import random

            for attempt in range(max_retries + 1):
                try:
                    return func(self, *args, **kwargs)

                except Exception as e:
                    if attempt == max_retries:
                        # Final attempt failed, re-raise
                        raise

                    # Calculate delay
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)

                    # Add jitter if requested
                    if jitter:
                        delay = delay * (0.5 + random.random() * 0.5)

                    logger.warning(
                        "Task attempt failed, retrying",
                        task_id=getattr(self.request, 'id', 'unknown'),
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        delay=delay,
                        error=str(e)
                    )

                    time.sleep(delay)

        return wrapper
    return decorator