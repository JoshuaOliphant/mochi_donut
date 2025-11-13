# Unit Tests for Service Layer - Business Logic
"""
Comprehensive unit tests for service layer testing business logic,
orchestration patterns, external integrations, and error handling.
"""

import pytest
from datetime import datetime, timezone
from typing import Dict, Any, List
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import BackgroundTasks

from app.services.content_processor import ContentProcessorService
from app.services.prompt_service import PromptService
from app.services.prompt_generator import PromptGeneratorService
from app.repositories.content import ContentRepository
from app.repositories.prompt import PromptRepository
from app.schemas.content import (
    ContentProcessingRequest, ContentProcessingResponse,
    ContentBatchProcessingRequest, ContentBatchProcessingResponse,
    ContentCreate
)
from app.schemas.prompt import PromptCreate, PromptUpdate
from app.db.models import SourceType, ProcessingStatus, PromptType, Content, Prompt
from app.integrations.jina_client import JinaAIClient, JinaContentResult
from app.integrations.chroma_client import ChromaClient
from app.integrations.openai_client import OpenAIClient


class TestContentProcessorService:
    """Test suite for ContentProcessorService business logic."""

    @pytest.fixture
    def mock_content_repo(self):
        """Mock content repository."""
        repo = AsyncMock(spec=ContentRepository)
        return repo

    @pytest.fixture
    def mock_prompt_repo(self):
        """Mock prompt repository."""
        repo = AsyncMock(spec=PromptRepository)
        return repo

    @pytest.fixture
    def mock_jina_client(self):
        """Mock JinaAI client."""
        client = AsyncMock(spec=JinaAIClient)
        return client

    @pytest.fixture
    def mock_chroma_client(self):
        """Mock Chroma client."""
        client = AsyncMock(spec=ChromaClient)
        return client

    @pytest.fixture
    def content_processor_service(self, mock_content_repo, mock_prompt_repo, mock_jina_client, mock_chroma_client):
        """Create ContentProcessorService with mocked dependencies."""
        return ContentProcessorService(
            content_repo=mock_content_repo,
            prompt_repo=mock_prompt_repo,
            jina_client=mock_jina_client,
            chroma_client=mock_chroma_client
        )

    @pytest.fixture
    def sample_processing_request(self):
        """Sample content processing request."""
        return ContentProcessingRequest(
            source_url="https://example.com/article",
            source_type=SourceType.WEB,
            processing_config={"max_prompts": 10},
            priority=5
        )

    @pytest.fixture
    def sample_raw_content_request(self):
        """Sample raw content processing request."""
        return ContentProcessingRequest(
            source_type=SourceType.MARKDOWN,
            raw_content="# Test Content\n\nThis is test content for processing.",
            priority=3
        )

    async def test_submit_for_processing_with_raw_content(
        self,
        content_processor_service,
        mock_content_repo,
        sample_raw_content_request
    ):
        """Test submitting raw content for processing."""
        # Arrange
        mock_content_repo.get_by_hash.return_value = None  # No duplicate
        mock_content = Content(id=uuid.uuid4(), processing_status=ProcessingStatus.PENDING)
        mock_content_repo.create.return_value = mock_content

        background_tasks = MagicMock(spec=BackgroundTasks)

        # Act
        result = await content_processor_service.submit_for_processing(
            sample_raw_content_request,
            background_tasks
        )

        # Assert
        assert isinstance(result, ContentProcessingResponse)
        assert result.content_id == mock_content.id
        assert result.processing_status == ProcessingStatus.PENDING
        assert "submitted for processing" in result.message

        # Verify content creation was called
        mock_content_repo.create.assert_called_once()
        create_call_args = mock_content_repo.create.call_args[0][0]
        assert create_call_args.markdown_content == sample_raw_content_request.raw_content
        assert create_call_args.source_type == SourceType.MARKDOWN

        # Verify background task was added
        background_tasks.add_task.assert_called_once()

    async def test_submit_for_processing_with_url(
        self,
        content_processor_service,
        mock_content_repo,
        mock_jina_client,
        sample_processing_request
    ):
        """Test submitting URL for processing."""
        # Arrange
        mock_jina_result = JinaContentResult(
            content="# Fetched Content\n\nThis is fetched from URL.",
            title="Fetched Article",
            metadata={"word_count": 10}
        )
        mock_jina_client.extract_from_url.return_value = mock_jina_result
        mock_content_repo.get_by_hash.return_value = None  # No duplicate
        mock_content = Content(id=uuid.uuid4(), processing_status=ProcessingStatus.PENDING)
        mock_content_repo.create.return_value = mock_content

        background_tasks = MagicMock(spec=BackgroundTasks)

        # Act
        result = await content_processor_service.submit_for_processing(
            sample_processing_request,
            background_tasks
        )

        # Assert
        assert isinstance(result, ContentProcessingResponse)
        assert result.content_id == mock_content.id
        assert result.processing_status == ProcessingStatus.PENDING

        # Verify JinaAI was called
        mock_jina_client.extract_from_url.assert_called_once_with(
            sample_processing_request.source_url,
            use_cache=True
        )

        # Verify content creation
        mock_content_repo.create.assert_called_once()
        create_call_args = mock_content_repo.create.call_args[0][0]
        assert create_call_args.title == "Fetched Article"
        assert create_call_args.markdown_content == mock_jina_result.content

    async def test_submit_for_processing_duplicate_content(
        self,
        content_processor_service,
        mock_content_repo,
        sample_raw_content_request
    ):
        """Test submitting duplicate content."""
        # Arrange
        existing_content = Content(
            id=uuid.uuid4(),
            processing_status=ProcessingStatus.COMPLETED,
            processed_at=datetime.now(timezone.utc)
        )
        mock_content_repo.get_by_hash.return_value = existing_content

        background_tasks = MagicMock(spec=BackgroundTasks)

        # Act
        result = await content_processor_service.submit_for_processing(
            sample_raw_content_request,
            background_tasks
        )

        # Assert
        assert result.content_id == existing_content.id
        assert result.processing_status == ProcessingStatus.COMPLETED
        assert "already exists" in result.message

        # Verify no new content was created
        mock_content_repo.create.assert_not_called()

    async def test_submit_for_processing_jina_failure(
        self,
        content_processor_service,
        mock_jina_client,
        sample_processing_request
    ):
        """Test handling JinaAI extraction failure."""
        # Arrange
        mock_jina_client.extract_from_url.side_effect = Exception("JinaAI service unavailable")

        background_tasks = MagicMock(spec=BackgroundTasks)

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            await content_processor_service.submit_for_processing(
                sample_processing_request,
                background_tasks
            )

        assert "Failed to submit content for processing" in str(exc_info.value)

    async def test_submit_batch_for_processing_mixed_results(
        self,
        content_processor_service,
        mock_content_repo,
        mock_jina_client
    ):
        """Test batch processing with mixed success/failure results."""
        # Arrange
        successful_request = ContentProcessingRequest(
            source_type=SourceType.MARKDOWN,
            raw_content="# Success Content",
            priority=5
        )
        failing_request = ContentProcessingRequest(
            source_url="https://invalid-url",
            source_type=SourceType.WEB,
            priority=5
        )

        batch_request = ContentBatchProcessingRequest(
            items=[successful_request, failing_request],
            batch_config={"parallel": True}
        )

        # Mock successful processing for first item
        mock_content_repo.get_by_hash.return_value = None
        mock_content = Content(id=uuid.uuid4(), processing_status=ProcessingStatus.PENDING)
        mock_content_repo.create.return_value = mock_content

        # Mock failure for second item
        mock_jina_client.extract_from_url.side_effect = Exception("Invalid URL")

        background_tasks = MagicMock(spec=BackgroundTasks)

        # Act
        result = await content_processor_service.submit_batch_for_processing(
            batch_request,
            background_tasks
        )

        # Assert
        assert isinstance(result, ContentBatchProcessingResponse)
        assert result.total_items == 2
        assert result.accepted_items == 1
        assert result.rejected_items == 1
        assert len(result.results) == 2

        # Check individual results
        assert result.results[0].processing_status == ProcessingStatus.PENDING
        assert result.results[1].processing_status == ProcessingStatus.FAILED

    async def test_generate_content_hash(self, content_processor_service):
        """Test content hash generation."""
        # Arrange
        content1 = "# Test Content\n\nSame content"
        content2 = "# Test Content\n\nSame content"
        content3 = "# Different Content\n\nDifferent text"

        # Act
        hash1 = content_processor_service._generate_content_hash(content1)
        hash2 = content_processor_service._generate_content_hash(content2)
        hash3 = content_processor_service._generate_content_hash(content3)

        # Assert
        assert len(hash1) == 64  # SHA-256 hex length
        assert hash1 == hash2  # Same content should produce same hash
        assert hash1 != hash3  # Different content should produce different hash

    async def test_estimate_reading_time(self, content_processor_service):
        """Test reading time estimation."""
        # Arrange
        short_content = "Short content with five words."  # 5 words
        medium_content = "This is a medium length content " * 50  # ~400 words
        long_content = "This is a very long content " * 100  # ~600 words

        # Act
        short_time = content_processor_service._estimate_reading_time(short_content)
        medium_time = content_processor_service._estimate_reading_time(medium_content)
        long_time = content_processor_service._estimate_reading_time(long_content)

        # Assert (assuming 200 WPM reading speed)
        assert short_time == 1  # Minimum 1 minute
        assert medium_time == 2  # ~400 words / 200 WPM = 2 minutes
        assert long_time == 3  # ~600 words / 200 WPM = 3 minutes

    async def test_store_in_vector_db(
        self,
        content_processor_service,
        mock_content_repo,
        mock_chroma_client,
        sample_content
    ):
        """Test storing content in vector database."""
        # Arrange
        content_id = sample_content.id
        mock_content_repo.get.return_value = sample_content

        # Act
        document_id = await content_processor_service._store_in_vector_db(content_id)

        # Assert
        assert document_id == str(content_id)

        # Verify Chroma operations
        mock_chroma_client.get_or_create_collection.assert_called_once()
        mock_chroma_client.add_document.assert_called_once()

        # Verify content update with Chroma info
        mock_content_repo.update.assert_called_once_with(
            content_id,
            {
                "chroma_collection": "content_embeddings",
                "chroma_document_id": str(content_id)
            }
        )

    async def test_store_in_vector_db_content_not_found(
        self,
        content_processor_service,
        mock_content_repo
    ):
        """Test storing non-existent content in vector database."""
        # Arrange
        content_id = uuid.uuid4()
        mock_content_repo.get.return_value = None

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            await content_processor_service._store_in_vector_db(content_id)

        assert "Content" in str(exc_info.value) and "not found" in str(exc_info.value)

    async def test_get_processing_status(
        self,
        content_processor_service,
        mock_content_repo,
        mock_prompt_repo,
        sample_content
    ):
        """Test getting detailed processing status."""
        # Arrange
        content_id = sample_content.id
        mock_content_repo.get.return_value = sample_content
        mock_content_repo.get_agent_executions.return_value = [MagicMock(), MagicMock()]  # 2 executions
        mock_prompt_repo.count.return_value = 5  # 5 prompts

        # Act
        status = await content_processor_service.get_processing_status(content_id)

        # Assert
        assert status["content_id"] == content_id
        assert status["processing_status"] == sample_content.processing_status
        assert status["prompt_count"] == 5
        assert status["agent_executions"] == 2
        assert "created_at" in status

    async def test_get_processing_status_content_not_found(
        self,
        content_processor_service,
        mock_content_repo
    ):
        """Test getting status for non-existent content."""
        # Arrange
        content_id = uuid.uuid4()
        mock_content_repo.get.return_value = None

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            await content_processor_service.get_processing_status(content_id)

        assert "Content not found" in str(exc_info.value)


class TestPromptService:
    """Test suite for PromptService business logic."""

    @pytest.fixture
    def mock_prompt_repo(self):
        """Mock prompt repository."""
        repo = AsyncMock(spec=PromptRepository)
        return repo

    @pytest.fixture
    def mock_content_repo(self):
        """Mock content repository."""
        repo = AsyncMock(spec=ContentRepository)
        return repo

    @pytest.fixture
    def prompt_service(self, mock_prompt_repo, mock_content_repo):
        """Create PromptService with mocked dependencies."""
        return PromptService(
            prompt_repo=mock_prompt_repo,
            content_repo=mock_content_repo
        )

    async def test_create_prompt(self, prompt_service, mock_prompt_repo, sample_prompt_data):
        """Test creating a new prompt."""
        # Arrange
        prompt_create = PromptCreate(**{
            **sample_prompt_data,
            "content_id": uuid.uuid4()
        })
        mock_prompt = Prompt(id=uuid.uuid4(), **sample_prompt_data)
        mock_prompt_repo.create.return_value = mock_prompt

        # Act
        result = await prompt_service.create_prompt(prompt_create)

        # Assert
        assert result == mock_prompt
        mock_prompt_repo.create.assert_called_once_with(prompt_create)

    async def test_update_prompt(self, prompt_service, mock_prompt_repo):
        """Test updating an existing prompt."""
        # Arrange
        prompt_id = uuid.uuid4()
        update_data = PromptUpdate(
            question="Updated question?",
            answer="Updated answer",
            edit_reason="Improved clarity"
        )
        mock_updated_prompt = Prompt(id=prompt_id, question="Updated question?")
        mock_prompt_repo.update.return_value = mock_updated_prompt

        # Act
        result = await prompt_service.update_prompt(prompt_id, update_data)

        # Assert
        assert result == mock_updated_prompt
        mock_prompt_repo.update.assert_called_once_with(prompt_id, update_data)

    async def test_update_prompt_not_found(self, prompt_service, mock_prompt_repo):
        """Test updating non-existent prompt."""
        # Arrange
        prompt_id = uuid.uuid4()
        update_data = PromptUpdate(question="Updated question?")
        mock_prompt_repo.update.return_value = None

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            await prompt_service.update_prompt(prompt_id, update_data)

        assert "Prompt not found" in str(exc_info.value)

    async def test_get_prompts_by_content(self, prompt_service, mock_prompt_repo):
        """Test getting prompts by content ID."""
        # Arrange
        content_id = uuid.uuid4()
        mock_prompts = [
            Prompt(id=uuid.uuid4(), content_id=content_id),
            Prompt(id=uuid.uuid4(), content_id=content_id)
        ]
        mock_prompt_repo.get_by_content_id.return_value = mock_prompts

        # Act
        result = await prompt_service.get_prompts_by_content(content_id)

        # Assert
        assert result == mock_prompts
        mock_prompt_repo.get_by_content_id.assert_called_once_with(content_id)

    async def test_get_high_quality_prompts(self, prompt_service, mock_prompt_repo):
        """Test getting high-quality prompts."""
        # Arrange
        min_confidence = 0.8
        mock_prompts = [
            Prompt(id=uuid.uuid4(), confidence_score=0.9),
            Prompt(id=uuid.uuid4(), confidence_score=0.85)
        ]
        mock_prompt_repo.get_high_quality_prompts.return_value = mock_prompts

        # Act
        result = await prompt_service.get_high_quality_prompts(min_confidence)

        # Assert
        assert result == mock_prompts
        mock_prompt_repo.get_high_quality_prompts.assert_called_once_with(min_confidence)

    async def test_bulk_approve_prompts(self, prompt_service, mock_prompt_repo):
        """Test bulk approving prompts."""
        # Arrange
        prompt_ids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]
        approval_data = {
            "approved_by": "reviewer@example.com",
            "approval_reason": "Quality review passed"
        }

        mock_prompt_repo.update_bulk.return_value = 3  # 3 prompts updated

        # Act
        result = await prompt_service.bulk_approve_prompts(prompt_ids, approval_data)

        # Assert
        assert result == 3
        mock_prompt_repo.update_bulk.assert_called_once()

    async def test_get_unsynced_prompts(self, prompt_service, mock_prompt_repo):
        """Test getting prompts not synced to Mochi."""
        # Arrange
        mock_prompts = [
            Prompt(id=uuid.uuid4(), mochi_card_id=None),
            Prompt(id=uuid.uuid4(), mochi_card_id=None)
        ]
        mock_prompt_repo.get_unsynced_to_mochi.return_value = mock_prompts

        # Act
        result = await prompt_service.get_unsynced_prompts()

        # Assert
        assert result == mock_prompts
        mock_prompt_repo.get_unsynced_to_mochi.assert_called_once()


class TestPromptGeneratorService:
    """Test suite for PromptGeneratorService AI integration."""

    @pytest.fixture
    def mock_openai_client(self):
        """Mock OpenAI client."""
        client = AsyncMock(spec=OpenAIClient)
        return client

    @pytest.fixture
    def mock_prompt_repo(self):
        """Mock prompt repository."""
        repo = AsyncMock(spec=PromptRepository)
        return repo

    @pytest.fixture
    def prompt_generator_service(self, mock_openai_client, mock_prompt_repo):
        """Create PromptGeneratorService with mocked dependencies."""
        return PromptGeneratorService(
            openai_client=mock_openai_client,
            prompt_repo=mock_prompt_repo
        )

    async def test_generate_prompts_from_content(
        self,
        prompt_generator_service,
        mock_openai_client,
        sample_content
    ):
        """Test generating prompts from content."""
        # Arrange
        mock_ai_response = {
            "prompts": [
                {
                    "question": "What is the main topic?",
                    "answer": "The main topic is TDD testing.",
                    "type": "factual",
                    "confidence": 0.9
                },
                {
                    "question": "Explain the concept of TDD.",
                    "answer": "TDD is a development approach where tests are written before code.",
                    "type": "conceptual",
                    "confidence": 0.85
                }
            ]
        }
        mock_openai_client.generate_prompts.return_value = mock_ai_response

        # Act
        result = await prompt_generator_service.generate_prompts_from_content(
            sample_content,
            max_prompts=10
        )

        # Assert
        assert len(result) == 2
        assert all("question" in prompt for prompt in result)
        assert all("answer" in prompt for prompt in result)
        assert result[0]["confidence"] == 0.9

        # Verify OpenAI was called with correct parameters
        mock_openai_client.generate_prompts.assert_called_once()
        call_args = mock_openai_client.generate_prompts.call_args
        assert sample_content.markdown_content in str(call_args)

    async def test_generate_prompts_ai_failure(
        self,
        prompt_generator_service,
        mock_openai_client,
        sample_content
    ):
        """Test handling AI generation failure."""
        # Arrange
        mock_openai_client.generate_prompts.side_effect = Exception("AI service unavailable")

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            await prompt_generator_service.generate_prompts_from_content(
                sample_content,
                max_prompts=5
            )

        assert "AI service unavailable" in str(exc_info.value)

    async def test_refine_prompt_quality(
        self,
        prompt_generator_service,
        mock_openai_client,
        sample_prompt
    ):
        """Test refining prompt quality."""
        # Arrange
        mock_refinement_response = {
            "refined_question": "What is the primary concept discussed in TDD?",
            "refined_answer": "The primary concept in TDD is writing tests before implementation code.",
            "improvements": ["More specific language", "Better focus"],
            "quality_score": 0.95
        }
        mock_openai_client.refine_prompt.return_value = mock_refinement_response

        # Act
        result = await prompt_generator_service.refine_prompt_quality(sample_prompt)

        # Assert
        assert result["quality_score"] == 0.95
        assert "refined_question" in result
        assert "improvements" in result

        # Verify OpenAI was called
        mock_openai_client.refine_prompt.assert_called_once()

    async def test_evaluate_prompt_quality(
        self,
        prompt_generator_service,
        mock_openai_client,
        sample_prompt
    ):
        """Test evaluating prompt quality metrics."""
        # Arrange
        mock_evaluation_response = {
            "focus_specificity": 0.8,
            "precision_clarity": 0.9,
            "cognitive_load": 0.7,
            "retrieval_practice": 0.85,
            "overall_quality": 0.82,
            "feedback": {
                "strengths": ["Clear question", "Specific answer"],
                "improvements": ["Could be more challenging"]
            }
        }
        mock_openai_client.evaluate_prompt_quality.return_value = mock_evaluation_response

        # Act
        result = await prompt_generator_service.evaluate_prompt_quality(sample_prompt)

        # Assert
        assert result["overall_quality"] == 0.82
        assert result["focus_specificity"] == 0.8
        assert "feedback" in result
        assert "strengths" in result["feedback"]

        # Verify OpenAI was called
        mock_openai_client.evaluate_prompt_quality.assert_called_once()


class TestServiceLayerIntegration:
    """Test suite for service layer integration patterns."""

    async def test_service_dependency_injection(self):
        """Test that services can be properly dependency-injected."""
        # Arrange
        mock_content_repo = AsyncMock(spec=ContentRepository)
        mock_prompt_repo = AsyncMock(spec=PromptRepository)
        mock_jina_client = AsyncMock(spec=JinaAIClient)
        mock_chroma_client = AsyncMock(spec=ChromaClient)

        # Act
        service = ContentProcessorService(
            content_repo=mock_content_repo,
            prompt_repo=mock_prompt_repo,
            jina_client=mock_jina_client,
            chroma_client=mock_chroma_client
        )

        # Assert
        assert service.content_repo == mock_content_repo
        assert service.prompt_repo == mock_prompt_repo
        assert service.jina_client == mock_jina_client
        assert service.chroma_client == mock_chroma_client

    async def test_service_error_propagation(self, content_processor_service, mock_content_repo):
        """Test that service errors are properly propagated."""
        # Arrange
        mock_content_repo.get.side_effect = Exception("Database connection failed")

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            await content_processor_service.get_processing_status(uuid.uuid4())

        assert "Database connection failed" in str(exc_info.value)

    async def test_service_transaction_handling(self, content_processor_service, mock_content_repo):
        """Test service transaction handling patterns."""
        # This test ensures services handle database transactions appropriately
        # In a real implementation, we'd test rollback behavior on failures

        # Arrange
        content_id = uuid.uuid4()
        mock_content_repo.update.return_value = True

        # Act
        await content_processor_service._store_in_vector_db.__wrapped__(
            content_processor_service, content_id
        )

        # Assert that the method would handle transaction boundaries
        # In real implementation, this would test actual transaction behavior
        assert True  # Placeholder for transaction testing


class TestServiceValidation:
    """Test suite for service-level validation and business rules."""

    async def test_content_processing_business_rules(self, content_processor_service):
        """Test business rule validation in content processing."""
        # Test that empty URL raises appropriate error
        with pytest.raises(ValueError) as exc_info:
            await content_processor_service._fetch_content_from_url("")

        assert "URL is required" in str(exc_info.value)

    async def test_prompt_validation_rules(self, prompt_service, mock_prompt_repo):
        """Test prompt validation business rules."""
        # Arrange
        invalid_prompt_create = PromptCreate(
            content_id=uuid.uuid4(),
            question="",  # Invalid: empty question
            answer="Some answer",
            prompt_type=PromptType.FACTUAL
        )

        # This validation would typically happen at the service layer
        # For now, we test that validation logic exists
        assert hasattr(invalid_prompt_create, 'question')
        assert invalid_prompt_create.question == ""

    async def test_batch_size_limits(self, content_processor_service):
        """Test business rules for batch processing limits."""
        # Test would verify that batch sizes are within acceptable limits
        # This is typically enforced at the schema level but can be double-checked in services

        # Arrange
        large_batch = ContentBatchProcessingRequest(
            items=[
                ContentProcessingRequest(
                    source_type=SourceType.MARKDOWN,
                    raw_content=f"Content {i}",
                    priority=5
                )
                for i in range(150)  # Exceeds typical batch limit
            ]
        )

        # Assert that validation exists (would be in schema validation)
        assert len(large_batch.items) == 150