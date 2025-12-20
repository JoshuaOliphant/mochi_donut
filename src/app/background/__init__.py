# ABOUTME: Background task module for async operations and scheduling
# ABOUTME: Replaces Celery with native async/await and APScheduler

from app.background.progress import (
    ProgressTracker,
    TaskProgress,
    get_progress_tracker,
    progress_tracker,
)
from app.background.scheduler import (
    create_scheduler,
    init_scheduler,
    shutdown_scheduler,
    get_scheduler,
    add_job,
    remove_job,
    get_jobs,
)

__all__ = [
    # Progress tracking
    "ProgressTracker",
    "TaskProgress",
    "get_progress_tracker",
    "progress_tracker",
    # Scheduler
    "create_scheduler",
    "init_scheduler",
    "shutdown_scheduler",
    "get_scheduler",
    "add_job",
    "remove_job",
    "get_jobs",
]
