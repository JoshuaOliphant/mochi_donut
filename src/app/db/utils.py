# Database Utilities - Helper Functions and Performance Tools
"""
Database utility functions for initialization, health checks, performance monitoring,
and maintenance operations for the Mochi Donut SQLAlchemy setup.
"""

import hashlib
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import uuid

from sqlalchemy import text, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.engine import Result

from app.db.config import get_database_manager
from app.db.models import Content, ProcessingStatus, SourceType


class DatabaseUtils:
    """
    Utility class for database operations and maintenance.
    """

    @staticmethod
    def generate_content_hash(content: str) -> str:
        """
        Generate SHA-256 hash for content deduplication.

        Args:
            content: Content string to hash

        Returns:
            Hexadecimal hash string
        """
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    async def health_check(session: AsyncSession) -> Dict[str, Any]:
        """
        Perform comprehensive database health check.

        Args:
            session: Async database session

        Returns:
            Dictionary with health check results
        """
        start_time = time.time()
        health_status = {
            "database_accessible": False,
            "response_time_ms": 0,
            "table_counts": {},
            "recent_activity": {},
            "errors": []
        }

        try:
            # Basic connectivity test
            result = await session.execute(text("SELECT 1"))
            if result.scalar() == 1:
                health_status["database_accessible"] = True

            # Get table counts
            content_count = await session.scalar(
                select(func.count(Content.id))
            )
            health_status["table_counts"]["content"] = content_count or 0

            # Check recent activity (last 24 hours)
            recent_cutoff = datetime.utcnow() - timedelta(hours=24)
            recent_content = await session.scalar(
                select(func.count(Content.id))
                .where(Content.created_at >= recent_cutoff)
            )
            health_status["recent_activity"]["new_content_24h"] = recent_content or 0

            # Check processing status distribution
            processing_stats = await session.execute(
                select(
                    Content.processing_status,
                    func.count(Content.id).label("count")
                )
                .group_by(Content.processing_status)
            )

            status_counts = {}
            for row in processing_stats:
                status_counts[row.processing_status.value] = row.count

            health_status["processing_status"] = status_counts

        except Exception as e:
            health_status["errors"].append(str(e))

        health_status["response_time_ms"] = int((time.time() - start_time) * 1000)
        return health_status

    @staticmethod
    async def get_database_statistics(session: AsyncSession) -> Dict[str, Any]:
        """
        Get comprehensive database statistics.

        Args:
            session: Async database session

        Returns:
            Dictionary with database statistics
        """
        stats = {
            "content": {},
            "processing": {},
            "source_types": {},
            "performance": {}
        }

        # Content statistics
        content_stats = await session.execute(
            select(
                func.count(Content.id).label("total"),
                func.avg(Content.word_count).label("avg_words"),
                func.sum(Content.word_count).label("total_words"),
                func.min(Content.created_at).label("oldest"),
                func.max(Content.created_at).label("newest")
            )
        )

        row = content_stats.first()
        if row:
            stats["content"] = {
                "total_items": int(row.total or 0),
                "avg_word_count": float(row.avg_words or 0),
                "total_word_count": int(row.total_words or 0),
                "oldest_content": row.oldest.isoformat() if row.oldest else None,
                "newest_content": row.newest.isoformat() if row.newest else None
            }

        # Processing status distribution
        processing_stats = await session.execute(
            select(
                Content.processing_status,
                func.count(Content.id).label("count")
            )
            .group_by(Content.processing_status)
        )

        stats["processing"] = {
            row.processing_status.value: row.count
            for row in processing_stats
        }

        # Source type distribution
        source_stats = await session.execute(
            select(
                Content.source_type,
                func.count(Content.id).label("count")
            )
            .group_by(Content.source_type)
        )

        stats["source_types"] = {
            row.source_type.value: row.count
            for row in source_stats
        }

        return stats

    @staticmethod
    async def cleanup_old_failed_content(
        session: AsyncSession,
        days: int = 30
    ) -> int:
        """
        Clean up old failed content with no associated prompts.

        Args:
            session: Async database session
            days: Remove failed content older than this many days

        Returns:
            Number of records deleted
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Find failed content older than cutoff with no prompts
        failed_content = await session.execute(
            select(Content.id)
            .where(
                Content.processing_status == ProcessingStatus.FAILED,
                Content.updated_at < cutoff_date
            )
            .outerjoin(Content.prompts)
            .where(Content.prompts == None)
        )

        failed_ids = [row.id for row in failed_content]

        if failed_ids:
            # Delete the failed content
            await session.execute(
                text("DELETE FROM contents WHERE id = ANY(:ids)"),
                {"ids": failed_ids}
            )
            await session.commit()

        return len(failed_ids)

    @staticmethod
    async def find_duplicate_content(
        session: AsyncSession,
        limit: int = 100
    ) -> List[Tuple[str, List[uuid.UUID]]]:
        """
        Find potential duplicate content by hash.

        Args:
            session: Async database session
            limit: Maximum number of duplicate groups to return

        Returns:
            List of (hash, [content_ids]) tuples for duplicates
        """
        duplicates_query = await session.execute(
            select(
                Content.content_hash,
                func.array_agg(Content.id).label("content_ids"),
                func.count(Content.id).label("count")
            )
            .group_by(Content.content_hash)
            .having(func.count(Content.id) > 1)
            .order_by(func.count(Content.id).desc())
            .limit(limit)
        )

        return [
            (row.content_hash, list(row.content_ids))
            for row in duplicates_query
        ]

    @staticmethod
    async def vacuum_analyze_database(session: AsyncSession) -> bool:
        """
        Perform database maintenance (PostgreSQL specific).

        Args:
            session: Async database session

        Returns:
            True if successful, False otherwise
        """
        try:
            # This is PostgreSQL specific - SQLite doesn't need VACUUM in async context
            await session.execute(text("ANALYZE"))
            await session.commit()
            return True
        except Exception:
            await session.rollback()
            return False

    @staticmethod
    async def get_slow_queries_info(session: AsyncSession) -> List[Dict[str, Any]]:
        """
        Get information about slow queries (PostgreSQL specific).

        Args:
            session: Async database session

        Returns:
            List of slow query information
        """
        try:
            # This requires pg_stat_statements extension
            slow_queries = await session.execute(
                text("""
                SELECT
                    query,
                    calls,
                    total_exec_time,
                    mean_exec_time,
                    rows
                FROM pg_stat_statements
                WHERE query LIKE '%contents%' OR query LIKE '%prompts%'
                ORDER BY mean_exec_time DESC
                LIMIT 10
                """)
            )

            return [
                {
                    "query": row.query,
                    "calls": row.calls,
                    "total_time": row.total_exec_time,
                    "mean_time": row.mean_exec_time,
                    "rows": row.rows
                }
                for row in slow_queries
            ]
        except Exception:
            # Extension not available or not PostgreSQL
            return []


@asynccontextmanager
async def get_db_session():
    """
    Context manager for database sessions with automatic cleanup.

    Yields:
        Async database session with automatic commit/rollback
    """
    db_manager = get_database_manager()
    async with db_manager.session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def initialize_database():
    """
    Initialize database with tables and initial data.
    """
    db_manager = get_database_manager()
    await db_manager.create_all_tables()


async def check_database_connection() -> bool:
    """
    Simple database connectivity check.

    Returns:
        True if database is accessible, False otherwise
    """
    try:
        async with get_db_session() as session:
            result = await session.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception:
        return False


class PerformanceMonitor:
    """
    Performance monitoring utilities for database operations.
    """

    @staticmethod
    @asynccontextmanager
    async def time_query(session: AsyncSession, operation_name: str):
        """
        Context manager to time database operations.

        Args:
            session: Database session
            operation_name: Name of the operation for logging

        Yields:
            Dictionary that will contain timing information
        """
        start_time = time.time()
        timing_info = {"operation": operation_name}

        try:
            yield timing_info
        finally:
            end_time = time.time()
            timing_info.update({
                "duration_ms": int((end_time - start_time) * 1000),
                "start_time": datetime.fromtimestamp(start_time),
                "end_time": datetime.fromtimestamp(end_time)
            })

    @staticmethod
    async def get_table_sizes(session: AsyncSession) -> Dict[str, Dict[str, Any]]:
        """
        Get table sizes and row counts (PostgreSQL specific).

        Args:
            session: Database session

        Returns:
            Dictionary with table size information
        """
        try:
            # PostgreSQL specific query
            size_query = await session.execute(
                text("""
                SELECT
                    schemaname,
                    tablename,
                    attname,
                    n_distinct,
                    correlation
                FROM pg_stats
                WHERE schemaname = 'public'
                AND tablename IN ('contents', 'prompts', 'quality_metrics')
                """)
            )

            table_info = {}
            for row in size_query:
                table_name = row.tablename
                if table_name not in table_info:
                    table_info[table_name] = {"columns": []}

                table_info[table_name]["columns"].append({
                    "name": row.attname,
                    "n_distinct": row.n_distinct,
                    "correlation": row.correlation
                })

            return table_info
        except Exception:
            # Fallback for non-PostgreSQL databases
            return {}


# Migration utilities
async def run_data_migration(
    session: AsyncSession,
    migration_func,
    batch_size: int = 1000
) -> int:
    """
    Run a data migration function in batches.

    Args:
        session: Database session
        migration_func: Function to run on each batch
        batch_size: Size of each batch

    Returns:
        Total number of records processed
    """
    processed = 0
    offset = 0

    while True:
        batch = await migration_func(session, offset, batch_size)
        if not batch:
            break

        processed += len(batch)
        offset += batch_size

        # Commit each batch
        await session.commit()

    return processed