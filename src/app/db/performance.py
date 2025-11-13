# Database Performance Optimization - Query Patterns and Caching
"""
Performance optimization utilities for SQLAlchemy operations including
query optimization, caching strategies, and monitoring tools.
"""

import asyncio
import time
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.sql import Select

from app.db.models import Content, Prompt, QualityMetric


F = TypeVar('F', bound=Callable[..., Any])


class QueryOptimizer:
    """
    Query optimization utilities and patterns for common operations.
    """

    @staticmethod
    def optimize_content_with_prompts(query: Select) -> Select:
        """
        Optimize query for loading content with prompts to avoid N+1 queries.

        Args:
            query: Base SQLAlchemy select query

        Returns:
            Optimized query with eager loading
        """
        return query.options(
            selectinload(Content.prompts).options(
                selectinload(Prompt.quality_metrics)
            )
        )

    @staticmethod
    def optimize_prompts_with_quality(query: Select) -> Select:
        """
        Optimize query for loading prompts with quality metrics.

        Args:
            query: Base SQLAlchemy select query

        Returns:
            Optimized query with eager loading
        """
        return query.options(
            selectinload(Prompt.quality_metrics),
            joinedload(Prompt.content)
        )

    @staticmethod
    def add_common_filters(
        query: Select,
        model_class,
        filters: Dict[str, Any]
    ) -> Select:
        """
        Add common filtering patterns to queries.

        Args:
            query: Base SQLAlchemy select query
            model_class: SQLAlchemy model class
            filters: Dictionary of filter criteria

        Returns:
            Query with applied filters
        """
        for field, value in filters.items():
            if hasattr(model_class, field) and value is not None:
                if isinstance(value, list):
                    query = query.where(getattr(model_class, field).in_(value))
                elif isinstance(value, dict) and 'gte' in value:
                    query = query.where(getattr(model_class, field) >= value['gte'])
                elif isinstance(value, dict) and 'lte' in value:
                    query = query.where(getattr(model_class, field) <= value['lte'])
                else:
                    query = query.where(getattr(model_class, field) == value)

        return query


class QueryCache:
    """
    Simple in-memory query cache for frequently accessed data.
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        """
        Initialize query cache.

        Args:
            max_size: Maximum number of cached items
            ttl_seconds: Time-to-live for cached items in seconds
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Dict[str, Any]] = {}

    def _generate_key(self, query_str: str, params: Dict[str, Any]) -> str:
        """
        Generate cache key from query and parameters.

        Args:
            query_str: SQL query string
            params: Query parameters

        Returns:
            Cache key string
        """
        import hashlib
        cache_data = f"{query_str}:{str(sorted(params.items()))}"
        return hashlib.md5(cache_data.encode()).hexdigest()

    def get(self, query_str: str, params: Dict[str, Any]) -> Optional[Any]:
        """
        Get cached query result.

        Args:
            query_str: SQL query string
            params: Query parameters

        Returns:
            Cached result or None if not found/expired
        """
        key = self._generate_key(query_str, params)
        if key in self._cache:
            cached_item = self._cache[key]
            if time.time() - cached_item['timestamp'] < self.ttl_seconds:
                return cached_item['result']
            else:
                del self._cache[key]
        return None

    def set(self, query_str: str, params: Dict[str, Any], result: Any) -> None:
        """
        Cache query result.

        Args:
            query_str: SQL query string
            params: Query parameters
            result: Query result to cache
        """
        if len(self._cache) >= self.max_size:
            # Remove oldest item
            oldest_key = min(
                self._cache.keys(),
                key=lambda k: self._cache[k]['timestamp']
            )
            del self._cache[oldest_key]

        key = self._generate_key(query_str, params)
        self._cache[key] = {
            'result': result,
            'timestamp': time.time()
        }

    def clear(self) -> None:
        """Clear all cached items."""
        self._cache.clear()

    def size(self) -> int:
        """Get current cache size."""
        return len(self._cache)


# Global cache instance
_query_cache = QueryCache()


def cached_query(ttl_seconds: int = 300):
    """
    Decorator for caching query results.

    Args:
        ttl_seconds: Time-to-live for cached results

    Returns:
        Decorator function
    """
    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            cache_key = f"{func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"

            # Try to get from cache
            cached_result = _query_cache.get(cache_key, {})
            if cached_result is not None:
                return cached_result

            # Execute function and cache result
            result = await func(*args, **kwargs)
            _query_cache.set(cache_key, {}, result)

            return result
        return wrapper
    return decorator


class PerformanceMonitor:
    """
    Performance monitoring for database operations.
    """

    def __init__(self):
        self.query_stats: Dict[str, Dict[str, Any]] = {}

    @asynccontextmanager
    async def monitor_query(self, operation_name: str):
        """
        Context manager for monitoring query performance.

        Args:
            operation_name: Name of the operation being monitored

        Yields:
            Dictionary that will contain performance metrics
        """
        start_time = time.time()
        metrics = {"operation": operation_name}

        try:
            yield metrics
        finally:
            end_time = time.time()
            duration = end_time - start_time

            # Update statistics
            if operation_name not in self.query_stats:
                self.query_stats[operation_name] = {
                    "count": 0,
                    "total_time": 0.0,
                    "avg_time": 0.0,
                    "min_time": float('inf'),
                    "max_time": 0.0
                }

            stats = self.query_stats[operation_name]
            stats["count"] += 1
            stats["total_time"] += duration
            stats["avg_time"] = stats["total_time"] / stats["count"]
            stats["min_time"] = min(stats["min_time"], duration)
            stats["max_time"] = max(stats["max_time"], duration)

            metrics.update({
                "duration_seconds": duration,
                "duration_ms": int(duration * 1000)
            })

    def get_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get performance statistics for all monitored operations.

        Returns:
            Dictionary with performance statistics
        """
        return self.query_stats.copy()

    def reset_stats(self) -> None:
        """Reset all performance statistics."""
        self.query_stats.clear()


# Global performance monitor
_performance_monitor = PerformanceMonitor()


def monitored_query(operation_name: Optional[str] = None):
    """
    Decorator for monitoring query performance.

    Args:
        operation_name: Optional operation name (defaults to function name)

    Returns:
        Decorator function
    """
    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            name = operation_name or func.__name__
            async with _performance_monitor.monitor_query(name) as metrics:
                result = await func(*args, **kwargs)
                return result
        return wrapper
    return decorator


class BatchProcessor:
    """
    Utilities for batch processing database operations.
    """

    @staticmethod
    async def process_in_batches(
        session: AsyncSession,
        items: List[Any],
        batch_size: int,
        process_func: Callable,
        **kwargs
    ) -> List[Any]:
        """
        Process items in batches to avoid memory issues.

        Args:
            session: Database session
            items: List of items to process
            batch_size: Size of each batch
            process_func: Function to process each batch
            **kwargs: Additional arguments for process_func

        Returns:
            List of all processed results
        """
        results = []

        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            batch_results = await process_func(session, batch, **kwargs)
            results.extend(batch_results)

            # Commit each batch
            await session.commit()

        return results

    @staticmethod
    async def bulk_insert_optimized(
        session: AsyncSession,
        model_class,
        data: List[Dict[str, Any]],
        batch_size: int = 1000
    ) -> int:
        """
        Optimized bulk insert using batch processing.

        Args:
            session: Database session
            model_class: SQLAlchemy model class
            data: List of dictionaries with model data
            batch_size: Size of each batch

        Returns:
            Number of records inserted
        """
        total_inserted = 0

        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]

            # Use bulk_insert_mappings for better performance
            await session.execute(
                model_class.__table__.insert(),
                batch
            )

            total_inserted += len(batch)
            await session.commit()

        return total_inserted


class ConnectionPoolOptimizer:
    """
    Utilities for optimizing database connection pool settings.
    """

    @staticmethod
    def get_optimal_pool_settings(
        max_connections: int = 20,
        environment: str = "production"
    ) -> Dict[str, Any]:
        """
        Get optimal connection pool settings based on environment.

        Args:
            max_connections: Maximum number of connections available
            environment: Environment name (development, staging, production)

        Returns:
            Dictionary with optimal pool settings
        """
        if environment == "development":
            return {
                "pool_size": min(5, max_connections // 2),
                "max_overflow": min(10, max_connections // 2),
                "pool_timeout": 30,
                "pool_recycle": 3600,
                "pool_pre_ping": True
            }
        elif environment == "staging":
            return {
                "pool_size": min(10, max_connections // 2),
                "max_overflow": min(15, max_connections // 2),
                "pool_timeout": 20,
                "pool_recycle": 1800,
                "pool_pre_ping": True
            }
        else:  # production
            return {
                "pool_size": min(15, max_connections // 2),
                "max_overflow": min(20, max_connections // 2),
                "pool_timeout": 10,
                "pool_recycle": 900,
                "pool_pre_ping": True
            }

    @staticmethod
    async def test_connection_pool(session: AsyncSession, iterations: int = 10) -> Dict[str, Any]:
        """
        Test connection pool performance.

        Args:
            session: Database session
            iterations: Number of test iterations

        Returns:
            Dictionary with performance metrics
        """
        start_time = time.time()
        successful_connections = 0

        tasks = []
        for _ in range(iterations):
            tasks.append(_test_single_connection(session))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if not isinstance(result, Exception):
                successful_connections += 1

        end_time = time.time()

        return {
            "total_iterations": iterations,
            "successful_connections": successful_connections,
            "failed_connections": iterations - successful_connections,
            "success_rate": successful_connections / iterations,
            "total_time_seconds": end_time - start_time,
            "avg_time_per_connection": (end_time - start_time) / iterations
        }


async def _test_single_connection(session: AsyncSession) -> bool:
    """
    Test a single database connection.

    Args:
        session: Database session

    Returns:
        True if connection successful, False otherwise
    """
    try:
        result = await session.execute(text("SELECT 1"))
        return result.scalar() == 1
    except Exception:
        return False


# Utility functions for accessing global instances
def get_query_cache() -> QueryCache:
    """Get the global query cache instance."""
    return _query_cache


def get_performance_monitor() -> PerformanceMonitor:
    """Get the global performance monitor instance."""
    return _performance_monitor


def clear_all_caches() -> None:
    """Clear all performance caches."""
    _query_cache.clear()
    _performance_monitor.reset_stats()