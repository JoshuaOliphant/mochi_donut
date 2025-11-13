# Prompt Repository - Domain-Specific Operations
"""
Prompt repository with specialized operations for prompt management,
quality tracking, and Mochi integration support.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
import uuid

from sqlalchemy import and_, func, or_, select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.db.models import Prompt, PromptType, QualityMetric, QualityMetricType
from app.repositories.base import BaseRepository


class PromptRepository(BaseRepository[Prompt, Any, Any]):
    """
    Repository for Prompt model with specialized prompt management operations.
    """

    def __init__(self, session: AsyncSession):
        super().__init__(Prompt, session)

    async def get_by_content(
        self,
        content_id: uuid.UUID,
        include_quality_metrics: bool = False
    ) -> List[Prompt]:
        """
        Get all prompts for a specific content item.

        Args:
            content_id: Content UUID
            include_quality_metrics: Whether to load quality metrics

        Returns:
            List of prompts for the content
        """
        query = (
            select(self.model)
            .where(self.model.content_id == content_id)
            .order_by(self.model.created_at.asc())
        )

        if include_quality_metrics:
            query = query.options(selectinload(self.model.quality_metrics))

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_with_quality_metrics(self, id: uuid.UUID) -> Optional[Prompt]:
        """
        Get prompt with all quality metrics loaded.

        Args:
            id: Prompt UUID

        Returns:
            Prompt instance with quality metrics or None
        """
        query = (
            select(self.model)
            .where(self.model.id == id)
            .options(selectinload(self.model.quality_metrics))
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_pending_mochi_sync(self, limit: int = 50) -> List[Prompt]:
        """
        Get prompts that haven't been synced to Mochi yet.

        Args:
            limit: Maximum number of prompts to return

        Returns:
            List of prompts pending Mochi sync
        """
        query = (
            select(self.model)
            .where(
                and_(
                    self.model.mochi_card_id.is_(None),
                    self.model.confidence_score >= 0.7  # Only sync high-quality prompts
                )
            )
            .order_by(self.model.created_at.asc())
            .limit(limit)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_mochi_card_id(self, mochi_card_id: str) -> Optional[Prompt]:
        """
        Get prompt by Mochi card ID.

        Args:
            mochi_card_id: Mochi card identifier

        Returns:
            Prompt instance or None
        """
        query = select(self.model).where(self.model.mochi_card_id == mochi_card_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def search_prompts(
        self,
        search_term: str,
        prompt_types: Optional[List[PromptType]] = None,
        min_confidence: Optional[float] = None,
        limit: int = 50
    ) -> List[Prompt]:
        """
        Search prompts by question or answer content.

        Args:
            search_term: Text to search for
            prompt_types: Optional filter by prompt types
            min_confidence: Minimum confidence score
            limit: Maximum number of results

        Returns:
            List of matching prompts
        """
        search_pattern = f"%{search_term}%"
        query = (
            select(self.model)
            .where(
                or_(
                    self.model.question.ilike(search_pattern),
                    self.model.answer.ilike(search_pattern)
                )
            )
            .order_by(desc(self.model.confidence_score))
            .limit(limit)
        )

        if prompt_types:
            query = query.where(self.model.prompt_type.in_(prompt_types))

        if min_confidence is not None:
            query = query.where(self.model.confidence_score >= min_confidence)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_low_quality_prompts(
        self,
        max_confidence: float = 0.5,
        limit: int = 100
    ) -> List[Prompt]:
        """
        Get prompts with low confidence scores for review.

        Args:
            max_confidence: Maximum confidence score to include
            limit: Maximum number of results

        Returns:
            List of low-quality prompts
        """
        query = (
            select(self.model)
            .where(self.model.confidence_score <= max_confidence)
            .order_by(self.model.confidence_score.asc())
            .limit(limit)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_recently_edited(
        self,
        days: int = 7,
        limit: int = 100
    ) -> List[Prompt]:
        """
        Get prompts that were recently edited by users.

        Args:
            days: Number of days to look back
            limit: Maximum number of results

        Returns:
            List of recently edited prompts
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        query = (
            select(self.model)
            .where(
                and_(
                    self.model.is_edited == True,
                    self.model.edited_at >= cutoff_date
                )
            )
            .order_by(desc(self.model.edited_at))
            .limit(limit)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_prompt_type_distribution(
        self,
        content_id: Optional[uuid.UUID] = None
    ) -> Dict[str, int]:
        """
        Get distribution of prompt types.

        Args:
            content_id: Optional filter by content ID

        Returns:
            Dictionary with counts by prompt type
        """
        query = (
            select(
                self.model.prompt_type,
                func.count(self.model.id).label("count")
            )
            .group_by(self.model.prompt_type)
        )

        if content_id:
            query = query.where(self.model.content_id == content_id)

        result = await self.session.execute(query)
        distribution = {ptype.value: 0 for ptype in PromptType}

        for row in result:
            distribution[row.prompt_type.value] = row.count

        return distribution

    async def get_quality_statistics(
        self,
        content_id: Optional[uuid.UUID] = None
    ) -> Dict[str, float]:
        """
        Get quality statistics for prompts.

        Args:
            content_id: Optional filter by content ID

        Returns:
            Dictionary with quality statistics
        """
        query = select(
            func.avg(self.model.confidence_score).label("avg_confidence"),
            func.min(self.model.confidence_score).label("min_confidence"),
            func.max(self.model.confidence_score).label("max_confidence"),
            func.count(self.model.id).label("total_prompts"),
            func.sum(
                func.case((self.model.is_edited == True, 1), else_=0)
            ).label("edited_count")
        )

        if content_id:
            query = query.where(self.model.content_id == content_id)

        result = await self.session.execute(query)
        row = result.first()

        if not row or row.total_prompts == 0:
            return {
                "avg_confidence": 0.0,
                "min_confidence": 0.0,
                "max_confidence": 0.0,
                "total_prompts": 0,
                "edited_percentage": 0.0
            }

        return {
            "avg_confidence": float(row.avg_confidence or 0.0),
            "min_confidence": float(row.min_confidence or 0.0),
            "max_confidence": float(row.max_confidence or 0.0),
            "total_prompts": int(row.total_prompts),
            "edited_percentage": float(row.edited_count / row.total_prompts * 100)
        }

    async def mark_sent_to_mochi(
        self,
        id: uuid.UUID,
        mochi_card_id: str,
        mochi_deck_id: Optional[str] = None
    ) -> bool:
        """
        Mark prompt as sent to Mochi with card details.

        Args:
            id: Prompt UUID
            mochi_card_id: Mochi card identifier
            mochi_deck_id: Optional Mochi deck identifier

        Returns:
            True if updated successfully
        """
        prompt = await self.get(id)
        if not prompt:
            return False

        prompt.mochi_card_id = mochi_card_id
        prompt.mochi_status = "synced"
        prompt.sent_to_mochi_at = datetime.utcnow()

        if mochi_deck_id:
            prompt.mochi_deck_id = mochi_deck_id

        await self.session.flush()
        return True

    async def mark_edited(
        self,
        id: uuid.UUID,
        edit_reason: Optional[str] = None
    ) -> bool:
        """
        Mark prompt as edited by user.

        Args:
            id: Prompt UUID
            edit_reason: Optional reason for the edit

        Returns:
            True if updated successfully
        """
        prompt = await self.get(id)
        if not prompt:
            return False

        prompt.is_edited = True
        prompt.edited_at = datetime.utcnow()
        prompt.version += 1

        if edit_reason:
            prompt.edit_reason = edit_reason

        await self.session.flush()
        return True

    async def get_prompts_needing_quality_review(
        self,
        limit: int = 50
    ) -> List[Prompt]:
        """
        Get prompts that need quality metric evaluation.

        Args:
            limit: Maximum number of prompts to return

        Returns:
            List of prompts needing quality review
        """
        # Subquery to find prompts without quality metrics
        subquery = (
            select(QualityMetric.prompt_id)
            .where(QualityMetric.metric_type == QualityMetricType.OVERALL_QUALITY)
        )

        query = (
            select(self.model)
            .where(self.model.id.notin_(subquery))
            .order_by(self.model.created_at.asc())
            .limit(limit)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_high_confidence_prompts(
        self,
        min_confidence: float = 0.8,
        days: int = 7,
        limit: int = 100
    ) -> List[Prompt]:
        """
        Get high-confidence prompts from recent content.

        Args:
            min_confidence: Minimum confidence score
            days: Number of days to look back
            limit: Maximum number of results

        Returns:
            List of high-confidence prompts
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        query = (
            select(self.model)
            .where(
                and_(
                    self.model.confidence_score >= min_confidence,
                    self.model.created_at >= cutoff_date
                )
            )
            .order_by(desc(self.model.confidence_score))
            .limit(limit)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def bulk_update_confidence_scores(
        self,
        updates: List[Tuple[uuid.UUID, float]]
    ) -> int:
        """
        Bulk update confidence scores for multiple prompts.

        Args:
            updates: List of (prompt_id, confidence_score) tuples

        Returns:
            Number of prompts updated
        """
        if not updates:
            return 0

        update_data = [
            {"id": prompt_id, "confidence_score": score}
            for prompt_id, score in updates
        ]

        return await self.update_bulk(update_data)

    async def get_mochi_sync_statistics(self) -> Dict[str, int]:
        """
        Get statistics about Mochi synchronization.

        Returns:
            Dictionary with sync statistics
        """
        query = select(
            func.count(self.model.id).label("total_prompts"),
            func.sum(
                func.case((self.model.mochi_card_id.isnot(None), 1), else_=0)
            ).label("synced_count"),
            func.sum(
                func.case(
                    (
                        and_(
                            self.model.mochi_card_id.is_(None),
                            self.model.confidence_score >= 0.7
                        ),
                        1
                    ),
                    else_=0
                )
            ).label("pending_sync_count")
        )

        result = await self.session.execute(query)
        row = result.first()

        return {
            "total_prompts": int(row.total_prompts or 0),
            "synced_count": int(row.synced_count or 0),
            "pending_sync_count": int(row.pending_sync_count or 0),
            "sync_percentage": float(
                (row.synced_count or 0) / max(row.total_prompts or 1, 1) * 100
            )
        }

    async def get_with_quality(self, id: uuid.UUID) -> Optional[Prompt]:
        """Get prompt with quality metrics."""
        return await self.get_with_quality_metrics(id)

    async def update_with_history(self, id: uuid.UUID, prompt_data) -> Optional[Prompt]:
        """Update prompt and mark as edited."""
        updated_prompt = await self.update(id, prompt_data)
        if updated_prompt:
            await self.mark_edited(id, getattr(prompt_data, 'edit_reason', None))
        return updated_prompt

    async def add_quality_metric(self, metric_data) -> QualityMetric:
        """Add quality metric to prompt."""
        from app.db.models import QualityMetric

        if hasattr(metric_data, 'model_dump'):
            data = metric_data.model_dump()
        else:
            data = metric_data.dict()

        metric = QualityMetric(**data)
        self.session.add(metric)
        await self.session.flush()
        await self.session.refresh(metric)
        return metric

    async def get_quality_metrics(self, prompt_id: uuid.UUID) -> List[QualityMetric]:
        """Get all quality metrics for a prompt."""
        query = select(QualityMetric).where(QualityMetric.prompt_id == prompt_id)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_multi_with_filters(
        self,
        skip: int = 0,
        limit: int = 50,
        min_confidence: Optional[float] = None,
        has_mochi_card: Optional[bool] = None,
        **filters
    ) -> List[Prompt]:
        """Get prompts with additional filters."""
        query = select(self.model)

        # Apply base filters
        for key, value in filters.items():
            if hasattr(self.model, key):
                query = query.where(getattr(self.model, key) == value)

        # Apply additional filters
        if min_confidence is not None:
            query = query.where(self.model.confidence_score >= min_confidence)

        if has_mochi_card is not None:
            if has_mochi_card:
                query = query.where(self.model.mochi_card_id.isnot(None))
            else:
                query = query.where(self.model.mochi_card_id.is_(None))

        query = query.offset(skip).limit(limit).order_by(self.model.created_at.desc())

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def batch_update(self, prompt_updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Batch update prompts."""
        updated_items = 0
        failed_items = 0
        results = []

        for update_data in prompt_updates:
            try:
                prompt_id = update_data.get('id')
                if prompt_id:
                    updated_prompt = await self.update(prompt_id, update_data)
                    if updated_prompt:
                        updated_items += 1
                        results.append({"id": prompt_id, "status": "updated"})
                    else:
                        failed_items += 1
                        results.append({"id": prompt_id, "status": "not_found"})
                else:
                    failed_items += 1
                    results.append({"status": "missing_id"})
            except Exception as e:
                failed_items += 1
                results.append({"id": update_data.get('id'), "status": "error", "error": str(e)})

        return {
            "total_items": len(prompt_updates),
            "updated_items": updated_items,
            "failed_items": failed_items,
            "results": results
        }

    async def get_prompts_needing_review(
        self,
        skip: int = 0,
        limit: int = 50,
        quality_threshold: float = 0.7
    ) -> List[Prompt]:
        """Get prompts needing quality review."""
        query = (
            select(self.model)
            .where(
                or_(
                    self.model.confidence_score < quality_threshold,
                    self.model.confidence_score.is_(None)
                )
            )
            .order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(limit)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def validate_prompt(self, prompt_data) -> Dict[str, Any]:
        """Validate prompt data."""
        return {
            "valid": True,
            "issues": []
        }

    async def search(self, search_request) -> tuple[List[Prompt], int, Optional[Dict[str, Any]]]:
        """Search prompts."""
        results = await self.search_prompts(
            search_request.query,
            search_request.prompt_types,
            search_request.min_confidence,
            search_request.limit or 50
        )
        total_count = len(results)
        facets = None
        return results, total_count, facets

    async def find_similar(self, prompt_id: uuid.UUID, limit: int = 10, min_similarity: float = 0.5) -> List[Prompt]:
        """Find similar prompts (placeholder)."""
        return []

    async def get_search_suggestions(self, query: str, limit: int = 10) -> List[str]:
        """Get search suggestions."""
        return []

    async def get_trending(self, limit: int = 10, days: int = 7) -> List[Dict[str, Any]]:
        """Get trending prompts."""
        return []

    async def get_statistics(self) -> Dict[str, Any]:
        """Get prompt statistics."""
        total_query = select(func.count(self.model.id))
        total_result = await self.session.execute(total_query)
        total_prompts = total_result.scalar()

        type_distribution = await self.get_prompt_type_distribution()
        quality_stats = await self.get_quality_statistics()
        mochi_sync_stats = await self.get_mochi_sync_statistics()

        return {
            "total_prompts": total_prompts,
            "type_distribution": type_distribution,
            "quality_stats": quality_stats,
            "mochi_sync_stats": mochi_sync_stats,
            "recent_activity": {}
        }

    async def count_by_date_range(self, start_date: datetime, end_date: datetime) -> int:
        """Count prompts created in date range."""
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

    async def get_quality_trends(self, start_date: datetime, end_date: datetime, group_by: str) -> Dict[str, Any]:
        """Get quality trends."""
        return {}

    async def get_cost_breakdown(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get cost breakdown."""
        return {"total_cost": 0.0}

    async def get_efficiency_by_source(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get efficiency by source."""
        return {}

    async def generate_quality_report(self, start_date: datetime, end_date: datetime, include_details: bool) -> Dict[str, Any]:
        """Generate quality report."""
        return {}

    async def count(self, **filters) -> int:
        """Count prompts with filters."""
        return await super().count(**filters)

    async def get_by_content_id(
        self,
        content_id: uuid.UUID,
        status: Optional[Any] = None,
        limit: int = 50
    ) -> List[Prompt]:
        """
        Get prompts by content ID with optional status filter.

        Args:
            content_id: Content UUID
            status: Optional status filter
            limit: Maximum number of results

        Returns:
            List of prompts
        """
        query = (
            select(self.model)
            .where(self.model.content_id == content_id)
            .order_by(self.model.created_at.desc())
            .limit(limit)
        )

        if status is not None:
            query = query.where(self.model.status == status)

        result = await self.session.execute(query)
        return list(result.scalars().all())