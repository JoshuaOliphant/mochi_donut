# ABOUTME: APScheduler configuration for periodic background tasks
# ABOUTME: Replaces Celery Beat with native async scheduler

import logging
from typing import Optional, Callable, Any
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, JobExecutionEvent

logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler: Optional[AsyncIOScheduler] = None


def job_listener(event: JobExecutionEvent):
    """Log job execution events."""
    if event.exception:
        logger.error(
            f"Scheduled job failed: {event.job_id}",
            exc_info=event.exception
        )
    else:
        logger.info(f"Scheduled job completed: {event.job_id}")


def create_scheduler() -> AsyncIOScheduler:
    """
    Create and configure the APScheduler instance.

    Returns:
        Configured AsyncIOScheduler
    """
    scheduler = AsyncIOScheduler(
        timezone="UTC",
        job_defaults={
            "coalesce": True,  # Combine missed runs into one
            "max_instances": 1,  # Only one instance of each job at a time
            "misfire_grace_time": 60 * 5,  # 5 minute grace period
        }
    )

    # Add job execution listener
    scheduler.add_listener(job_listener, EVENT_JOB_ERROR | EVENT_JOB_EXECUTED)

    return scheduler


def configure_scheduled_jobs(scheduler: AsyncIOScheduler):
    """
    Configure all scheduled jobs (replaces Celery Beat schedule).

    Migrates these 6 jobs from celery_app.py beat_schedule:
    1. aggregate_analytics - Daily 2 AM
    2. invalidate_cache - Every 6 hours
    3. cleanup_old_data - Weekly Sunday 3 AM
    4. health_check - Every 15 minutes
    5. verify_sync - Daily 1 AM
    6. track_costs - Daily 4 AM
    """
    # Import tasks here to avoid circular imports
    from app.background.tasks import (
        aggregate_analytics,
        invalidate_cache,
        cleanup_old_data,
        health_check,
        verify_sync,
        track_costs,
    )

    # Daily analytics aggregation at 2 AM
    scheduler.add_job(
        aggregate_analytics,
        CronTrigger(hour=2, minute=0),
        id="aggregate-daily-analytics",
        name="Aggregate daily analytics",
        kwargs={"period": "daily"},
        replace_existing=True,
    )

    # Cache cleanup every 6 hours
    scheduler.add_job(
        invalidate_cache,
        IntervalTrigger(hours=6),
        id="cleanup-expired-cache",
        name="Invalidate expired cache entries",
        replace_existing=True,
    )

    # Database cleanup weekly on Sunday at 3 AM
    scheduler.add_job(
        cleanup_old_data,
        CronTrigger(day_of_week="sun", hour=3, minute=0),
        id="cleanup-old-data",
        name="Clean up old data",
        kwargs={"retention_days": 30},
        replace_existing=True,
    )

    # Health checks every 15 minutes
    scheduler.add_job(
        health_check,
        IntervalTrigger(minutes=15),
        id="system-health-check",
        name="System health check",
        replace_existing=True,
    )

    # Mochi sync verification daily at 1 AM
    scheduler.add_job(
        verify_sync,
        CronTrigger(hour=1, minute=0),
        id="verify-mochi-sync",
        name="Verify Mochi sync status",
        replace_existing=True,
    )

    # AI cost tracking daily at 4 AM
    scheduler.add_job(
        track_costs,
        CronTrigger(hour=4, minute=0),
        id="track-ai-costs",
        name="Track AI usage costs",
        kwargs={"period": "daily"},
        replace_existing=True,
    )

    logger.info("Configured 6 scheduled jobs")


def get_scheduler() -> Optional[AsyncIOScheduler]:
    """Get the global scheduler instance."""
    return _scheduler


def init_scheduler() -> AsyncIOScheduler:
    """Initialize and start the global scheduler."""
    global _scheduler

    if _scheduler is not None:
        logger.warning("Scheduler already initialized")
        return _scheduler

    _scheduler = create_scheduler()
    configure_scheduled_jobs(_scheduler)
    _scheduler.start()
    logger.info("Scheduler started")

    return _scheduler


def shutdown_scheduler():
    """Shutdown the global scheduler."""
    global _scheduler

    if _scheduler is not None:
        _scheduler.shutdown(wait=True)
        _scheduler = None
        logger.info("Scheduler shutdown complete")


def add_job(
    func: Callable,
    trigger: Any,
    job_id: str,
    name: str = None,
    **kwargs
) -> str:
    """
    Add a new job to the scheduler dynamically.

    Args:
        func: Async function to execute
        trigger: APScheduler trigger (CronTrigger, IntervalTrigger, etc.)
        job_id: Unique job identifier
        name: Human-readable job name
        **kwargs: Additional arguments passed to the job

    Returns:
        Job ID
    """
    if _scheduler is None:
        raise RuntimeError("Scheduler not initialized")

    _scheduler.add_job(
        func,
        trigger,
        id=job_id,
        name=name or job_id,
        replace_existing=True,
        **kwargs,
    )
    logger.info(f"Added job: {job_id}")
    return job_id


def remove_job(job_id: str) -> bool:
    """
    Remove a job from the scheduler.

    Args:
        job_id: Job identifier to remove

    Returns:
        True if removed, False if not found
    """
    if _scheduler is None:
        raise RuntimeError("Scheduler not initialized")

    try:
        _scheduler.remove_job(job_id)
        logger.info(f"Removed job: {job_id}")
        return True
    except Exception:
        logger.warning(f"Job not found: {job_id}")
        return False


def get_jobs() -> list[dict]:
    """
    Get information about all scheduled jobs.

    Returns:
        List of job info dictionaries
    """
    if _scheduler is None:
        return []

    jobs = []
    for job in _scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
        })
    return jobs
