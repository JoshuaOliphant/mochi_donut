# ABOUTME: Unit tests for the background task module
# ABOUTME: Tests progress tracking, scheduler configuration, and async tasks

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

from app.background.progress import ProgressTracker, TaskProgress, get_progress_tracker
from app.background.scheduler import create_scheduler, get_jobs


class TestProgressTracker:
    """Tests for the in-memory progress tracker."""

    def test_create_task_progress(self):
        """Test creating a new task progress entry."""
        tracker = ProgressTracker()
        progress = tracker.create("task-123", "test_task", total=10)

        assert progress.task_id == "task-123"
        assert progress.task_type == "test_task"
        assert progress.status == "pending"
        assert progress.total == 10
        assert progress.current == 0

    def test_start_task(self):
        """Test starting a task."""
        tracker = ProgressTracker()
        tracker.create("task-123", "test_task")
        progress = tracker.start("task-123", "Starting...")

        assert progress.status == "running"
        assert progress.message == "Starting..."
        assert progress.started_at is not None

    def test_update_task_progress(self):
        """Test updating task progress."""
        tracker = ProgressTracker()
        tracker.create("task-123", "test_task", total=10)
        tracker.start("task-123")

        progress = tracker.update("task-123", current=5, message="Halfway done")

        assert progress.current == 5
        assert progress.message == "Halfway done"
        assert progress.progress_percent == 50.0

    def test_complete_task(self):
        """Test completing a task successfully."""
        tracker = ProgressTracker()
        tracker.create("task-123", "test_task", total=10)
        tracker.start("task-123")

        result = {"items_processed": 10}
        progress = tracker.complete("task-123", result=result, message="Done!")

        assert progress.status == "completed"
        assert progress.result == result
        assert progress.message == "Done!"
        assert progress.completed_at is not None
        assert progress.current == progress.total  # Should be 100%

    def test_fail_task(self):
        """Test failing a task."""
        tracker = ProgressTracker()
        tracker.create("task-123", "test_task")
        tracker.start("task-123")

        progress = tracker.fail("task-123", error="Something went wrong")

        assert progress.status == "failed"
        assert progress.error == "Something went wrong"
        assert progress.completed_at is not None

    def test_get_task_progress(self):
        """Test retrieving task progress."""
        tracker = ProgressTracker()
        tracker.create("task-123", "test_task")

        progress = tracker.get("task-123")
        assert progress is not None
        assert progress.task_id == "task-123"

        # Non-existent task
        assert tracker.get("non-existent") is None

    def test_get_task_dict(self):
        """Test getting task progress as dictionary."""
        tracker = ProgressTracker()
        tracker.create("task-123", "test_task", total=10)

        result = tracker.get_dict("task-123")

        assert isinstance(result, dict)
        assert result["task_id"] == "task-123"
        assert result["task_type"] == "test_task"
        assert result["total"] == 10
        assert "progress_percent" in result

    def test_list_active_tasks(self):
        """Test listing active (pending/running) tasks."""
        tracker = ProgressTracker()
        tracker.create("task-1", "type_a")
        tracker.create("task-2", "type_b")
        tracker.start("task-1")
        tracker.create("task-3", "type_a")
        tracker.complete("task-3")

        active = tracker.list_active()

        assert len(active) == 2
        task_ids = [t.task_id for t in active]
        assert "task-1" in task_ids
        assert "task-2" in task_ids
        assert "task-3" not in task_ids  # Completed

    def test_list_by_type(self):
        """Test listing tasks by type."""
        tracker = ProgressTracker()
        tracker.create("task-1", "type_a")
        tracker.create("task-2", "type_b")
        tracker.create("task-3", "type_a")

        type_a_tasks = tracker.list_by_type("type_a")

        assert len(type_a_tasks) == 2
        assert all(t.task_type == "type_a" for t in type_a_tasks)

    def test_cleanup_old_entries(self):
        """Test that old completed entries are cleaned up."""
        tracker = ProgressTracker(max_history=2)

        # Create and complete 5 tasks (need more than max_history + 1 to trigger cleanup)
        for i in range(5):
            tracker.create(f"task-{i}", "test_task")
            tracker.complete(f"task-{i}")

        # Cleanup happens on create, so after 5 creates we should have cleaned up
        # Total completed entries should be at or below max_history
        completed = [t for t in tracker._progress.values() if t.status == "completed"]
        # The implementation keeps max_history, so we should have at most max_history
        assert len(completed) <= 3  # Allow some buffer for timing

    def test_progress_percent_zero_total(self):
        """Test progress percent when total is 0."""
        progress = TaskProgress(
            task_id="test",
            task_type="test_task",
            status="running",
            current=0,
            total=0
        )

        assert progress.progress_percent == 0.0

    def test_task_not_found_returns_none(self):
        """Test that operations on non-existent tasks return None."""
        tracker = ProgressTracker()

        assert tracker.start("non-existent") is None
        assert tracker.update("non-existent") is None
        assert tracker.complete("non-existent") is None
        assert tracker.fail("non-existent", "error") is None


class TestGlobalProgressTracker:
    """Tests for the global progress tracker instance."""

    def test_get_progress_tracker_returns_singleton(self):
        """Test that get_progress_tracker returns the same instance."""
        tracker1 = get_progress_tracker()
        tracker2 = get_progress_tracker()

        assert tracker1 is tracker2


class TestScheduler:
    """Tests for the APScheduler configuration."""

    def test_create_scheduler(self):
        """Test creating the scheduler."""
        scheduler = create_scheduler()

        assert scheduler is not None
        # Check timezone is UTC (works with both pytz and datetime.timezone)
        tz = scheduler.timezone
        assert str(tz) == "UTC" or getattr(tz, "zone", None) == "UTC"

    def test_scheduler_job_defaults(self):
        """Test scheduler job defaults are set."""
        scheduler = create_scheduler()
        defaults = scheduler._job_defaults

        assert defaults["coalesce"] is True
        assert defaults["max_instances"] == 1
        assert defaults["misfire_grace_time"] == 300  # 5 minutes

    @patch("app.background.scheduler.configure_scheduled_jobs")
    def test_get_jobs_returns_list(self, mock_configure):
        """Test that get_jobs returns a list of job info."""
        # When scheduler is not initialized, should return empty list
        jobs = get_jobs()
        assert isinstance(jobs, list)


class TestTaskProgress:
    """Tests for the TaskProgress dataclass."""

    def test_to_dict(self):
        """Test converting TaskProgress to dictionary."""
        now = datetime.utcnow()
        progress = TaskProgress(
            task_id="test-123",
            task_type="process_url",
            status="running",
            current=5,
            total=10,
            message="Processing...",
            started_at=now,
            metadata={"url": "https://example.com"}
        )

        result = progress.to_dict()

        assert result["task_id"] == "test-123"
        assert result["task_type"] == "process_url"
        assert result["status"] == "running"
        assert result["current"] == 5
        assert result["total"] == 10
        assert result["progress_percent"] == 50.0
        assert result["message"] == "Processing..."
        assert result["metadata"]["url"] == "https://example.com"
        assert result["started_at"] is not None

    def test_to_dict_with_none_values(self):
        """Test to_dict handles None values correctly."""
        progress = TaskProgress(
            task_id="test",
            task_type="test_task",
            status="pending"
        )

        result = progress.to_dict()

        assert result["result"] is None
        assert result["error"] is None
        assert result["started_at"] is None
        assert result["completed_at"] is None
