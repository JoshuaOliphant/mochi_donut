"""
Celery application configuration for Mochi Donut background processing.

This module sets up the Celery app with Redis broker, task routing, and
monitoring capabilities for the spaced repetition learning system.
"""

import os
from typing import Dict, Any
from celery import Celery
from celery.schedules import crontab
from kombu import Queue
import structlog

# Configure structured logging
logger = structlog.get_logger()

# Redis configuration from environment
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_RESULT_BACKEND = os.getenv("REDIS_RESULT_BACKEND", "redis://localhost:6379/1")

# Celery application configuration
celery_app = Celery(
    "mochi_donut",
    broker=REDIS_URL,
    backend=REDIS_RESULT_BACKEND,
    include=[
        "app.tasks.content_tasks",
        "app.tasks.agent_tasks",
        "app.tasks.sync_tasks",
        "app.tasks.maintenance_tasks",
    ]
)

# Task routing configuration
TASK_ROUTES = {
    # Content processing tasks - high priority queue
    "app.tasks.content_tasks.process_url_content": {"queue": "content_processing"},
    "app.tasks.content_tasks.extract_content_jina": {"queue": "content_processing"},
    "app.tasks.content_tasks.generate_embeddings": {"queue": "content_processing"},
    "app.tasks.content_tasks.detect_duplicates": {"queue": "content_processing"},
    "app.tasks.content_tasks.batch_process_content": {"queue": "content_processing"},

    # AI agent tasks - dedicated queue for GPU/memory intensive work
    "app.tasks.agent_tasks.generate_prompts": {"queue": "ai_processing"},
    "app.tasks.agent_tasks.review_prompt_quality": {"queue": "ai_processing"},
    "app.tasks.agent_tasks.refine_prompts": {"queue": "ai_processing"},
    "app.tasks.agent_tasks.track_ai_costs": {"queue": "ai_processing"},

    # Mochi sync tasks - external API queue
    "app.tasks.sync_tasks.create_mochi_card": {"queue": "external_apis"},
    "app.tasks.sync_tasks.batch_sync_cards": {"queue": "external_apis"},
    "app.tasks.sync_tasks.sync_deck_metadata": {"queue": "external_apis"},
    "app.tasks.sync_tasks.verify_sync_status": {"queue": "external_apis"},

    # Maintenance tasks - low priority queue
    "app.tasks.maintenance_tasks.cleanup_old_data": {"queue": "maintenance"},
    "app.tasks.maintenance_tasks.invalidate_expired_cache": {"queue": "maintenance"},
    "app.tasks.maintenance_tasks.aggregate_analytics": {"queue": "maintenance"},
    "app.tasks.maintenance_tasks.health_check": {"queue": "maintenance"},
}

# Queue definitions with priority levels
TASK_QUEUES = [
    Queue("content_processing", routing_key="content_processing"),
    Queue("ai_processing", routing_key="ai_processing"),
    Queue("external_apis", routing_key="external_apis"),
    Queue("maintenance", routing_key="maintenance"),
]

# Celery configuration
celery_app.conf.update(
    # Task routing
    task_routes=TASK_ROUTES,
    task_default_queue="content_processing",
    task_default_exchange="tasks",
    task_default_exchange_type="direct",
    task_default_routing_key="content_processing",

    # Task execution settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task result settings
    result_expires=3600,  # 1 hour
    result_backend_transport_options={
        "master_name": "mymaster",
        "visibility_timeout": 3600,
    },

    # Task retry and error handling
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,  # Prevent worker overload

    # Retry policy defaults
    task_default_retry_delay=60,    # 1 minute
    task_max_retries=3,

    # Rate limiting
    task_annotations={
        # Content processing - moderate rate limiting
        "app.tasks.content_tasks.*": {"rate_limit": "10/m"},

        # AI tasks - more conservative rate limiting due to cost
        "app.tasks.agent_tasks.generate_prompts": {"rate_limit": "5/m"},
        "app.tasks.agent_tasks.review_prompt_quality": {"rate_limit": "3/m"},
        "app.tasks.agent_tasks.refine_prompts": {"rate_limit": "2/m"},

        # External APIs - respect API limits
        "app.tasks.sync_tasks.*": {"rate_limit": "20/m"},

        # Maintenance - low priority
        "app.tasks.maintenance_tasks.*": {"rate_limit": "2/m"},
    },

    # Worker configuration
    worker_max_tasks_per_child=1000,
    worker_disable_rate_limits=False,
    worker_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
    worker_task_log_format="[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s",

    # Beat scheduler configuration
    beat_schedule={
        # Analytics aggregation - daily at 2 AM
        "aggregate-daily-analytics": {
            "task": "app.tasks.maintenance_tasks.aggregate_analytics",
            "schedule": crontab(hour=2, minute=0),
            "args": ("daily",),
        },

        # Cache cleanup - every 6 hours
        "cleanup-expired-cache": {
            "task": "app.tasks.maintenance_tasks.invalidate_expired_cache",
            "schedule": crontab(minute=0, hour="*/6"),
        },

        # Database cleanup - weekly on Sunday at 3 AM
        "cleanup-old-data": {
            "task": "app.tasks.maintenance_tasks.cleanup_old_data",
            "schedule": crontab(hour=3, minute=0, day_of_week=0),
            "args": (30,),  # Keep data for 30 days
        },

        # Health checks - every 15 minutes
        "system-health-check": {
            "task": "app.tasks.maintenance_tasks.health_check",
            "schedule": crontab(minute="*/15"),
        },

        # Sync verification - daily at 1 AM
        "verify-mochi-sync": {
            "task": "app.tasks.sync_tasks.verify_sync_status",
            "schedule": crontab(hour=1, minute=0),
        },

        # Cost tracking - daily at 4 AM
        "track-ai-costs": {
            "task": "app.tasks.agent_tasks.track_ai_costs",
            "schedule": crontab(hour=4, minute=0),
            "args": ("daily",),
        },
    },

    # Monitoring and logging
    worker_send_task_events=True,
    task_send_sent_event=True,

    # Security settings
    worker_hijack_root_logger=False,
    worker_redirect_stdouts=True,
    worker_redirect_stdouts_level="INFO",
)

# Task priority levels (0 = highest, 9 = lowest)
TASK_PRIORITIES = {
    "content_processing": 3,
    "ai_processing": 4,
    "external_apis": 5,
    "maintenance": 7,
}


class TaskConfig:
    """Configuration class for task settings and utilities."""

    @staticmethod
    def get_retry_config(task_type: str) -> Dict[str, Any]:
        """Get retry configuration for different task types."""
        configs = {
            "content": {
                "autoretry_for": (Exception,),
                "retry_kwargs": {"max_retries": 3, "countdown": 60},
                "retry_backoff": True,
                "retry_backoff_max": 600,  # 10 minutes max
                "retry_jitter": True,
            },
            "ai": {
                "autoretry_for": (Exception,),
                "retry_kwargs": {"max_retries": 2, "countdown": 120},
                "retry_backoff": True,
                "retry_backoff_max": 1200,  # 20 minutes max
                "retry_jitter": True,
            },
            "external_api": {
                "autoretry_for": (Exception,),
                "retry_kwargs": {"max_retries": 5, "countdown": 30},
                "retry_backoff": True,
                "retry_backoff_max": 300,  # 5 minutes max
                "retry_jitter": True,
            },
            "maintenance": {
                "autoretry_for": (Exception,),
                "retry_kwargs": {"max_retries": 1, "countdown": 300},
                "retry_backoff": False,
                "retry_jitter": False,
            },
        }
        return configs.get(task_type, configs["content"])

    @staticmethod
    def get_task_logger(task_name: str) -> structlog.BoundLogger:
        """Get a structured logger for tasks."""
        return logger.bind(task=task_name)


# Task state callbacks for monitoring
@celery_app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery configuration."""
    logger.info("Debug task executed", task_id=self.request.id)
    return f"Request: {self.request!r}"


# Error handling callback
def task_failure_handler(sender=None, task_id=None, exception=None, traceback=None, einfo=None):
    """Handle task failures with proper logging."""
    logger.error(
        "Task failed",
        task_id=task_id,
        task_name=sender.name if sender else "unknown",
        exception=str(exception),
        traceback=traceback,
    )


def task_success_handler(sender=None, result=None, **kwargs):
    """Handle task success with metrics."""
    logger.info(
        "Task completed successfully",
        task_name=sender.name if sender else "unknown",
        result_type=type(result).__name__,
    )


# Connect signal handlers
celery_app.signals.task_failure.connect(task_failure_handler)
celery_app.signals.task_success.connect(task_success_handler)


def get_celery_app() -> Celery:
    """Get the configured Celery application."""
    return celery_app


# Health check for Celery
def celery_health_check() -> Dict[str, Any]:
    """Check Celery application health."""
    try:
        # Test broker connection
        inspector = celery_app.control.inspect()
        stats = inspector.stats()

        # Test task submission
        result = debug_task.delay()

        return {
            "status": "healthy",
            "broker_connected": bool(stats),
            "active_workers": len(stats) if stats else 0,
            "test_task_id": result.id,
        }
    except Exception as e:
        logger.error("Celery health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "error": str(e),
            "broker_connected": False,
            "active_workers": 0,
        }


if __name__ == "__main__":
    # CLI entry point for development
    celery_app.start()