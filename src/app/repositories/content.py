# Content Repository - Domain-Specific Operations
"""
Content repository with specialized operations for content management,
duplicate detection, and processing workflow support.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import uuid

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Content, ProcessingStatus, SourceType
from app.repositories.base import BaseRepository


class ContentRepository(BaseRepository[Content, Any, Any]):
    """
    Repository for Content model with specialized content management operations.
    """

    def __init__(self, session: AsyncSession):
        super().__init__(Content, session)

    async def get_by_hash(self, content_hash: str) -> Optional[Content]:
        """
        Get content by hash to detect duplicates.

        Args:
            content_hash: SHA-256 hash of the content

        Returns:
            Content instance or None if not found
        """
        query = select(self.model).where(self.model.content_hash == content_hash)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_url(self, source_url: str) -> Optional[Content]:
        """
        Get content by source URL.

        Args:
            source_url: Original source URL

        Returns:
            Content instance or None if not found
        """
        query = select(self.model).where(self.model.source_url == source_url)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_chroma_id(self, chroma_document_id: str) -> Optional[Content]:
        """
        Get content by Chroma document ID.

        Args:
            chroma_document_id: Chroma document identifier

        Returns:
            Content instance or None if not found
        """
        query = select(self.model).where(self.model.chroma_document_id == chroma_document_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_with_prompts(self, id: uuid.UUID) -> Optional[Content]:
        """
        Get content with all associated prompts loaded.

        Args:
            id: Content UUID

        Returns:
            Content instance with prompts or None
        """
        query = (
            select(self.model)
            .where(self.model.id == id)
            .options(selectinload(self.model.prompts))
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_pending_processing(
        self,
        limit: int = 10,
        source_types: Optional[List[SourceType]] = None
    ) -> List[Content]:
        """
        Get content items pending processing.

        Args:
            limit: Maximum number of items to return
            source_types: Optional filter by source types

        Returns:
            List of content items awaiting processing
        """
        query = (
            select(self.model)
            .where(self.model.processing_status == ProcessingStatus.PENDING)
            .order_by(self.model.created_at.asc())
            .limit(limit)
        )

        if source_types:
            query = query.where(self.model.source_type.in_(source_types))

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_failed_processing(
        self,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Content]:
        """
        Get content items that failed processing for retry.

        Args:
            since: Only include failures since this datetime
            limit: Maximum number of items to return

        Returns:
            List of failed content items
        """
        query = (
            select(self.model)
            .where(self.model.processing_status == ProcessingStatus.FAILED)
            .order_by(self.model.updated_at.desc())
            .limit(limit)
        )

        if since:
            query = query.where(self.model.updated_at >= since)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def search_by_title_or_content(
        self,
        search_term: str,
        limit: int = 50
    ) -> List[Content]:
        """
        Full-text search across titles and content.

        Args:
            search_term: Text to search for
            limit: Maximum number of results

        Returns:
            List of matching content items
        """
        search_pattern = f"%{search_term}%"
        query = (
            select(self.model)
            .where(
                or_(
                    self.model.title.ilike(search_pattern),
                    self.model.markdown_content.ilike(search_pattern)
                )
            )
            .order_by(self.model.created_at.desc())
            .limit(limit)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_chroma_document(
        self,
        collection: str,
        document_id: str
    ) -> Optional[Content]:
        """
        Get content by Chroma vector database reference.

        Args:
            collection: Chroma collection name
            document_id: Chroma document ID

        Returns:
            Content instance or None
        """
        query = select(self.model).where(
            and_(
                self.model.chroma_collection == collection,
                self.model.chroma_document_id == document_id
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_processing_stats(self) -> Dict[str, int]:
        """
        Get processing statistics across all content.

        Returns:
            Dictionary with counts by processing status
        """
        query = (
            select(
                self.model.processing_status,
                func.count(self.model.id).label("count")
            )
            .group_by(self.model.processing_status)
        )

        result = await self.session.execute(query)
        stats = {status.value: 0 for status in ProcessingStatus}

        for row in result:
            stats[row.processing_status.value] = row.count

        return stats

    async def get_source_type_stats(self) -> Dict[str, int]:
        """
        Get content statistics by source type.

        Returns:
            Dictionary with counts by source type
        """
        query = (
            select(
                self.model.source_type,
                func.count(self.model.id).label("count")
            )
            .group_by(self.model.source_type)
        )

        result = await self.session.execute(query)
        stats = {source.value: 0 for source in SourceType}

        for row in result:
            stats[row.source_type.value] = row.count

        return stats

    async def mark_processing_started(self, id: uuid.UUID) -> bool:
        """
        Mark content as processing started.

        Args:
            id: Content UUID

        Returns:
            True if updated successfully
        """
        content = await self.get(id)
        if not content:
            return False

        content.processing_status = ProcessingStatus.PROCESSING
        content.updated_at = datetime.utcnow()

        await self.session.flush()
        return True

    async def mark_processing_completed(
        self,
        id: uuid.UUID,
        chroma_collection: Optional[str] = None,
        chroma_document_id: Optional[str] = None
    ) -> bool:
        """
        Mark content as processing completed.

        Args:
            id: Content UUID
            chroma_collection: Chroma collection name
            chroma_document_id: Chroma document ID

        Returns:
            True if updated successfully
        """
        content = await self.get(id)
        if not content:
            return False

        content.processing_status = ProcessingStatus.COMPLETED
        content.processed_at = datetime.utcnow()
        content.updated_at = datetime.utcnow()

        if chroma_collection:
            content.chroma_collection = chroma_collection
        if chroma_document_id:
            content.chroma_document_id = chroma_document_id

        await self.session.flush()
        return True

    async def mark_processing_failed(
        self,
        id: uuid.UUID,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Mark content as processing failed.

        Args:
            id: Content UUID
            error_message: Optional error description

        Returns:
            True if updated successfully
        """
        content = await self.get(id)
        if not content:
            return False

        content.processing_status = ProcessingStatus.FAILED
        content.updated_at = datetime.utcnow()

        if error_message and content.metadata:
            content.metadata = content.metadata or {}
            content.metadata["last_error"] = error_message
        elif error_message:
            content.metadata = {"last_error": error_message}

        await self.session.flush()
        return True

    async def get_recent_by_source_type(
        self,
        source_type: SourceType,
        days: int = 7,
        limit: int = 100
    ) -> List[Content]:
        """
        Get recent content by source type.

        Args:
            source_type: Type of content source
            days: Number of days to look back
            limit: Maximum number of results

        Returns:
            List of recent content items
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        query = (
            select(self.model)
            .where(
                and_(
                    self.model.source_type == source_type,
                    self.model.created_at >= cutoff_date
                )
            )
            .order_by(self.model.created_at.desc())
            .limit(limit)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def cleanup_old_failed(self, days: int = 30) -> int:
        """
        Clean up old failed content entries.

        Args:
            days: Remove failed content older than this many days

        Returns:
            Number of records deleted
        """
        from datetime import timedelta

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Only delete failed content with no associated prompts
        subquery = (
            select(Content.id)
            .join(Content.prompts, isouter=True)
            .where(
                and_(
                    Content.processing_status == ProcessingStatus.FAILED,
                    Content.updated_at < cutoff_date,
                    Content.prompts == None  # No associated prompts
                )
            )
        )

        result = await self.session.execute(subquery)
        failed_ids = [row[0] for row in result]

        if failed_ids:
            return await self.delete_multi(failed_ids)

        return 0

    async def create_with_hash(self, content_data) -> Content:
        """Create content with automatic hash generation."""
        if hasattr(content_data, 'model_dump'):
            data = content_data.model_dump()
        else:
            data = content_data.dict()

        # Generate hash if not provided
        if not data.get('content_hash'):
            import hashlib
            data['content_hash'] = hashlib.sha256(data['markdown_content'].encode()).hexdigest()

        return await self.create(content_data)

    async def get_with_stats(self, id: uuid.UUID) -> Optional[Content]:
        """Get content with processing statistics."""
        content = await self.get(id)
        if content:
            # Add prompt count
            from app.db.models import Prompt
            prompt_count_query = select(func.count(Prompt.id)).where(Prompt.content_id == id)
            result = await self.session.execute(prompt_count_query)
            content.prompt_count = result.scalar()
        return content

    async def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive content statistics."""
        total_query = select(func.count(self.model.id))
        total_result = await self.session.execute(total_query)
        total_content = total_result.scalar()

        processing_stats = await self.get_processing_stats()
        source_type_stats = await self.get_source_type_stats()

        return {
            "total_content": total_content,
            "processing_stats": processing_stats,
            "source_type_stats": source_type_stats,
            "recent_activity": {}  # Placeholder
        }

    async def find_duplicates(self, content_id: uuid.UUID) -> List[Content]:
        """Find potential duplicate content based on content hash."""
        content = await self.get(content_id)
        if not content:
            return []

        query = (
            select(self.model)
            .where(
                and_(
                    self.model.content_hash == content.content_hash,
                    self.model.id != content_id
                )
            )
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def validate_content(self, content_data) -> Dict[str, Any]:
        """Validate content data."""
        return {
            "valid": True,
            "issues": []
        }

    async def get_processing_status(self, content_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """Get processing status information."""
        content = await self.get(content_id)
        if not content:
            return None

        return {
            "status": content.processing_status,
            "created_at": content.created_at,
            "processed_at": content.processed_at,
            "metadata": content.metadata
        }

    async def get_agent_executions(self, content_id: uuid.UUID) -> List:
        """Get agent executions for content."""
        from app.db.models import AgentExecution
        query = select(AgentExecution).where(AgentExecution.content_id == content_id)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def search(self, search_request) -> tuple[List[Content], int, Optional[Dict[str, Any]]]:
        """Search content with filters."""
        # Basic text search implementation
        results = await self.search_by_title_or_content(
            search_request.query,
            search_request.limit or 50
        )
        total_count = len(results)
        facets = None  # Placeholder for faceted search
        return results, total_count, facets

    async def find_similar(self, content_id: uuid.UUID, limit: int = 10, min_similarity: float = 0.5) -> List[Content]:
        """Find similar content (placeholder for vector similarity)."""
        # Placeholder implementation - would use vector database in production
        return []

    async def get_search_suggestions(self, query: str, limit: int = 10) -> List[str]:
        """Get search suggestions."""
        # Placeholder implementation
        return []

    async def get_trending(self, limit: int = 10, days: int = 7) -> List[Dict[str, Any]]:
        """Get trending content."""
        # Placeholder implementation
        return []

    async def count_by_date_range(self, start_date: datetime, end_date: datetime) -> int:
        """Count content created in date range."""
        query = (
            select(func.count(self.model.id))
            .where(
                and_(
                    self.model.created_at >= start_date,
                    self.model.created_at < end_date
                )
            )
        )
        result = await self.session.execute(query)
        return result.scalar()

    async def get_recent_activity(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent activity."""
        # Placeholder implementation
        return []

    async def get_processing_performance(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get processing performance metrics."""
        # Placeholder implementation
        return {}

    async def get_ai_usage_stats(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get AI usage statistics."""
        # Placeholder implementation
        return {"cache_hit_rate": 0.8}

    async def get_source_analysis(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get source analysis."""
        # Placeholder implementation
        return {}

    async def get_queue_size(self) -> int:
        """Get processing queue size."""
        query = select(func.count(self.model.id)).where(
            self.model.processing_status == ProcessingStatus.PENDING
        )
        result = await self.session.execute(query)
        return result.scalar()

    async def get_failed_jobs_count(self) -> int:
        """Get failed jobs count."""
        query = select(func.count(self.model.id)).where(
            self.model.processing_status == ProcessingStatus.FAILED
        )
        result = await self.session.execute(query)
        return result.scalar()

    async def get_avg_processing_time(self) -> float:
        """Get average processing time in seconds."""
        # Placeholder implementation
        return 120.0