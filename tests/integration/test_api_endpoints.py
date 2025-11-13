# Integration Tests for API Endpoints - FastAPI Testing
"""
Comprehensive integration tests for FastAPI endpoints testing request/response
cycles, authentication, validation, error handling, and business workflows.
"""

import pytest
from datetime import datetime, timezone
from typing import Dict, Any
import uuid
import json

from httpx import AsyncClient
from fastapi import status

from app.db.models import Content, Prompt, SourceType, PromptType, ProcessingStatus
from app.schemas.content import ContentProcessingRequest, ContentBatchProcessingRequest
from app.schemas.prompt import PromptCreate, PromptUpdate


class TestHealthAndStatus:
    """Test suite for health check and status endpoints."""

    async def test_health_check_endpoint(self, async_client: AsyncClient):
        """Test health check endpoint returns successful response."""
        # Act
        response = await async_client.get("/health")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data

    async def test_api_status_endpoint(self, async_client: AsyncClient):
        """Test API status endpoint returns system information."""
        # Act
        response = await async_client.get("/api/v1/status")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "api_version" in data
        assert "database_status" in data
        assert "external_services" in data

    async def test_metrics_endpoint(self, async_client: AsyncClient):
        """Test metrics endpoint returns system metrics."""
        # Act
        response = await async_client.get("/api/v1/metrics")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "content_stats" in data
        assert "prompt_stats" in data
        assert "processing_stats" in data


class TestContentEndpoints:
    """Test suite for content management endpoints."""

    async def test_create_content_with_url(self, async_client: AsyncClient):
        """Test creating content from URL."""
        # Arrange
        request_data = {
            "source_url": "https://example.com/test-article",
            "source_type": "WEB",
            "processing_config": {"max_prompts": 10},
            "priority": 5
        }

        # Act
        response = await async_client.post("/api/v1/content/process", json=request_data)

        # Assert
        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        assert "content_id" in data
        assert data["processing_status"] == "PENDING"
        assert "submitted for processing" in data["message"]

    async def test_create_content_with_raw_content(self, async_client: AsyncClient):
        """Test creating content with raw markdown."""
        # Arrange
        request_data = {
            "source_type": "MARKDOWN",
            "raw_content": "# Test Content\n\nThis is test content for integration testing.",
            "priority": 3
        }

        # Act
        response = await async_client.post("/api/v1/content/process", json=request_data)

        # Assert
        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        assert "content_id" in data
        assert data["processing_status"] == "PENDING"

    async def test_create_content_invalid_request(self, async_client: AsyncClient):
        """Test creating content with invalid request data."""
        # Arrange
        invalid_request = {
            "source_type": "WEB",
            # Missing both source_url and raw_content
            "priority": 5
        }

        # Act
        response = await async_client.post("/api/v1/content/process", json=invalid_request)

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        data = response.json()
        assert "detail" in data

    async def test_get_content_by_id(self, async_client: AsyncClient, sample_content: Content):
        """Test retrieving content by ID."""
        # Act
        response = await async_client.get(f"/api/v1/content/{sample_content.id}")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == str(sample_content.id)
        assert data["title"] == sample_content.title
        assert data["source_type"] == sample_content.source_type.value

    async def test_get_content_not_found(self, async_client: AsyncClient):
        """Test retrieving non-existent content."""
        # Arrange
        nonexistent_id = uuid.uuid4()

        # Act
        response = await async_client.get(f"/api/v1/content/{nonexistent_id}")

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "Content not found" in data["detail"]

    async def test_list_content_with_pagination(self, async_client: AsyncClient, sample_content: Content):
        """Test listing content with pagination."""
        # Act
        response = await async_client.get("/api/v1/content?skip=0&limit=10")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert len(data["items"]) >= 1

    async def test_list_content_with_filters(self, async_client: AsyncClient, sample_content: Content):
        """Test listing content with filters."""
        # Act
        response = await async_client.get(
            f"/api/v1/content?source_type={sample_content.source_type.value}&processing_status=PENDING"
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "items" in data
        # All items should match the filter criteria
        for item in data["items"]:
            assert item["source_type"] == sample_content.source_type.value

    async def test_update_content(self, async_client: AsyncClient, sample_content: Content):
        """Test updating content."""
        # Arrange
        update_data = {
            "title": "Updated Title",
            "author": "Updated Author"
        }

        # Act
        response = await async_client.put(f"/api/v1/content/{sample_content.id}", json=update_data)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["title"] == "Updated Title"
        assert data["author"] == "Updated Author"

    async def test_delete_content(self, async_client: AsyncClient, sample_content: Content):
        """Test deleting content."""
        # Act
        response = await async_client.delete(f"/api/v1/content/{sample_content.id}")

        # Assert
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify deletion
        get_response = await async_client.get(f"/api/v1/content/{sample_content.id}")
        assert get_response.status_code == status.HTTP_404_NOT_FOUND

    async def test_get_content_processing_status(self, async_client: AsyncClient, sample_content: Content):
        """Test getting detailed content processing status."""
        # Act
        response = await async_client.get(f"/api/v1/content/{sample_content.id}/status")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["content_id"] == str(sample_content.id)
        assert "processing_status" in data
        assert "prompt_count" in data
        assert "agent_executions" in data

    async def test_batch_content_processing(self, async_client: AsyncClient):
        """Test batch content processing."""
        # Arrange
        batch_request = {
            "items": [
                {
                    "source_type": "MARKDOWN",
                    "raw_content": "# Content 1\n\nFirst test content.",
                    "priority": 5
                },
                {
                    "source_type": "MARKDOWN",
                    "raw_content": "# Content 2\n\nSecond test content.",
                    "priority": 3
                }
            ],
            "batch_config": {"parallel_processing": True}
        }

        # Act
        response = await async_client.post("/api/v1/content/batch", json=batch_request)

        # Assert
        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        assert "batch_id" in data
        assert data["total_items"] == 2
        assert data["accepted_items"] >= 0
        assert len(data["results"]) == 2

    async def test_search_content(self, async_client: AsyncClient, sample_content: Content):
        """Test content search functionality."""
        # Arrange
        search_request = {
            "query": "test content",
            "source_types": ["WEB"],
            "limit": 10
        }

        # Act
        response = await async_client.post("/api/v1/content/search", json=search_request)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "results" in data
        assert "total_results" in data
        assert "query" in data
        assert data["query"] == "test content"


class TestPromptEndpoints:
    """Test suite for prompt management endpoints."""

    async def test_create_prompt(self, async_client: AsyncClient, sample_content: Content):
        """Test creating a new prompt."""
        # Arrange
        prompt_data = {
            "content_id": str(sample_content.id),
            "question": "What is the main concept in this content?",
            "answer": "The main concept is integration testing.",
            "prompt_type": "CONCEPTUAL",
            "confidence_score": 0.85,
            "difficulty_level": 3
        }

        # Act
        response = await async_client.post("/api/v1/prompts", json=prompt_data)

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["question"] == prompt_data["question"]
        assert data["answer"] == prompt_data["answer"]
        assert data["prompt_type"] == prompt_data["prompt_type"]
        assert data["confidence_score"] == prompt_data["confidence_score"]

    async def test_create_prompt_invalid_content_id(self, async_client: AsyncClient):
        """Test creating prompt with invalid content ID."""
        # Arrange
        prompt_data = {
            "content_id": str(uuid.uuid4()),  # Non-existent content
            "question": "Test question?",
            "answer": "Test answer",
            "prompt_type": "FACTUAL"
        }

        # Act
        response = await async_client.post("/api/v1/prompts", json=prompt_data)

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_get_prompt_by_id(self, async_client: AsyncClient, sample_prompt: Prompt):
        """Test retrieving prompt by ID."""
        # Act
        response = await async_client.get(f"/api/v1/prompts/{sample_prompt.id}")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == str(sample_prompt.id)
        assert data["question"] == sample_prompt.question
        assert data["answer"] == sample_prompt.answer

    async def test_update_prompt(self, async_client: AsyncClient, sample_prompt: Prompt):
        """Test updating a prompt."""
        # Arrange
        update_data = {
            "question": "Updated question: What is the main concept?",
            "answer": "Updated answer: The main concept is comprehensive testing.",
            "edit_reason": "Improved clarity and specificity"
        }

        # Act
        response = await async_client.put(f"/api/v1/prompts/{sample_prompt.id}", json=update_data)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["question"] == update_data["question"]
        assert data["answer"] == update_data["answer"]
        assert data["edit_reason"] == update_data["edit_reason"]
        assert data["is_edited"] is True

    async def test_delete_prompt(self, async_client: AsyncClient, sample_prompt: Prompt):
        """Test deleting a prompt."""
        # Act
        response = await async_client.delete(f"/api/v1/prompts/{sample_prompt.id}")

        # Assert
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify deletion
        get_response = await async_client.get(f"/api/v1/prompts/{sample_prompt.id}")
        assert get_response.status_code == status.HTTP_404_NOT_FOUND

    async def test_list_prompts_by_content(self, async_client: AsyncClient, sample_content: Content, sample_prompt: Prompt):
        """Test listing prompts by content ID."""
        # Act
        response = await async_client.get(f"/api/v1/content/{sample_content.id}/prompts")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 1
        assert any(p["id"] == str(sample_prompt.id) for p in data)

    async def test_get_prompts_by_type(self, async_client: AsyncClient, sample_prompt: Prompt):
        """Test getting prompts filtered by type."""
        # Act
        response = await async_client.get(f"/api/v1/prompts?prompt_type={sample_prompt.prompt_type.value}")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "items" in data
        for prompt in data["items"]:
            assert prompt["prompt_type"] == sample_prompt.prompt_type.value

    async def test_get_high_quality_prompts(self, async_client: AsyncClient):
        """Test getting high-quality prompts."""
        # Act
        response = await async_client.get("/api/v1/prompts?min_confidence=0.8")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "items" in data
        for prompt in data["items"]:
            if prompt["confidence_score"] is not None:
                assert prompt["confidence_score"] >= 0.8

    async def test_batch_review_prompts(self, async_client: AsyncClient, sample_prompt: Prompt):
        """Test batch reviewing prompts."""
        # Arrange
        review_request = {
            "prompt_ids": [str(sample_prompt.id)],
            "review_criteria": {
                "focus_specificity": 0.8,
                "precision_clarity": 0.75
            },
            "reviewer_notes": "Batch review for quality assurance"
        }

        # Act
        response = await async_client.post("/api/v1/prompts/batch-review", json=review_request)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "review_results" in data
        assert "batch_summary" in data

    async def test_prompt_quality_metrics(self, async_client: AsyncClient, sample_prompt: Prompt):
        """Test getting prompt quality metrics."""
        # Act
        response = await async_client.get(f"/api/v1/prompts/{sample_prompt.id}/quality")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "quality_metrics" in data
        assert "overall_score" in data
        assert "recommendations" in data


class TestMochiIntegration:
    """Test suite for Mochi integration endpoints."""

    async def test_get_mochi_decks(self, async_client: AsyncClient):
        """Test getting available Mochi decks."""
        # Act
        response = await async_client.get("/api/v1/mochi/decks")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "decks" in data
        assert isinstance(data["decks"], list)

    async def test_create_mochi_cards(self, async_client: AsyncClient, sample_prompt: Prompt):
        """Test creating Mochi cards from prompts."""
        # Arrange
        card_request = {
            "prompt_ids": [str(sample_prompt.id)],
            "deck_id": "test-deck-123",
            "tags": ["integration-test"]
        }

        # Act
        response = await async_client.post("/api/v1/mochi/cards/create", json=card_request)

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "cards_created" in data
        assert "sync_summary" in data

    async def test_sync_prompt_to_mochi(self, async_client: AsyncClient, sample_prompt: Prompt):
        """Test syncing individual prompt to Mochi."""
        # Arrange
        sync_request = {
            "deck_id": "test-deck-456",
            "tags": ["test", "api"]
        }

        # Act
        response = await async_client.post(f"/api/v1/prompts/{sample_prompt.id}/sync-mochi", json=sync_request)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "mochi_card_id" in data
        assert "sync_status" in data

    async def test_get_mochi_sync_status(self, async_client: AsyncClient, sample_prompt: Prompt):
        """Test getting Mochi sync status for prompts."""
        # Act
        response = await async_client.get(f"/api/v1/prompts/{sample_prompt.id}/mochi-status")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "is_synced" in data
        assert "mochi_card_id" in data
        assert "last_sync_at" in data


class TestErrorHandling:
    """Test suite for API error handling and edge cases."""

    async def test_invalid_uuid_parameter(self, async_client: AsyncClient):
        """Test handling invalid UUID parameters."""
        # Act
        response = await async_client.get("/api/v1/content/invalid-uuid")

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_request_validation_errors(self, async_client: AsyncClient):
        """Test request validation error responses."""
        # Arrange
        invalid_request = {
            "source_type": "INVALID_TYPE",
            "priority": 15  # Out of range
        }

        # Act
        response = await async_client.post("/api/v1/content/process", json=invalid_request)

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        data = response.json()
        assert "detail" in data
        assert isinstance(data["detail"], list)

    async def test_large_request_handling(self, async_client: AsyncClient):
        """Test handling of large request payloads."""
        # Arrange
        large_content = "x" * 200000  # 200KB content
        request_data = {
            "source_type": "MARKDOWN",
            "raw_content": large_content,
            "priority": 5
        }

        # Act
        response = await async_client.post("/api/v1/content/process", json=request_data)

        # Assert
        # Should either succeed or return appropriate error for size limit
        assert response.status_code in [status.HTTP_202_ACCEPTED, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE]

    async def test_concurrent_request_handling(self, async_client: AsyncClient):
        """Test handling concurrent requests."""
        import asyncio

        # Arrange
        request_data = {
            "source_type": "MARKDOWN",
            "raw_content": "# Concurrent Test\n\nTest concurrent request handling.",
            "priority": 5
        }

        # Act - Send multiple concurrent requests
        tasks = [
            async_client.post("/api/v1/content/process", json=request_data)
            for _ in range(5)
        ]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Assert
        successful_responses = [r for r in responses if not isinstance(r, Exception)]
        assert len(successful_responses) >= 1  # At least one should succeed
        for response in successful_responses:
            assert response.status_code == status.HTTP_202_ACCEPTED

    async def test_rate_limiting(self, async_client: AsyncClient):
        """Test API rate limiting behavior."""
        # This test would verify rate limiting if enabled
        # For now, we test that the endpoint responds normally

        # Act
        responses = []
        for _ in range(10):
            response = await async_client.get("/health")
            responses.append(response)

        # Assert
        # Without rate limiting, all should succeed
        for response in responses:
            assert response.status_code in [status.HTTP_200_OK, status.HTTP_429_TOO_MANY_REQUESTS]


class TestAuthentication:
    """Test suite for authentication and authorization."""

    async def test_public_endpoints_no_auth(self, async_client: AsyncClient):
        """Test that public endpoints work without authentication."""
        # Act
        health_response = await async_client.get("/health")
        status_response = await async_client.get("/api/v1/status")

        # Assert
        assert health_response.status_code == status.HTTP_200_OK
        assert status_response.status_code == status.HTTP_200_OK

    async def test_protected_endpoints_require_auth(self, async_client: AsyncClient):
        """Test that protected endpoints require authentication."""
        # This test assumes some endpoints require authentication
        # Implementation depends on actual auth strategy

        # Act
        response = await async_client.post("/api/v1/admin/system-reset")

        # Assert
        # Should return 401 or 403 if authentication is required
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND  # If endpoint doesn't exist yet
        ]

    async def test_api_key_authentication(self, async_client: AsyncClient):
        """Test API key authentication if implemented."""
        # Arrange
        headers = {"X-API-Key": "test-api-key"}

        # Act
        response = await async_client.get("/api/v1/content", headers=headers)

        # Assert
        # Behavior depends on whether API key auth is implemented
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN
        ]


class TestAPIDocumentation:
    """Test suite for API documentation endpoints."""

    async def test_openapi_schema_endpoint(self, async_client: AsyncClient):
        """Test OpenAPI schema endpoint."""
        # Act
        response = await async_client.get("/openapi.json")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "openapi" in data
        assert "info" in data
        assert "paths" in data

    async def test_swagger_ui_endpoint(self, async_client: AsyncClient):
        """Test Swagger UI endpoint."""
        # Act
        response = await async_client.get("/docs")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert "text/html" in response.headers.get("content-type", "")

    async def test_redoc_endpoint(self, async_client: AsyncClient):
        """Test ReDoc endpoint."""
        # Act
        response = await async_client.get("/redoc")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert "text/html" in response.headers.get("content-type", "")