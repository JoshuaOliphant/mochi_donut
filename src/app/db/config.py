# Database Configuration - SQLAlchemy 2.0 Async
"""
Async SQLAlchemy configuration with connection pooling, session management,
and environment-specific settings for the Mochi Donut application.
"""

import os
from functools import lru_cache
from typing import Optional, AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    async_sessionmaker,
    create_async_engine
)
from sqlalchemy.pool import NullPool, QueuePool
from pydantic import field_validator
from pydantic_settings import BaseSettings


class DatabaseSettings(BaseSettings):
    """
    Database configuration with environment-specific defaults.
    Supports SQLite for development and PostgreSQL for production.
    """

    # Database URL configuration
    database_url: str = "sqlite+aiosqlite:///./mochi_donut.db"
    test_database_url: Optional[str] = "sqlite+aiosqlite:///./test_mochi_donut.db"

    # Connection pool settings
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600  # 1 hour
    pool_pre_ping: bool = True

    # Session settings
    echo_sql: bool = False
    expire_on_commit: bool = False

    # Environment detection
    environment: str = "development"
    testing: bool = False

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Ensure database URL is properly formatted."""
        if not v:
            raise ValueError("Database URL cannot be empty")
        return v

    @field_validator("pool_size")
    @classmethod
    def validate_pool_size(cls, v: int) -> int:
        """Ensure pool size is reasonable."""
        if v < 1:
            raise ValueError("Pool size must be at least 1")
        if v > 100:
            raise ValueError("Pool size should not exceed 100")
        return v

    def get_engine_kwargs(self) -> dict:
        """
        Get engine configuration based on database type and environment.

        Returns:
            Dictionary of engine configuration parameters
        """
        kwargs = {
            "echo": self.echo_sql,
            "future": True,  # Use SQLAlchemy 2.0 style
        }

        if "sqlite" in self.database_url.lower():
            # SQLite-specific configuration
            kwargs.update({
                "poolclass": NullPool,  # SQLite doesn't need pooling
                "connect_args": {
                    "check_same_thread": False,
                    "timeout": 20,
                }
            })
        else:
            # PostgreSQL-specific configuration
            kwargs.update({
                "poolclass": QueuePool,
                "pool_size": self.pool_size,
                "max_overflow": self.max_overflow,
                "pool_timeout": self.pool_timeout,
                "pool_recycle": self.pool_recycle,
                "pool_pre_ping": self.pool_pre_ping,
            })

        return kwargs

    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
    }


# Global database settings instance
@lru_cache()
def get_database_settings() -> DatabaseSettings:
    """Get cached database settings instance."""
    return DatabaseSettings()


class DatabaseManager:
    """
    Database manager for async SQLAlchemy operations.
    Handles engine creation, session management, and connection lifecycle.
    """

    def __init__(self, settings: Optional[DatabaseSettings] = None):
        """
        Initialize database manager with settings.

        Args:
            settings: Optional database settings (defaults to global settings)
        """
        self.settings = settings or get_database_settings()
        self._engine: Optional[AsyncEngine] = None
        self._session_maker: Optional[async_sessionmaker] = None

    @property
    def engine(self) -> AsyncEngine:
        """
        Get or create the async database engine.

        Returns:
            Configured async SQLAlchemy engine
        """
        if self._engine is None:
            database_url = self.settings.database_url
            if self.settings.testing and self.settings.test_database_url:
                database_url = self.settings.test_database_url

            engine_kwargs = self.settings.get_engine_kwargs()
            self._engine = create_async_engine(database_url, **engine_kwargs)

        return self._engine

    @property
    def session_maker(self) -> async_sessionmaker:
        """
        Get or create the async session maker.

        Returns:
            Configured async session maker
        """
        if self._session_maker is None:
            self._session_maker = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=self.settings.expire_on_commit,
                autoflush=True,
                autocommit=False,
            )

        return self._session_maker

    async def create_all_tables(self) -> None:
        """
        Create all database tables.
        Should only be used in development or for testing.
        """
        from app.db.models import Base

        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def drop_all_tables(self) -> None:
        """
        Drop all database tables.
        Should only be used in testing.
        """
        if not self.settings.testing:
            raise RuntimeError("Can only drop tables in testing mode")

        from app.db.models import Base

        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    async def get_session(self) -> AsyncSession:
        """
        Get a new database session.

        Returns:
            New async database session
        """
        return self.session_maker()

    async def close(self) -> None:
        """
        Close the database engine and all connections.
        """
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_maker = None

    async def health_check(self) -> bool:
        """
        Perform a database health check.

        Returns:
            True if database is accessible, False otherwise
        """
        try:
            from sqlalchemy import text
            async with self.session_maker() as session:
                result = await session.execute(text("SELECT 1"))
                return result.scalar() == 1
        except Exception:
            return False


# Global database manager instance
_database_manager: Optional[DatabaseManager] = None


def get_database_manager() -> DatabaseManager:
    """
    Get or create the global database manager instance.

    Returns:
        Global database manager
    """
    global _database_manager
    if _database_manager is None:
        _database_manager = DatabaseManager()
    return _database_manager


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for getting async database sessions.

    Yields:
        Async database session with automatic cleanup
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


# Utility functions for testing
async def init_test_database() -> DatabaseManager:
    """
    Initialize a test database with clean tables.

    Returns:
        Database manager configured for testing
    """
    settings = get_database_settings()
    settings.testing = True

    db_manager = DatabaseManager(settings)
    await db_manager.drop_all_tables()
    await db_manager.create_all_tables()

    return db_manager


async def cleanup_test_database(db_manager: DatabaseManager) -> None:
    """
    Clean up test database and close connections.

    Args:
        db_manager: Database manager to clean up
    """
    await db_manager.drop_all_tables()
    await db_manager.close()


# Repository factory for dependency injection
def get_content_repository(session: AsyncSession) -> "ContentRepository":
    """
    Factory function for ContentRepository.

    Args:
        session: Async database session

    Returns:
        Configured ContentRepository instance
    """
    from app.repositories.content import ContentRepository
    return ContentRepository(session)


def get_prompt_repository(session: AsyncSession) -> "PromptRepository":
    """
    Factory function for PromptRepository.

    Args:
        session: Async database session

    Returns:
        Configured PromptRepository instance
    """
    from app.repositories.prompt import PromptRepository
    return PromptRepository(session)


def get_quality_metric_repository(session: AsyncSession) -> "BaseRepository":
    """
    Factory function for QualityMetric repository.

    Args:
        session: Async database session

    Returns:
        Configured BaseRepository for QualityMetric
    """
    from app.repositories.base import BaseRepository
    from app.db.models import QualityMetric
    return BaseRepository(QualityMetric, session)


def get_agent_execution_repository(session: AsyncSession) -> "BaseRepository":
    """
    Factory function for AgentExecution repository.

    Args:
        session: Async database session

    Returns:
        Configured BaseRepository for AgentExecution
    """
    from app.repositories.base import BaseRepository
    from app.db.models import AgentExecution
    return BaseRepository(AgentExecution, session)