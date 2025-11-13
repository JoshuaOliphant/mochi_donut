from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool, QueuePool
from app.core.config import settings


class DatabaseConfig:
    def __init__(self):
        # Configure connection pool based on environment
        pool_config = {}
        if settings.is_development:
            # SQLite doesn't support connection pooling well
            if "sqlite" in settings.DATABASE_URL:
                pool_config = {
                    "poolclass": NullPool,
                }
            else:
                pool_config = {
                    "pool_size": 5,
                    "max_overflow": 10,
                }
        else:
            # Production configuration for async engines
            pool_config = {
                "pool_size": 20,
                "max_overflow": 40,
                "pool_timeout": 30,
                "pool_recycle": 1800,  # 30 minutes
            }

        # Create async engine
        self.engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.is_development and settings.LOG_LEVEL == "DEBUG",
            **pool_config
        )

        # Create session factory
        self.async_session = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False
        )

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get a database session for dependency injection.
        """
        async with self.async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def init_db(self):
        """
        Initialize the database (create tables if they don't exist).
        This is primarily for development. Production should use migrations.
        """
        from app.db.models import Base
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def close(self):
        """
        Close all database connections.
        """
        await self.engine.dispose()

    async def health_check(self) -> bool:
        """
        Check if database is accessible.
        """
        try:
            async with self.async_session() as session:
                await session.execute("SELECT 1")
                return True
        except Exception:
            return False


# Global database instance
db = DatabaseConfig()


# Dependency for FastAPI
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in db.get_session():
        yield session