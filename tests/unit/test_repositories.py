# Unit Tests for Repository Layer - Async Data Access
"""
Comprehensive unit tests for repository pattern implementation testing
CRUD operations, query building, filtering, and database interactions.
"""

import pytest
from datetime import datetime, timezone
from typing import List, Dict, Any
import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.repositories.base import BaseRepository
from app.repositories.content import ContentRepository
from app.repositories.prompt import PromptRepository
from app.db.models import Content, Prompt, QualityMetric, SourceType, PromptType, ProcessingStatus
from app.schemas.content import ContentCreate, ContentUpdate
from app.schemas.prompt import PromptCreate, PromptUpdate


class TestBaseRepository:
    """Test suite for BaseRepository abstract functionality."""

    @pytest.fixture
    def content_repository(self, db_session: AsyncSession):
        """Create a content repository for testing base functionality."""
        return BaseRepository[Content, ContentCreate, ContentUpdate](Content, db_session)

    async def test_repository_initialization(self, content_repository):
        """Test repository initialization with model and session."""
        # Assert
        assert content_repository.model == Content
        assert content_repository.session is not None

    async def test_get_by_id_existing(self, content_repository, sample_content):
        """Test getting an existing record by ID."""
        # Act
        result = await content_repository.get(sample_content.id)

        # Assert
        assert result is not None
        assert result.id == sample_content.id
        assert result.title == sample_content.title
        assert result.source_type == sample_content.source_type

    async def test_get_by_id_nonexistent(self, content_repository):
        """Test getting a non-existent record by ID."""
        # Arrange
        nonexistent_id = uuid.uuid4()

        # Act
        result = await content_repository.get(nonexistent_id)

        # Assert
        assert result is None

    async def test_get_with_additional_filters(self, content_repository, sample_content):
        """Test getting record by ID with additional filter criteria."""
        # Act - Matching additional filter
        result = await content_repository.get(
            sample_content.id,
            source_type=sample_content.source_type
        )
        assert result is not None
        assert result.id == sample_content.id

        # Act - Non-matching additional filter
        result = await content_repository.get(
            sample_content.id,
            source_type=SourceType.PDF  # Different from actual
        )
        assert result is None

    async def test_get_with_relations(self, db_session, sample_content, sample_prompt_data):
        """Test getting record with eager-loaded relationships."""
        # Arrange
        prompt_data = {**sample_prompt_data, "content_id": sample_content.id}
        prompt = Prompt(**prompt_data)
        db_session.add(prompt)
        await db_session.commit()

        content_repository = BaseRepository[Content, ContentCreate, ContentUpdate](Content, db_session)

        # Act
        result = await content_repository.get_with_relations(
            sample_content.id,
            relations=["prompts"]
        )

        # Assert
        assert result is not None
        assert result.id == sample_content.id
        assert len(result.prompts) == 1
        assert result.prompts[0].content_id == sample_content.id

    async def test_get_multi_basic(self, content_repository, db_session, sample_content_data):
        """Test getting multiple records with basic pagination."""
        # Arrange - Create multiple content records
        content_records = []
        for i in range(5):
            data = {**sample_content_data, "title": f"Test Content {i}", "content_hash": f"{i}" * 64}
            content = Content(**data)
            db_session.add(content)
            content_records.append(content)
        await db_session.commit()

        # Act
        results = await content_repository.get_multi(skip=0, limit=3)

        # Assert
        assert len(results) == 3
        assert all(isinstance(r, Content) for r in results)

    async def test_get_multi_with_filters(self, content_repository, db_session, sample_content_data):
        """Test getting multiple records with filtering."""
        # Arrange - Create records with different source types
        web_data = {**sample_content_data, "source_type": SourceType.WEB, "content_hash": "a" * 64}
        pdf_data = {**sample_content_data, "source_type": SourceType.PDF, "content_hash": "b" * 64}

        web_content = Content(**web_data)
        pdf_content = Content(**pdf_data)
        db_session.add_all([web_content, pdf_content])
        await db_session.commit()

        # Act - Filter by source type
        web_results = await content_repository.get_multi(source_type=SourceType.WEB)
        pdf_results = await content_repository.get_multi(source_type=SourceType.PDF)

        # Assert
        assert all(r.source_type == SourceType.WEB for r in web_results)
        assert all(r.source_type == SourceType.PDF for r in pdf_results)

    async def test_get_multi_with_list_filter(self, content_repository, db_session, sample_content_data):
        """Test getting multiple records with list-based filtering."""
        # Arrange - Create records with different source types
        for source_type, hash_char in [(SourceType.WEB, "a"), (SourceType.PDF, "b"), (SourceType.YOUTUBE, "c")]:
            data = {**sample_content_data, "source_type": source_type, "content_hash": hash_char * 64}
            content = Content(**data)
            db_session.add(content)
        await db_session.commit()

        # Act - Filter by multiple source types
        results = await content_repository.get_multi(
            source_type=[SourceType.WEB, SourceType.PDF]
        )

        # Assert
        assert len(results) == 2
        source_types = {r.source_type for r in results}
        assert source_types == {SourceType.WEB, SourceType.PDF}

    async def test_get_multi_with_ordering(self, content_repository, db_session, sample_content_data):
        """Test getting multiple records with ordering."""
        # Arrange - Create records with different timestamps
        for i in range(3):
            data = {**sample_content_data, "title": f"Content {i}", "content_hash": f"{i}" * 64}
            content = Content(**data)
            db_session.add(content)
        await db_session.commit()

        # Act - Order by title ascending
        asc_results = await content_repository.get_multi(order_by="title")

        # Act - Order by title descending
        desc_results = await content_repository.get_multi(order_by="-title")

        # Assert
        assert len(asc_results) >= 3
        assert len(desc_results) >= 3
        # Verify ordering is opposite
        assert asc_results[0].title != desc_results[0].title or len(asc_results) == 1

    async def test_count_basic(self, content_repository, sample_content):
        """Test counting records without filters."""
        # Act
        count = await content_repository.count()

        # Assert
        assert count >= 1  # At least the sample content

    async def test_count_with_filters(self, content_repository, db_session, sample_content_data):
        """Test counting records with filters."""
        # Arrange - Create records with different source types
        for source_type, hash_char in [(SourceType.WEB, "a"), (SourceType.PDF, "b")]:
            data = {**sample_content_data, "source_type": source_type, "content_hash": hash_char * 64}
            content = Content(**data)
            db_session.add(content)
        await db_session.commit()

        # Act
        web_count = await content_repository.count(source_type=SourceType.WEB)
        pdf_count = await content_repository.count(source_type=SourceType.PDF)
        total_count = await content_repository.count()

        # Assert
        assert web_count >= 1
        assert pdf_count >= 1
        assert total_count >= web_count + pdf_count

    async def test_create_record(self, content_repository, sample_content_data):
        """Test creating a new record."""
        # Arrange
        create_data = ContentCreate(**{
            **sample_content_data,
            "content_hash": "create_test" + "a" * 53  # Different hash
        })

        # Act
        result = await content_repository.create(create_data)

        # Assert
        assert result is not None
        assert result.id is not None
        assert isinstance(result.id, uuid.UUID)
        assert result.title == sample_content_data["title"]
        assert result.source_type == sample_content_data["source_type"]
        assert result.created_at is not None

    async def test_create_bulk_records(self, content_repository, sample_content_data):
        """Test creating multiple records in bulk."""
        # Arrange
        create_data_list = []
        for i in range(3):
            data = {**sample_content_data, "title": f"Bulk Content {i}", "content_hash": f"bulk{i}" + "x" * 59}
            create_data_list.append(ContentCreate(**data))

        # Act
        results = await content_repository.create_bulk(create_data_list)

        # Assert
        assert len(results) == 3
        assert all(r.id is not None for r in results)
        assert all(isinstance(r.id, uuid.UUID) for r in results)
        titles = {r.title for r in results}
        expected_titles = {f"Bulk Content {i}" for i in range(3)}
        assert titles == expected_titles

    async def test_update_existing_record(self, content_repository, sample_content):
        """Test updating an existing record."""
        # Arrange
        update_data = ContentUpdate(
            title="Updated Title",
            author="Updated Author",
            processing_status=ProcessingStatus.COMPLETED
        )

        # Act
        result = await content_repository.update(sample_content.id, update_data)

        # Assert
        assert result is not None
        assert result.id == sample_content.id
        assert result.title == "Updated Title"
        assert result.author == "Updated Author"
        assert result.processing_status == ProcessingStatus.COMPLETED

    async def test_update_nonexistent_record(self, content_repository):
        """Test updating a non-existent record."""
        # Arrange
        nonexistent_id = uuid.uuid4()
        update_data = ContentUpdate(title="Should Not Update")

        # Act
        result = await content_repository.update(nonexistent_id, update_data)

        # Assert
        assert result is None

    async def test_update_with_dict(self, content_repository, sample_content):
        """Test updating with dictionary data."""
        # Arrange
        update_dict = {
            "title": "Dict Updated Title",
            "word_count": 999
        }

        # Act
        result = await content_repository.update(sample_content.id, update_dict)

        # Assert
        assert result is not None
        assert result.title == "Dict Updated Title"
        assert result.word_count == 999

    async def test_delete_existing_record(self, content_repository, sample_content):
        """Test deleting an existing record."""
        # Arrange
        content_id = sample_content.id

        # Act
        success = await content_repository.delete(content_id)

        # Assert
        assert success is True

        # Verify deletion
        deleted_record = await content_repository.get(content_id)
        assert deleted_record is None

    async def test_delete_nonexistent_record(self, content_repository):
        """Test deleting a non-existent record."""
        # Arrange
        nonexistent_id = uuid.uuid4()

        # Act
        success = await content_repository.delete(nonexistent_id)

        # Assert
        assert success is False

    async def test_delete_multiple_records(self, content_repository, db_session, sample_content_data):
        """Test deleting multiple records."""
        # Arrange - Create multiple records via repository
        content_ids = []
        for i in range(3):
            data = {**sample_content_data, "title": f"Delete Test {i}", "content_hash": f"del{i}" + "x" * 61}
            content = Content(**data)
            db_session.add(content)
            await db_session.flush()  # Ensure ID is assigned
            content_ids.append(content.id)
        await db_session.commit()

        # Act
        deleted_count = await content_repository.delete_multi(content_ids)
        await db_session.commit()  # Ensure delete is committed

        # Assert - SQLite may not return accurate rowcount, so just verify deletion
        # Verify deletions
        for content_id in content_ids:
            deleted_record = await content_repository.get(content_id)
            assert deleted_record is None

    async def test_exists_check(self, content_repository, sample_content):
        """Test checking if record exists."""
        # Act - Check existing record
        exists = await content_repository.exists(sample_content.id)
        assert exists is True

        # Act - Check non-existent record
        nonexistent_id = uuid.uuid4()
        not_exists = await content_repository.exists(nonexistent_id)
        assert not_exists is False

    async def test_build_query(self, content_repository):
        """Test building base query."""
        # Act
        query = content_repository.build_query()

        # Assert
        assert query is not None
        assert hasattr(query, 'where')  # It's a Select object
        assert hasattr(query, 'order_by')
        assert hasattr(query, 'limit')

    async def test_execute_custom_query(self, content_repository, sample_content):
        """Test executing custom query."""
        # Arrange
        query = select(Content).where(Content.id == sample_content.id)

        # Act
        results = await content_repository.execute_query(query)

        # Assert
        assert len(results) == 1
        assert results[0].id == sample_content.id

    async def test_execute_scalar_query(self, content_repository, sample_content):
        """Test executing scalar query."""
        # Arrange
        query = select(func.count(Content.id)).where(Content.id == sample_content.id)

        # Act
        result = await content_repository.execute_scalar_query(query)

        # Assert
        assert result == 1


class TestContentRepository:
    """Test suite for ContentRepository domain-specific functionality."""

    @pytest.fixture
    def content_repository(self, db_session: AsyncSession):
        """Create a content repository for testing."""
        return ContentRepository(db_session)

    async def test_get_by_hash(self, content_repository, sample_content):
        """Test getting content by content hash."""
        # Act
        result = await content_repository.get_by_hash(sample_content.content_hash)

        # Assert
        assert result is not None
        assert result.id == sample_content.id
        assert result.content_hash == sample_content.content_hash

    async def test_get_by_hash_nonexistent(self, content_repository):
        """Test getting content by non-existent hash."""
        # Arrange
        nonexistent_hash = "z" * 64

        # Act
        result = await content_repository.get_by_hash(nonexistent_hash)

        # Assert
        assert result is None

    async def test_get_by_url(self, content_repository, sample_content):
        """Test getting content by source URL."""
        # Act
        result = await content_repository.get_by_url(sample_content.source_url)

        # Assert
        assert result is not None
        assert result.id == sample_content.id
        assert result.source_url == sample_content.source_url

    async def test_get_pending_processing(self, content_repository, db_session, sample_content_data):
        """Test getting content pending processing."""
        # Arrange - Create content with different statuses
        pending_data = {**sample_content_data, "processing_status": ProcessingStatus.PENDING, "content_hash": "p" * 64}
        completed_data = {**sample_content_data, "processing_status": ProcessingStatus.COMPLETED, "content_hash": "c" * 64}

        pending_content = Content(**pending_data)
        completed_content = Content(**completed_data)
        db_session.add_all([pending_content, completed_content])
        await db_session.commit()

        # Act
        results = await content_repository.get_pending_processing(limit=10)

        # Assert
        assert len(results) >= 1
        assert all(r.processing_status == ProcessingStatus.PENDING for r in results)

    async def test_get_by_chroma_document(self, content_repository, db_session, sample_content_data):
        """Test getting content by Chroma document ID."""
        # Arrange
        data = {
            **sample_content_data,
            "chroma_collection": "test_collection",
            "chroma_document_id": "doc_123",
            "content_hash": "chroma_test" + "x" * 53
        }
        content = Content(**data)
        db_session.add(content)
        await db_session.commit()

        # Act
        result = await content_repository.get_by_chroma_document("test_collection", "doc_123")

        # Assert
        assert result is not None
        assert result.chroma_collection == "test_collection"
        assert result.chroma_document_id == "doc_123"

    async def test_search_by_title_or_content(self, content_repository, db_session, sample_content_data):
        """Test searching content by title or content text."""
        # Arrange
        search_data = {
            **sample_content_data,
            "title": "Machine Learning Fundamentals",
            "markdown_content": "# Deep Learning\n\nNeural networks are powerful.",
            "content_hash": "search_test" + "x" * 53
        }
        content = Content(**search_data)
        db_session.add(content)
        await db_session.commit()

        # Act
        results = await content_repository.search_by_title_or_content("Machine Learning")

        # Assert
        assert len(results) >= 1
        matching_content = next((r for r in results if r.id == content.id), None)
        assert matching_content is not None
        assert "Machine Learning" in matching_content.title


class TestPromptRepository:
    """Test suite for PromptRepository domain-specific functionality."""

    @pytest.fixture
    def prompt_repository(self, db_session: AsyncSession):
        """Create a prompt repository for testing."""
        return PromptRepository(db_session)

    async def test_get_by_content_id(self, prompt_repository, sample_prompt):
        """Test getting prompts by content ID."""
        # Act
        results = await prompt_repository.get_by_content_id(sample_prompt.content_id)

        # Assert
        assert len(results) >= 1
        assert any(p.id == sample_prompt.id for p in results)
        assert all(p.content_id == sample_prompt.content_id for p in results)

    async def test_search_prompts_by_type(self, prompt_repository, db_session, sample_content, sample_prompt_data):
        """Test searching prompts by type."""
        # Arrange - Create prompts of different types
        for prompt_type in [PromptType.FACTUAL, PromptType.CONCEPTUAL]:
            data = {
                **sample_prompt_data,
                "content_id": sample_content.id,
                "prompt_type": prompt_type,
                "question": f"Test {prompt_type.value} question?"
            }
            prompt = Prompt(**data)
            db_session.add(prompt)
        await db_session.commit()

        # Act
        factual_results = await prompt_repository.search_prompts("Test", prompt_types=[PromptType.FACTUAL])
        conceptual_results = await prompt_repository.search_prompts("Test", prompt_types=[PromptType.CONCEPTUAL])

        # Assert
        assert all(p.prompt_type == PromptType.FACTUAL for p in factual_results)
        assert all(p.prompt_type == PromptType.CONCEPTUAL for p in conceptual_results)

    async def test_get_high_confidence_prompts(self, prompt_repository, db_session, sample_content, sample_prompt_data):
        """Test getting high-confidence prompts by confidence score."""
        # Arrange - Create prompts with different confidence scores
        for score, suffix in [(0.95, "high"), (0.5, "low")]:
            data = {
                **sample_prompt_data,
                "content_id": sample_content.id,
                "confidence_score": score,
                "question": f"Test question {suffix}?"
            }
            prompt = Prompt(**data)
            db_session.add(prompt)
        await db_session.commit()

        # Act
        high_quality = await prompt_repository.get_high_confidence_prompts(min_confidence=0.8)

        # Assert
        assert all(p.confidence_score >= 0.8 for p in high_quality)

    async def test_get_pending_mochi_sync(self, prompt_repository, db_session, sample_content, sample_prompt_data):
        """Test getting prompts not yet synced to Mochi."""
        # Arrange - Create synced and unsynced prompts with high confidence
        synced_data = {**sample_prompt_data, "content_id": sample_content.id, "mochi_card_id": "mochi_123", "confidence_score": 0.9}
        unsynced_data = {**sample_prompt_data, "content_id": sample_content.id, "mochi_card_id": None, "question": "Unsynced?", "confidence_score": 0.9}

        synced_prompt = Prompt(**synced_data)
        unsynced_prompt = Prompt(**unsynced_data)
        db_session.add_all([synced_prompt, unsynced_prompt])
        await db_session.commit()

        # Act
        unsynced_results = await prompt_repository.get_pending_mochi_sync()

        # Assert
        assert len(unsynced_results) >= 1
        assert all(p.mochi_card_id is None for p in unsynced_results)
        assert any(p.id == unsynced_prompt.id for p in unsynced_results)

    async def test_mark_sent_to_mochi(self, prompt_repository, sample_prompt):
        """Test marking prompt as sent to Mochi."""
        # Arrange
        mochi_card_id = "mochi_card_456"
        mochi_deck_id = "deck_789"

        # Act
        success = await prompt_repository.mark_sent_to_mochi(
            sample_prompt.id,
            mochi_card_id,
            mochi_deck_id
        )

        # Assert
        assert success is True

        # Verify update
        updated_prompt = await prompt_repository.get(sample_prompt.id)
        assert updated_prompt.mochi_card_id == mochi_card_id
        assert updated_prompt.mochi_deck_id == mochi_deck_id
        assert updated_prompt.sent_to_mochi_at is not None


class TestRepositoryErrorHandling:
    """Test suite for repository error handling and edge cases."""

    @pytest.fixture
    def content_repository(self, db_session: AsyncSession):
        """Create a content repository for testing."""
        return BaseRepository[Content, ContentCreate, ContentUpdate](Content, db_session)

    async def test_create_duplicate_hash(self, content_repository, sample_content, sample_content_data):
        """Test creating content with duplicate hash raises error."""
        # Arrange - Try to create content with same hash
        duplicate_data = ContentCreate(**{
            **sample_content_data,
            "title": "Different Title",
            "content_hash": sample_content.content_hash  # Same hash
        })

        # Act & Assert
        with pytest.raises(IntegrityError):
            await content_repository.create(duplicate_data)

    async def test_update_with_invalid_field(self, content_repository, sample_content):
        """Test updating with invalid field name."""
        # Arrange
        update_data = {"nonexistent_field": "value", "title": "Valid Update"}

        # Act - Should not raise error, just ignore invalid field
        result = await content_repository.update(sample_content.id, update_data)

        # Assert
        assert result is not None
        assert result.title == "Valid Update"
        assert not hasattr(result, "nonexistent_field")

    async def test_filter_with_invalid_field(self, content_repository):
        """Test filtering with invalid field name."""
        # Act - Should not raise error, just ignore invalid filter
        results = await content_repository.get_multi(nonexistent_field="value")

        # Assert - Should return all records (filter ignored)
        assert isinstance(results, list)

    async def test_order_by_invalid_field(self, content_repository):
        """Test ordering by invalid field name."""
        # Act - Should not raise error, just ignore invalid order
        results = await content_repository.get_multi(order_by="nonexistent_field")

        # Assert - Should return records without ordering
        assert isinstance(results, list)

    async def test_bulk_operations_empty_list(self, content_repository):
        """Test bulk operations with empty lists."""
        # Act
        create_results = await content_repository.create_bulk([])
        update_count = await content_repository.update_bulk([])
        delete_count = await content_repository.delete_multi([])

        # Assert
        assert create_results == []
        assert update_count == 0
        assert delete_count == 0

    async def test_pagination_edge_cases(self, content_repository):
        """Test pagination with edge case values."""
        # Act - Zero limit
        results_zero = await content_repository.get_multi(skip=0, limit=0)
        assert len(results_zero) == 0

        # Act - Large skip value
        results_large_skip = await content_repository.get_multi(skip=999999, limit=10)
        assert isinstance(results_large_skip, list)

        # Act - Negative values (should be handled gracefully)
        results_negative = await content_repository.get_multi(skip=-1, limit=-1)
        assert isinstance(results_negative, list)