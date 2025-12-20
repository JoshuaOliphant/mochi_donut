# ABOUTME: In-memory progress tracking for background tasks
# ABOUTME: Simple dict-based storage for task progress without Redis dependency

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TaskProgress:
    """Progress information for a single task."""
    task_id: str
    task_type: str
    status: str  # pending, running, completed, failed
    current: int = 0
    total: int = 0
    message: str = ""
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def progress_percent(self) -> float:
        """Calculate progress percentage."""
        if self.total == 0:
            return 0.0
        return (self.current / self.total) * 100

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status,
            "current": self.current,
            "total": self.total,
            "progress_percent": self.progress_percent,
            "message": self.message,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "metadata": self.metadata,
        }


class ProgressTracker:
    """
    In-memory progress tracking for background tasks.

    Thread-safe storage for tracking task progress without Redis.
    Progress is lost on server restart (acceptable for this use case).
    """

    def __init__(self, max_history: int = 1000):
        """
        Initialize progress tracker.

        Args:
            max_history: Maximum number of completed tasks to keep in memory
        """
        self._progress: Dict[str, TaskProgress] = {}
        self._max_history = max_history

    def create(self, task_id: str, task_type: str, total: int = 0, metadata: Optional[Dict] = None) -> TaskProgress:
        """
        Create a new task progress entry.

        Args:
            task_id: Unique task identifier
            task_type: Type of task (e.g., 'content_processing', 'mochi_sync')
            total: Total items to process (for batch operations)
            metadata: Optional metadata about the task

        Returns:
            TaskProgress instance
        """
        progress = TaskProgress(
            task_id=task_id,
            task_type=task_type,
            status="pending",
            total=total,
            started_at=datetime.utcnow(),
            metadata=metadata or {},
        )
        self._progress[task_id] = progress
        self._cleanup_old_entries()
        logger.debug(f"Created task progress: {task_id} ({task_type})")
        return progress

    def start(self, task_id: str, message: str = "Starting...") -> Optional[TaskProgress]:
        """Mark a task as started/running."""
        if task_id not in self._progress:
            logger.warning(f"Task not found for start: {task_id}")
            return None

        progress = self._progress[task_id]
        progress.status = "running"
        progress.message = message
        progress.started_at = datetime.utcnow()
        logger.debug(f"Task started: {task_id}")
        return progress

    def update(
        self,
        task_id: str,
        current: Optional[int] = None,
        total: Optional[int] = None,
        message: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> Optional[TaskProgress]:
        """
        Update task progress.

        Args:
            task_id: Task identifier
            current: Current progress count
            total: Total items (can be updated if discovered during execution)
            message: Progress message
            metadata: Additional metadata to merge

        Returns:
            Updated TaskProgress or None if not found
        """
        if task_id not in self._progress:
            logger.warning(f"Task not found for update: {task_id}")
            return None

        progress = self._progress[task_id]

        if current is not None:
            progress.current = current
        if total is not None:
            progress.total = total
        if message is not None:
            progress.message = message
        if metadata:
            progress.metadata.update(metadata)

        logger.debug(f"Task progress: {task_id} - {progress.current}/{progress.total}")
        return progress

    def complete(
        self,
        task_id: str,
        result: Optional[Dict[str, Any]] = None,
        message: str = "Completed"
    ) -> Optional[TaskProgress]:
        """Mark a task as completed successfully."""
        if task_id not in self._progress:
            logger.warning(f"Task not found for completion: {task_id}")
            return None

        progress = self._progress[task_id]
        progress.status = "completed"
        progress.message = message
        progress.result = result
        progress.completed_at = datetime.utcnow()
        progress.current = progress.total  # Ensure 100%
        logger.info(f"Task completed: {task_id}")
        return progress

    def fail(
        self,
        task_id: str,
        error: str,
        message: str = "Failed"
    ) -> Optional[TaskProgress]:
        """Mark a task as failed."""
        if task_id not in self._progress:
            logger.warning(f"Task not found for failure: {task_id}")
            return None

        progress = self._progress[task_id]
        progress.status = "failed"
        progress.message = message
        progress.error = error
        progress.completed_at = datetime.utcnow()
        logger.error(f"Task failed: {task_id} - {error}")
        return progress

    def get(self, task_id: str) -> Optional[TaskProgress]:
        """Get task progress by ID."""
        return self._progress.get(task_id)

    def get_dict(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task progress as dictionary for API responses."""
        progress = self.get(task_id)
        return progress.to_dict() if progress else None

    def list_active(self) -> list[TaskProgress]:
        """List all active (pending or running) tasks."""
        return [
            p for p in self._progress.values()
            if p.status in ("pending", "running")
        ]

    def list_by_type(self, task_type: str) -> list[TaskProgress]:
        """List all tasks of a specific type."""
        return [
            p for p in self._progress.values()
            if p.task_type == task_type
        ]

    def _cleanup_old_entries(self):
        """Remove old completed/failed entries to prevent memory bloat."""
        completed = [
            (task_id, p) for task_id, p in self._progress.items()
            if p.status in ("completed", "failed")
        ]

        if len(completed) > self._max_history:
            # Sort by completion time and remove oldest
            completed.sort(key=lambda x: x[1].completed_at or datetime.min)
            to_remove = len(completed) - self._max_history
            for task_id, _ in completed[:to_remove]:
                del self._progress[task_id]
            logger.debug(f"Cleaned up {to_remove} old task entries")


# Global progress tracker instance
progress_tracker = ProgressTracker()


def get_progress_tracker() -> ProgressTracker:
    """Get the global progress tracker instance."""
    return progress_tracker
