# Repository Package - Centralized Repository Access
"""
Repository package initialization with factory functions and dependency
injection setup for FastAPI integration.
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import BaseRepository
from app.repositories.content import ContentRepository
from app.repositories.prompt import PromptRepository
from app.db.models import QualityMetric, AgentExecution, UserInteraction, ProcessingQueue


class RepositoryFactory:
    """
    Factory class for creating repository instances with dependency injection.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize factory with database session.

        Args:
            session: Async database session
        """
        self.session = session
        self._repositories = {}

    def get_content_repository(self) -> ContentRepository:
        """
        Get or create ContentRepository instance.

        Returns:
            ContentRepository instance
        """
        if "content" not in self._repositories:
            self._repositories["content"] = ContentRepository(self.session)
        return self._repositories["content"]

    def get_prompt_repository(self) -> PromptRepository:
        """
        Get or create PromptRepository instance.

        Returns:
            PromptRepository instance
        """
        if "prompt" not in self._repositories:
            self._repositories["prompt"] = PromptRepository(self.session)
        return self._repositories["prompt"]

    def get_quality_metric_repository(self) -> BaseRepository:
        """
        Get or create QualityMetric repository instance.

        Returns:
            BaseRepository for QualityMetric
        """
        if "quality_metric" not in self._repositories:
            self._repositories["quality_metric"] = BaseRepository(
                QualityMetric, self.session
            )
        return self._repositories["quality_metric"]

    def get_agent_execution_repository(self) -> BaseRepository:
        """
        Get or create AgentExecution repository instance.

        Returns:
            BaseRepository for AgentExecution
        """
        if "agent_execution" not in self._repositories:
            self._repositories["agent_execution"] = BaseRepository(
                AgentExecution, self.session
            )
        return self._repositories["agent_execution"]

    def get_user_interaction_repository(self) -> BaseRepository:
        """
        Get or create UserInteraction repository instance.

        Returns:
            BaseRepository for UserInteraction
        """
        if "user_interaction" not in self._repositories:
            self._repositories["user_interaction"] = BaseRepository(
                UserInteraction, self.session
            )
        return self._repositories["user_interaction"]

    def get_processing_queue_repository(self) -> BaseRepository:
        """
        Get or create ProcessingQueue repository instance.

        Returns:
            BaseRepository for ProcessingQueue
        """
        if "processing_queue" not in self._repositories:
            self._repositories["processing_queue"] = BaseRepository(
                ProcessingQueue, self.session
            )
        return self._repositories["processing_queue"]


# FastAPI dependency functions
async def get_repository_factory(
    session: AsyncSession,
) -> RepositoryFactory:
    """
    FastAPI dependency for repository factory.

    Args:
        session: Async database session (injected dependency)

    Returns:
        Repository factory instance
    """
    return RepositoryFactory(session)


async def get_content_repository(
    factory: RepositoryFactory,
) -> ContentRepository:
    """
    FastAPI dependency for ContentRepository.

    Args:
        factory: Repository factory (injected dependency)

    Returns:
        ContentRepository instance
    """
    return factory.get_content_repository()


async def get_prompt_repository(
    factory: RepositoryFactory,
) -> PromptRepository:
    """
    FastAPI dependency for PromptRepository.

    Args:
        factory: Repository factory (injected dependency)

    Returns:
        PromptRepository instance
    """
    return factory.get_prompt_repository()


async def get_quality_metric_repository(
    factory: RepositoryFactory,
) -> BaseRepository:
    """
    FastAPI dependency for QualityMetric repository.

    Args:
        factory: Repository factory (injected dependency)

    Returns:
        BaseRepository for QualityMetric
    """
    return factory.get_quality_metric_repository()


async def get_agent_execution_repository(
    factory: RepositoryFactory,
) -> BaseRepository:
    """
    FastAPI dependency for AgentExecution repository.

    Args:
        factory: Repository factory (injected dependency)

    Returns:
        BaseRepository for AgentExecution
    """
    return factory.get_agent_execution_repository()


async def get_user_interaction_repository(
    factory: RepositoryFactory,
) -> BaseRepository:
    """
    FastAPI dependency for UserInteraction repository.

    Args:
        factory: Repository factory (injected dependency)

    Returns:
        BaseRepository for UserInteraction
    """
    return factory.get_user_interaction_repository()


async def get_processing_queue_repository(
    factory: RepositoryFactory,
) -> BaseRepository:
    """
    FastAPI dependency for ProcessingQueue repository.

    Args:
        factory: Repository factory (injected dependency)

    Returns:
        BaseRepository for ProcessingQueue
    """
    return factory.get_processing_queue_repository()


# Export commonly used repositories and factory
__all__ = [
    "RepositoryFactory",
    "get_repository_factory",
    "get_content_repository",
    "get_prompt_repository",
    "get_quality_metric_repository",
    "get_agent_execution_repository",
    "get_user_interaction_repository",
    "get_processing_queue_repository",
    "ContentRepository",
    "PromptRepository",
    "BaseRepository",
]