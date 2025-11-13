"""
Celery tasks package for the Mochi Donut system.

This package contains all background task implementations including:
- Content processing tasks (JinaAI integration, vector embeddings)
- AI agent tasks (prompt generation, quality review, refinement)
- Mochi sync tasks (card creation, batch operations)
- Maintenance tasks (cleanup, analytics, health monitoring)

Usage:
    from app.tasks import celery_app
    from app.tasks.content_tasks import process_url_content
    from app.tasks.agent_tasks import generate_prompts
    from app.tasks.sync_tasks import create_mochi_card
    from app.tasks.maintenance_tasks import health_check

    # Start Celery worker:
    # uv run celery -A app.tasks worker --loglevel=info

    # Start Celery beat scheduler:
    # uv run celery -A app.tasks beat --loglevel=info
"""

from app.tasks.celery_app import celery_app, get_celery_app, celery_health_check

# Import all task modules to ensure they're registered
from app.tasks import content_tasks
from app.tasks import agent_tasks
from app.tasks import sync_tasks
from app.tasks import maintenance_tasks

__all__ = [
    "celery_app",
    "get_celery_app",
    "celery_health_check",
    "content_tasks",
    "agent_tasks",
    "sync_tasks",
    "maintenance_tasks",
]