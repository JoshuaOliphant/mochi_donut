# Unit Tests for Pydantic Schemas - Request/Response Validation
"""
Comprehensive unit tests for Pydantic schemas testing validation rules,
serialization, field constraints, and type safety for API endpoints.
"""

import pytest
from datetime import datetime
from typing import Dict, Any
import uuid

from pydantic import ValidationError

from app.schemas.content import (
    ContentBase, ContentCreate, ContentUpdate, ContentInDB, ContentResponse,
    ContentSummary, ContentWithPrompts, ContentProcessingRequest,
    ContentProcessingResponse, ContentBatchProcessingRequest, ContentBatchProcessingResponse,
    ContentSearchRequest, ContentSearchResponse, ContentStatistics
)
from app.schemas.prompt import (
    PromptBase, PromptCreate, PromptUpdate, PromptInDB, PromptResponse,
    PromptSummary, PromptWithMetrics, PromptEditRequest, PromptBatchReviewRequest
)
from app.schemas.common import ErrorResponse, SuccessResponse, PaginatedResponse
from app.db.models import SourceType, PromptType, ProcessingStatus, QualityMetricType


class TestContentSchemas:
    """Test suite for content-related schemas."""

    def test_content_base_valid_data(self):
        """Test ContentBase schema with valid data."""
        # Arrange
        valid_data = {
            "source_url": "https://example.com/article",
            "source_type": SourceType.WEB,
            "title": "Test Article",
            "author": "Test Author",
            "markdown_content": "# Test Content\n\nThis is a test.",
            "word_count": 5,
            "estimated_reading_time": 1,
            "metadata": {"tag": "test"},
            "processing_config": {"max_prompts": 10}
        }

        # Act
        schema = ContentBase(**valid_data)

        # Assert
        assert schema.source_url == "https://example.com/article"
        assert schema.source_type == SourceType.WEB
        assert schema.title == "Test Article"
        assert schema.author == "Test Author"
        assert schema.markdown_content == "# Test Content\n\nThis is a test."
        assert schema.word_count == 5
        assert schema.estimated_reading_time == 1
        assert schema.metadata == {"tag": "test"}
        assert schema.processing_config == {"max_prompts": 10}

    def test_content_base_invalid_url(self):
        """Test ContentBase schema with invalid URL."""
        # Arrange
        invalid_data = {
            "source_url": "not-a-valid-url",
            "source_type": SourceType.WEB,
            "markdown_content": "# Test Content"
        }

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            ContentBase(**invalid_data)

        assert "Source URL must start with" in str(exc_info.value)

    def test_content_base_empty_markdown(self):
        """Test ContentBase schema with empty markdown content."""
        # Arrange
        invalid_data = {
            "source_type": SourceType.WEB,
            "markdown_content": ""
        }

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            ContentBase(**invalid_data)

        assert "Markdown content cannot be empty" in str(exc_info.value)

    def test_content_base_whitespace_only_markdown(self):
        """Test ContentBase schema with whitespace-only markdown."""
        # Arrange
        invalid_data = {
            "source_type": SourceType.WEB,
            "markdown_content": "   \n\t  \n  "
        }

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            ContentBase(**invalid_data)

        assert "Markdown content cannot be empty" in str(exc_info.value)

    def test_content_create_valid_hash(self):
        """Test ContentCreate schema with valid content hash."""
        # Arrange
        valid_data = {
            "source_type": SourceType.PDF,
            "markdown_content": "# PDF Content",
            "content_hash": "a" * 64  # 64-character SHA-256 hash
        }

        # Act
        schema = ContentCreate(**valid_data)

        # Assert
        assert schema.content_hash == "a" * 64

    def test_content_create_invalid_hash_length(self):
        """Test ContentCreate schema with invalid hash length."""
        # Arrange
        invalid_data = {
            "source_type": SourceType.PDF,
            "markdown_content": "# PDF Content",
            "content_hash": "short_hash"
        }

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            ContentCreate(**invalid_data)

        assert "Content hash must be 64 characters" in str(exc_info.value)

    def test_content_update_partial_fields(self):
        """Test ContentUpdate schema with partial field updates."""
        # Arrange
        update_data = {
            "title": "Updated Title",
            "processing_status": ProcessingStatus.COMPLETED
        }

        # Act
        schema = ContentUpdate(**update_data)

        # Assert
        assert schema.title == "Updated Title"
        assert schema.processing_status == ProcessingStatus.COMPLETED
        assert schema.source_url is None  # Not provided
        assert schema.markdown_content is None  # Not provided

    def test_content_in_db_complete_data(self):
        """Test ContentInDB schema with complete database data."""
        # Arrange
        db_data = {
            "id": uuid.uuid4(),
            "source_url": "https://example.com",
            "source_type": SourceType.WEB,
            "title": "Test",
            "author": "Author",
            "markdown_content": "# Content",
            "content_hash": "b" * 64,
            "raw_text": "Raw content text",
            "chroma_collection": "test_collection",
            "chroma_document_id": "doc_123",
            "word_count": 10,
            "estimated_reading_time": 2,
            "processing_status": ProcessingStatus.COMPLETED,
            "metadata": {"test": True},
            "processing_config": {"max": 5},
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "processed_at": datetime.utcnow()
        }

        # Act
        schema = ContentInDB(**db_data)

        # Assert
        assert isinstance(schema.id, uuid.UUID)
        assert schema.source_type == SourceType.WEB
        assert schema.processing_status == ProcessingStatus.COMPLETED
        assert isinstance(schema.created_at, datetime)
        assert isinstance(schema.updated_at, datetime)
        assert isinstance(schema.processed_at, datetime)

    def test_content_response_with_stats(self):
        """Test ContentResponse schema with processing statistics."""
        # Arrange
        response_data = {
            "id": uuid.uuid4(),
            "source_type": SourceType.WEB,
            "markdown_content": "# Test",
            "content_hash": "c" * 64,
            "processing_status": ProcessingStatus.COMPLETED,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "prompt_count": 5,
            "processing_stats": {
                "total_prompts": 5,
                "quality_scores": [0.8, 0.9, 0.7, 0.85, 0.82],
                "processing_time_ms": 3500
            }
        }

        # Act
        schema = ContentResponse(**response_data)

        # Assert
        assert schema.prompt_count == 5
        assert schema.processing_stats["total_prompts"] == 5
        assert len(schema.processing_stats["quality_scores"]) == 5


class TestContentProcessingSchemas:
    """Test suite for content processing request/response schemas."""

    def test_content_processing_request_with_url(self):
        """Test ContentProcessingRequest with source URL."""
        # Arrange
        request_data = {
            "source_url": "https://example.com/article",
            "source_type": SourceType.WEB,
            "processing_config": {"max_prompts": 15},
            "priority": 3
        }

        # Act
        schema = ContentProcessingRequest(**request_data)

        # Assert
        assert schema.source_url == "https://example.com/article"
        assert schema.source_type == SourceType.WEB
        assert schema.raw_content is None
        assert schema.priority == 3

    def test_content_processing_request_with_raw_content(self):
        """Test ContentProcessingRequest with raw content."""
        # Arrange
        request_data = {
            "source_type": SourceType.MARKDOWN,
            "raw_content": "# Direct Content\n\nDirect markdown input.",
            "priority": 5
        }

        # Act
        schema = ContentProcessingRequest(**request_data)

        # Assert
        assert schema.source_url is None
        assert schema.raw_content == "# Direct Content\n\nDirect markdown input."
        assert schema.priority == 5

    def test_content_processing_request_missing_both_sources(self):
        """Test ContentProcessingRequest validation when both sources are missing."""
        # Arrange
        invalid_data = {
            "source_type": SourceType.WEB,
            "priority": 5
        }

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            ContentProcessingRequest(**invalid_data)

        assert "Either source_url or raw_content must be provided" in str(exc_info.value)

    def test_content_processing_request_invalid_priority(self):
        """Test ContentProcessingRequest with invalid priority."""
        # Arrange
        invalid_data = {
            "source_url": "https://example.com",
            "source_type": SourceType.WEB,
            "priority": 15  # Invalid: > 10
        }

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            ContentProcessingRequest(**invalid_data)

        assert "Priority must be between 1 and 10" in str(exc_info.value)

    def test_batch_processing_request_valid(self):
        """Test ContentBatchProcessingRequest with valid batch."""
        # Arrange
        batch_data = {
            "items": [
                {
                    "source_url": "https://example.com/1",
                    "source_type": SourceType.WEB,
                    "priority": 3
                },
                {
                    "source_type": SourceType.MARKDOWN,
                    "raw_content": "# Content 2",
                    "priority": 5
                }
            ],
            "batch_config": {"parallel_processing": True}
        }

        # Act
        schema = ContentBatchProcessingRequest(**batch_data)

        # Assert
        assert len(schema.items) == 2
        assert schema.items[0].source_url == "https://example.com/1"
        assert schema.items[1].raw_content == "# Content 2"
        assert schema.batch_config == {"parallel_processing": True}

    def test_batch_processing_request_too_large(self):
        """Test ContentBatchProcessingRequest with too many items."""
        # Arrange
        large_batch = {
            "items": [
                {
                    "source_type": SourceType.WEB,
                    "source_url": f"https://example.com/{i}",
                    "priority": 5
                }
                for i in range(101)  # Too many items
            ]
        }

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            ContentBatchProcessingRequest(**large_batch)

        assert "Batch size cannot exceed 100 items" in str(exc_info.value)


class TestContentSearchSchemas:
    """Test suite for content search schemas."""

    def test_content_search_request_valid(self):
        """Test ContentSearchRequest with valid parameters."""
        # Arrange
        search_data = {
            "query": "machine learning algorithms",
            "source_types": [SourceType.WEB, SourceType.PDF],
            "processing_status": [ProcessingStatus.COMPLETED],
            "date_from": datetime(2023, 1, 1),
            "date_to": datetime(2023, 12, 31),
            "min_confidence": 0.7,
            "similarity_threshold": 0.8,
            "limit": 25,
            "offset": 0
        }

        # Act
        schema = ContentSearchRequest(**search_data)

        # Assert
        assert schema.query == "machine learning algorithms"
        assert SourceType.WEB in schema.source_types
        assert SourceType.PDF in schema.source_types
        assert ProcessingStatus.COMPLETED in schema.processing_status
        assert schema.min_confidence == 0.7
        assert schema.similarity_threshold == 0.8
        assert schema.limit == 25

    def test_content_search_request_empty_query(self):
        """Test ContentSearchRequest with empty query."""
        # Arrange
        invalid_data = {
            "query": "",
            "limit": 10
        }

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            ContentSearchRequest(**invalid_data)

        assert "Search query cannot be empty" in str(exc_info.value)

    def test_content_search_request_whitespace_query(self):
        """Test ContentSearchRequest with whitespace-only query."""
        # Arrange
        invalid_data = {
            "query": "   \n\t  ",
            "limit": 10
        }

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            ContentSearchRequest(**invalid_data)

        assert "Search query cannot be empty" in str(exc_info.value)

    def test_content_search_response_structure(self):
        """Test ContentSearchResponse structure."""
        # Arrange
        response_data = {
            "query": "test query",
            "results": [
                {
                    "id": str(uuid.uuid4()),
                    "title": "Result 1",
                    "similarity_score": 0.85,
                    "source_type": "WEB"
                },
                {
                    "id": str(uuid.uuid4()),
                    "title": "Result 2",
                    "similarity_score": 0.78,
                    "source_type": "PDF"
                }
            ],
            "total_results": 2,
            "similarity_threshold": 0.7,
            "search_metadata": {
                "search_time_ms": 150,
                "index_used": "content_embedding"
            }
        }

        # Act
        schema = ContentSearchResponse(**response_data)

        # Assert
        assert schema.query == "test query"
        assert len(schema.results) == 2
        assert schema.total_results == 2
        assert schema.similarity_threshold == 0.7
        assert schema.search_metadata["search_time_ms"] == 150


class TestPromptSchemas:
    """Test suite for prompt-related schemas."""

    def test_prompt_base_valid_data(self):
        """Test PromptBase schema with valid data."""
        # Arrange
        valid_data = {
            "question": "What is the capital of France?",
            "answer": "The capital of France is Paris.",
            "prompt_type": PromptType.FACTUAL,
            "confidence_score": 0.9,
            "difficulty_level": 2,
            "source_context": "Geography lesson context",
            "tags": ["geography", "europe", "capitals"],
            "metadata": {"source_page": 15}
        }

        # Act
        schema = PromptBase(**valid_data)

        # Assert
        assert schema.question == "What is the capital of France?"
        assert schema.answer == "The capital of France is Paris."
        assert schema.prompt_type == PromptType.FACTUAL
        assert schema.confidence_score == 0.9
        assert schema.difficulty_level == 2
        assert schema.tags == ["geography", "europe", "capitals"]

    def test_prompt_base_empty_question(self):
        """Test PromptBase schema with empty question."""
        # Arrange
        invalid_data = {
            "question": "",
            "answer": "Some answer",
            "prompt_type": PromptType.FACTUAL
        }

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            PromptBase(**invalid_data)

    def test_prompt_base_empty_answer(self):
        """Test PromptBase schema with empty answer."""
        # Arrange
        invalid_data = {
            "question": "Some question?",
            "answer": "",
            "prompt_type": PromptType.FACTUAL
        }

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            PromptBase(**invalid_data)

    def test_prompt_base_invalid_confidence_score(self):
        """Test PromptBase schema with invalid confidence score."""
        # Arrange
        invalid_data = {
            "question": "Test question?",
            "answer": "Test answer",
            "prompt_type": PromptType.FACTUAL,
            "confidence_score": 1.5  # Invalid: > 1.0
        }

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            PromptBase(**invalid_data)

    def test_prompt_base_invalid_difficulty_level(self):
        """Test PromptBase schema with invalid difficulty level."""
        # Arrange
        invalid_data = {
            "question": "Test question?",
            "answer": "Test answer",
            "prompt_type": PromptType.FACTUAL,
            "difficulty_level": 10  # Invalid: > 5
        }

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            PromptBase(**invalid_data)

    def test_prompt_create_with_content_id(self):
        """Test PromptCreate schema with content_id."""
        # Arrange
        create_data = {
            "content_id": uuid.uuid4(),
            "question": "What is TDD?",
            "answer": "Test-Driven Development",
            "prompt_type": PromptType.CONCEPTUAL
        }

        # Act
        schema = PromptCreate(**create_data)

        # Assert
        assert isinstance(schema.content_id, uuid.UUID)
        assert schema.question == "What is TDD?"
        assert schema.prompt_type == PromptType.CONCEPTUAL

    def test_prompt_update_partial_fields(self):
        """Test PromptUpdate schema with partial updates."""
        # Arrange
        update_data = {
            "question": "Updated question?",
            "confidence_score": 0.95,
            "edit_reason": "Improved clarity"
        }

        # Act
        schema = PromptUpdate(**update_data)

        # Assert
        assert schema.question == "Updated question?"
        assert schema.confidence_score == 0.95
        assert schema.edit_reason == "Improved clarity"
        assert schema.answer is None  # Not provided

    def test_prompt_edit_request_validation(self):
        """Test PromptEditRequest validation."""
        # Arrange
        edit_data = {
            "question": "What is the revised question?",
            "answer": "This is the revised answer.",
            "edit_reason": "Better alignment with learning objectives",
            "difficulty_adjustment": 1  # Increase difficulty by 1 level
        }

        # Act
        schema = PromptEditRequest(**edit_data)

        # Assert
        assert schema.question == "What is the revised question?"
        assert schema.edit_reason == "Better alignment with learning objectives"
        assert schema.difficulty_adjustment == 1

    def test_prompt_batch_review_request(self):
        """Test PromptBatchReviewRequest schema."""
        # Arrange
        batch_data = {
            "prompt_ids": [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()],
            "review_criteria": {
                "focus_specificity": 0.8,
                "precision_clarity": 0.75,
                "cognitive_load": 0.7
            },
            "reviewer_notes": "Batch review for quality assurance",
            "auto_approve_threshold": 0.85
        }

        # Act
        schema = PromptBatchReviewRequest(**batch_data)

        # Assert
        assert len(schema.prompt_ids) == 3
        assert schema.review_criteria["focus_specificity"] == 0.8
        assert schema.auto_approve_threshold == 0.85


class TestCommonSchemas:
    """Test suite for common/shared schemas."""

    def test_error_response_structure(self):
        """Test ErrorResponse schema structure."""
        # Arrange
        error_data = {
            "error": True,
            "message": "Validation failed",
            "error_code": "VALIDATION_ERROR",
            "details": {
                "field": "question",
                "issue": "cannot be empty"
            },
            "timestamp": datetime.utcnow()
        }

        # Act
        schema = ErrorResponse(**error_data)

        # Assert
        assert schema.error is True
        assert schema.message == "Validation failed"
        assert schema.error_code == "VALIDATION_ERROR"
        assert schema.details["field"] == "question"

    def test_success_response_structure(self):
        """Test SuccessResponse schema structure."""
        # Arrange
        success_data = {
            "success": True,
            "message": "Content processed successfully",
            "data": {
                "content_id": str(uuid.uuid4()),
                "prompts_generated": 8
            },
            "timestamp": datetime.utcnow()
        }

        # Act
        schema = SuccessResponse(**success_data)

        # Assert
        assert schema.success is True
        assert schema.message == "Content processed successfully"
        assert schema.data["prompts_generated"] == 8

    def test_paginated_response_structure(self):
        """Test PaginatedResponse schema structure."""
        # Arrange
        paginated_data = {
            "items": [
                {"id": str(uuid.uuid4()), "title": "Item 1"},
                {"id": str(uuid.uuid4()), "title": "Item 2"}
            ],
            "total": 25,
            "page": 1,
            "per_page": 10,
            "pages": 3,
            "has_next": True,
            "has_prev": False
        }

        # Act
        schema = PaginatedResponse(**paginated_data)

        # Assert
        assert len(schema.items) == 2
        assert schema.total == 25
        assert schema.page == 1
        assert schema.per_page == 10
        assert schema.pages == 3
        assert schema.has_next is True
        assert schema.has_prev is False


class TestSchemaFieldValidation:
    """Test suite for schema field validation edge cases."""

    def test_string_length_validation(self):
        """Test string length validation across schemas."""
        # Test title length limit
        with pytest.raises(ValidationError):
            ContentBase(
                source_type=SourceType.WEB,
                title="x" * 501,  # Exceeds 500 char limit
                markdown_content="# Content"
            )

        # Test author length limit
        with pytest.raises(ValidationError):
            ContentBase(
                source_type=SourceType.WEB,
                author="x" * 256,  # Exceeds 255 char limit
                markdown_content="# Content"
            )

    def test_numeric_range_validation(self):
        """Test numeric range validation."""
        # Test negative word count
        with pytest.raises(ValidationError):
            ContentBase(
                source_type=SourceType.WEB,
                markdown_content="# Content",
                word_count=-5  # Invalid: negative
            )

        # Test negative reading time
        with pytest.raises(ValidationError):
            ContentBase(
                source_type=SourceType.WEB,
                markdown_content="# Content",
                estimated_reading_time=-1  # Invalid: negative
            )

    def test_url_validation_edge_cases(self):
        """Test URL validation edge cases."""
        valid_urls = [
            "https://example.com",
            "http://test.org/path",
            "file:///local/path"
        ]

        for url in valid_urls:
            schema = ContentBase(
                source_type=SourceType.WEB,
                source_url=url,
                markdown_content="# Content"
            )
            assert schema.source_url == url

        invalid_urls = [
            "ftp://example.com",
            "example.com",
            "not-a-url"
        ]

        for url in invalid_urls:
            with pytest.raises(ValidationError):
                ContentBase(
                    source_type=SourceType.WEB,
                    source_url=url,
                    markdown_content="# Content"
                )

    def test_json_field_validation(self):
        """Test JSON field validation."""
        # Valid JSON objects
        valid_metadata = [
            {"key": "value"},
            {"nested": {"object": True}},
            {"array": [1, 2, 3]},
            None  # Should be allowed
        ]

        for metadata in valid_metadata:
            schema = ContentBase(
                source_type=SourceType.WEB,
                markdown_content="# Content",
                metadata=metadata
            )
            assert schema.metadata == metadata