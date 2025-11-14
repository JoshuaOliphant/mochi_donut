# Alembic Environment Configuration - Async Support
"""
Alembic environment configuration with async SQLAlchemy 2.0 support.
Handles both offline and online migration modes with proper async patterns.
"""

import asyncio
import os
from logging.config import fileConfig
from typing import Optional

from sqlalchemy import engine_from_config, pool
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.dialects.postgresql import UUID
from alembic import context

# Import your models here to ensure they're registered with metadata
from app.db.models import Base
from app.db.config import get_database_settings

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_database_url() -> str:
    """
    Get database URL from environment or configuration.

    Returns:
        Database URL string
    """
    # Try environment variable first
    url = os.getenv("DATABASE_URL")
    if url:
        return url

    # Fall back to settings
    settings = get_database_settings()
    return settings.database_url


def compare_type(context, inspected_column, metadata_column, inspected_type, metadata_type):
    """
    Custom type comparison to handle SQLite UUID edge cases.

    SQLite stores UUID as TEXT/BLOB/NUMERIC, so we need to suppress false
    positives when comparing UUID types with SQLite's representation.
    """
    # Check if we're using SQLite
    if context.dialect.name == "sqlite":
        # Suppress UUID vs NUMERIC/TEXT/BLOB comparisons
        from sqlalchemy import NUMERIC, TEXT
        if isinstance(metadata_type, UUID) and isinstance(inspected_type, (NUMERIC, TEXT)):
            return False

    # Default comparison
    return None  # None means use default comparison


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well. By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = get_database_url()

    # Remove async driver prefix for offline mode
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://")
    elif url.startswith("sqlite+aiosqlite://"):
        url = url.replace("sqlite+aiosqlite://", "sqlite://")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=compare_type,
        compare_server_default=True,
        render_as_batch=True,  # For SQLite compatibility
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """
    Run migrations with the given connection.

    Args:
        connection: Database connection
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=compare_type,
        compare_server_default=True,
        render_as_batch=True,  # For SQLite compatibility
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Run migrations in async mode.

    Creates an async engine and runs migrations within
    an async context.
    """
    database_url = get_database_url()

    # Create async engine
    connectable = create_async_engine(
        database_url,
        echo=False,
        future=True,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    # Check if we're in async mode
    database_url = get_database_url()

    if any(driver in database_url for driver in ["asyncpg", "aiosqlite"]):
        # Async mode
        asyncio.run(run_async_migrations())
    else:
        # Sync mode fallback
        connectable = engine_from_config(
            config.get_section(config.config_ini_section),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )

        with connectable.connect() as connection:
            do_run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()