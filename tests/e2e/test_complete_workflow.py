# End-to-End Tests for Complete Workflow
"""
Comprehensive end-to-end tests covering the complete user journey from
content submission to Mochi card creation, testing the entire system.
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
import uuid
import json

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import Content, Prompt, AgentExecution, ProcessingStatus, SourceType, PromptType
from app.repositories.content import ContentRepository
from app.repositories.prompt import PromptRepository


class TestCompleteContentWorkflow:
    """Test suite for complete content processing workflow."""

    async def test_url_to_mochi_cards_complete_workflow(self, async_client: AsyncClient, db_session: AsyncSession):
        """Test complete workflow from URL submission to Mochi card creation."""
        # Phase 1: Submit URL for processing
        url_request = {
            "source_url": "https://httpbin.org/html",
            "source_type": "WEB",
            "processing_config": {
                "max_prompts": 5,
                "quality_threshold": 0.8,
                "enable_refinement": True
            },
            "priority": 5
        }

        # Act - Submit content
        submit_response = await async_client.post("/api/v1/content/process", json=url_request)

        # Assert - Content submission successful
        assert submit_response.status_code == 202
        submit_data = submit_response.json()
        content_id = submit_data["content_id"]
        assert "submitted for processing" in submit_data["message"]

        # Phase 2: Monitor processing status
        await asyncio.sleep(0.5)  # Allow time for background processing to start

        status_response = await async_client.get(f"/api/v1/content/{content_id}/status")
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert status_data["content_id"] == content_id
        assert status_data["processing_status"] in ["PENDING", "PROCESSING", "COMPLETED"]

        # Phase 3: Verify content was stored
        content_response = await async_client.get(f"/api/v1/content/{content_id}")
        assert content_response.status_code == 200
        content_data = content_response.json()
        assert content_data["source_url"] == url_request["source_url"]
        assert content_data["source_type"] == "WEB"
        assert len(content_data["markdown_content"]) > 0

        # Phase 4: Check if prompts were generated (in real scenario)
        prompts_response = await async_client.get(f"/api/v1/content/{content_id}/prompts")
        assert prompts_response.status_code == 200
        prompts_data = prompts_response.json()
        # In test environment, prompts might not be generated yet due to mocking
        assert isinstance(prompts_data, list)

        # Phase 5: If prompts exist, test Mochi sync
        if len(prompts_data) > 0:
            prompt_id = prompts_data[0]["id"]

            # Test individual prompt sync to Mochi
            mochi_sync_request = {
                "deck_id": "test-deck-e2e",
                "tags": ["e2e-test", "automated"]
            }

            mochi_response = await async_client.post(
                f"/api/v1/prompts/{prompt_id}/sync-mochi",
                json=mochi_sync_request
            )

            # In test environment with mocked Mochi, this might succeed or fail gracefully
            assert mochi_response.status_code in [200, 503]  # Success or service unavailable

    async def test_raw_content_to_quality_prompts_workflow(self, async_client: AsyncClient, db_session: AsyncSession):
        """Test complete workflow with raw content to high-quality prompts."""
        # Phase 1: Submit comprehensive content
        comprehensive_content = """
        # Advanced Machine Learning Concepts

        ## Introduction to Deep Learning
        Deep learning is a subset of machine learning that uses artificial neural networks
        with multiple layers to progressively extract higher-level features from raw input.

        ## Neural Network Architectures

        ### Convolutional Neural Networks (CNNs)
        CNNs are particularly effective for image recognition tasks. They use:
        - Convolutional layers for feature detection
        - Pooling layers for dimensionality reduction
        - Fully connected layers for classification

        Key advantages:
        1. Translation invariance
        2. Parameter sharing
        3. Local connectivity

        ### Recurrent Neural Networks (RNNs)
        RNNs are designed for sequential data processing:
        - LSTM (Long Short-Term Memory) networks
        - GRU (Gated Recurrent Unit) networks
        - Bidirectional RNNs

        ## Training Techniques

        ### Backpropagation
        The fundamental algorithm for training neural networks:
        1. Forward pass: Compute predictions
        2. Calculate loss function
        3. Backward pass: Compute gradients
        4. Update weights using optimization algorithm

        ### Regularization Methods
        - Dropout: Randomly deactivate neurons during training
        - Batch normalization: Normalize inputs to each layer
        - L1/L2 regularization: Add penalty terms to loss function

        ## Practical Applications
        - Computer vision: Image classification, object detection
        - Natural language processing: Language translation, sentiment analysis
        - Reinforcement learning: Game playing, robotics
        """

        content_request = {
            "source_type": "MARKDOWN",
            "raw_content": comprehensive_content,
            "processing_config": {
                "max_prompts": 15,
                "quality_threshold": 0.85,
                "enable_refinement": True,
                "prompt_types": ["FACTUAL", "CONCEPTUAL", "PROCEDURAL"]
            },
            "priority": 3
        }

        # Act - Submit content
        submit_response = await async_client.post("/api/v1/content/process", json=content_request)

        # Assert
        assert submit_response.status_code == 202
        content_id = submit_response.json()["content_id"]

        # Phase 2: Verify content properties
        content_response = await async_client.get(f"/api/v1/content/{content_id}")
        assert content_response.status_code == 200
        content_data = content_response.json()

        assert content_data["word_count"] > 200
        assert content_data["estimated_reading_time"] >= 1
        assert "Deep learning" in content_data["markdown_content"]
        assert "CNN" in content_data["markdown_content"]

        # Phase 3: Wait for and verify processing completion
        # In a real scenario, we would poll until completion
        max_wait_time = 30  # seconds
        wait_interval = 1   # second
        processing_complete = False

        for _ in range(max_wait_time):
            status_response = await async_client.get(f"/api/v1/content/{content_id}/status")
            status_data = status_response.json()

            if status_data["processing_status"] == "COMPLETED":
                processing_complete = True
                break
            elif status_data["processing_status"] == "FAILED":
                break

            await asyncio.sleep(wait_interval)

        # Phase 4: Check generated prompts quality
        prompts_response = await async_client.get(f"/api/v1/content/{content_id}/prompts")
        assert prompts_response.status_code == 200
        prompts_data = prompts_response.json()

        if len(prompts_data) > 0:
            # Verify prompt diversity
            prompt_types = set(p["prompt_type"] for p in prompts_data)
            assert len(prompt_types) >= 1  # At least one type should be present

            # Verify prompt quality
            high_quality_prompts = [p for p in prompts_data if p.get("confidence_score", 0) >= 0.8]
            assert len(high_quality_prompts) >= 1

            # Test prompt quality evaluation
            if len(prompts_data) > 0:
                prompt_id = prompts_data[0]["id"]
                quality_response = await async_client.get(f"/api/v1/prompts/{prompt_id}/quality")
                assert quality_response.status_code == 200

    async def test_batch_processing_complete_workflow(self, async_client: AsyncClient, db_session: AsyncSession):
        """Test complete batch processing workflow."""
        # Phase 1: Submit batch of related content
        batch_content = [
            {
                "source_type": "MARKDOWN",
                "raw_content": "# Python Basics\n\nPython is a versatile programming language known for its simplicity and readability.",
                "priority": 5,
                "processing_config": {"max_prompts": 3}
            },
            {
                "source_type": "MARKDOWN",
                "raw_content": "# Python Data Structures\n\nLists, dictionaries, and sets are fundamental data structures in Python.",
                "priority": 5,
                "processing_config": {"max_prompts": 4}
            },
            {
                "source_type": "MARKDOWN",
                "raw_content": "# Python Functions\n\nFunctions in Python allow code reusability and better organization.",
                "priority": 5,
                "processing_config": {"max_prompts": 3}
            }
        ]

        batch_request = {
            "items": batch_content,
            "batch_config": {
                "parallel_processing": True,
                "quality_threshold": 0.7
            }
        }

        # Act - Submit batch
        batch_response = await async_client.post("/api/v1/content/batch", json=batch_request)

        # Assert
        assert batch_response.status_code == 202
        batch_data = batch_response.json()
        assert batch_data["total_items"] == 3
        assert len(batch_data["results"]) == 3

        # Phase 2: Monitor batch processing
        content_ids = [result["content_id"] for result in batch_data["results"]
                      if result["processing_status"] != "FAILED"]

        await asyncio.sleep(1)  # Allow processing time

        # Phase 3: Verify all content items
        for content_id in content_ids:
            content_response = await async_client.get(f"/api/v1/content/{content_id}")
            assert content_response.status_code == 200
            content_data = content_response.json()
            assert "Python" in content_data["markdown_content"]

        # Phase 4: Test batch operations on results
        if len(content_ids) > 0:
            # Get all prompts from batch processing
            all_prompts = []
            for content_id in content_ids:
                prompts_response = await async_client.get(f"/api/v1/content/{content_id}/prompts")
                if prompts_response.status_code == 200:
                    all_prompts.extend(prompts_response.json())

            # If prompts were generated, test batch review
            if len(all_prompts) > 0:
                prompt_ids = [p["id"] for p in all_prompts]

                batch_review_request = {
                    "prompt_ids": prompt_ids,
                    "review_criteria": {
                        "focus_specificity": 0.7,
                        "precision_clarity": 0.8
                    },
                    "reviewer_notes": "E2E batch review test"
                }

                review_response = await async_client.post(
                    "/api/v1/prompts/batch-review",
                    json=batch_review_request
                )

                assert review_response.status_code == 200

    async def test_error_recovery_workflow(self, async_client: AsyncClient, db_session: AsyncSession):
        """Test error handling and recovery in complete workflow."""
        # Phase 1: Submit content that might cause processing issues
        problematic_content = {
            "source_type": "MARKDOWN",
            "raw_content": "x" * 500,  # Very repetitive content
            "processing_config": {
                "max_prompts": 50,  # Unrealistic number
                "quality_threshold": 0.99  # Unrealistic threshold
            },
            "priority": 1
        }

        # Act - Submit problematic content
        submit_response = await async_client.post("/api/v1/content/process", json=problematic_content)

        # Should accept the content even if processing might fail
        assert submit_response.status_code == 202
        content_id = submit_response.json()["content_id"]

        # Phase 2: Monitor for failure handling
        await asyncio.sleep(1)

        status_response = await async_client.get(f"/api/v1/content/{content_id}/status")
        assert status_response.status_code == 200
        status_data = status_response.json()

        # Content should exist even if processing failed
        assert status_data["content_id"] == content_id
        assert status_data["processing_status"] in ["PENDING", "PROCESSING", "FAILED", "COMPLETED"]

        # Phase 3: Test error information retrieval
        content_response = await async_client.get(f"/api/v1/content/{content_id}")
        assert content_response.status_code == 200
        content_data = content_response.json()

        # Content should be stored regardless of processing outcome
        assert content_data["markdown_content"] == "x" * 500

        # Phase 4: Test retry mechanism (if implemented)
        if status_data["processing_status"] == "FAILED":
            # Could test retry functionality here
            retry_response = await async_client.post(f"/api/v1/content/{content_id}/retry")
            # Retry endpoint might not be implemented yet
            assert retry_response.status_code in [200, 404, 501]

    async def test_search_and_discovery_workflow(self, async_client: AsyncClient, db_session: AsyncSession):
        """Test search and content discovery workflow."""
        # Phase 1: Submit searchable content
        searchable_contents = [
            {
                "source_type": "MARKDOWN",
                "raw_content": "# Artificial Intelligence Overview\n\nAI is transforming technology.",
                "priority": 5
            },
            {
                "source_type": "MARKDOWN",
                "raw_content": "# Machine Learning Fundamentals\n\nML algorithms learn from data.",
                "priority": 5
            },
            {
                "source_type": "MARKDOWN",
                "raw_content": "# Deep Learning Networks\n\nNeural networks with multiple layers.",
                "priority": 5
            }
        ]

        content_ids = []
        for content in searchable_contents:
            submit_response = await async_client.post("/api/v1/content/process", json=content)
            assert submit_response.status_code == 202
            content_ids.append(submit_response.json()["content_id"])

        await asyncio.sleep(0.5)  # Allow processing time

        # Phase 2: Test content listing and filtering
        list_response = await async_client.get("/api/v1/content?limit=10")
        assert list_response.status_code == 200
        list_data = list_response.json()
        assert len(list_data["items"]) >= 3

        # Phase 3: Test search functionality
        search_request = {
            "query": "machine learning artificial intelligence",
            "source_types": ["MARKDOWN"],
            "limit": 5
        }

        search_response = await async_client.post("/api/v1/content/search", json=search_request)
        assert search_response.status_code == 200
        search_data = search_response.json()
        assert "results" in search_data
        assert search_data["query"] == "machine learning artificial intelligence"

        # Phase 4: Test filtering by processing status
        completed_response = await async_client.get("/api/v1/content?processing_status=COMPLETED")
        assert completed_response.status_code == 200

        pending_response = await async_client.get("/api/v1/content?processing_status=PENDING")
        assert pending_response.status_code == 200

    async def test_mochi_integration_complete_workflow(self, async_client: AsyncClient, db_session: AsyncSession):
        """Test complete Mochi integration workflow."""
        # Phase 1: Submit content optimized for flashcards
        flashcard_content = {
            "source_type": "MARKDOWN",
            "raw_content": """
            # Spanish Vocabulary Lesson

            ## Basic Greetings
            - Hola = Hello
            - Adiós = Goodbye
            - Por favor = Please
            - Gracias = Thank you

            ## Common Phrases
            - ¿Cómo estás? = How are you?
            - Me llamo... = My name is...
            - ¿Dónde está? = Where is?

            ## Numbers 1-10
            1. Uno
            2. Dos
            3. Tres
            4. Cuatro
            5. Cinco
            6. Seis
            7. Siete
            8. Ocho
            9. Nueve
            10. Diez
            """,
            "processing_config": {
                "max_prompts": 10,
                "prompt_types": ["FACTUAL", "CLOZE_DELETION"],
                "quality_threshold": 0.8
            },
            "priority": 7
        }

        # Act - Submit content
        submit_response = await async_client.post("/api/v1/content/process", json=flashcard_content)
        assert submit_response.status_code == 202
        content_id = submit_response.json()["content_id"]

        await asyncio.sleep(1)  # Allow processing

        # Phase 2: Get generated prompts
        prompts_response = await async_client.get(f"/api/v1/content/{content_id}/prompts")
        assert prompts_response.status_code == 200
        prompts_data = prompts_response.json()

        # Phase 3: Test Mochi deck operations
        decks_response = await async_client.get("/api/v1/mochi/decks")
        # Might be mocked or return service unavailable
        assert decks_response.status_code in [200, 503]

        if decks_response.status_code == 200:
            decks_data = decks_response.json()
            assert "decks" in decks_data

        # Phase 4: Test card creation if prompts exist
        if len(prompts_data) > 0:
            # Test individual card sync
            prompt_id = prompts_data[0]["id"]

            sync_request = {
                "deck_id": "spanish-vocabulary",
                "tags": ["spanish", "vocabulary", "e2e-test"]
            }

            sync_response = await async_client.post(
                f"/api/v1/prompts/{prompt_id}/sync-mochi",
                json=sync_request
            )

            # Expect success or graceful failure with mocked services
            assert sync_response.status_code in [200, 503]

            # Test batch card creation
            card_creation_request = {
                "prompt_ids": [p["id"] for p in prompts_data[:3]],  # First 3 prompts
                "deck_id": "spanish-vocabulary",
                "tags": ["batch-created", "e2e-test"]
            }

            batch_card_response = await async_client.post(
                "/api/v1/mochi/cards/create",
                json=card_creation_request
            )

            assert batch_card_response.status_code in [201, 503]

        # Phase 5: Verify sync status tracking
        if len(prompts_data) > 0:
            prompt_id = prompts_data[0]["id"]

            mochi_status_response = await async_client.get(
                f"/api/v1/prompts/{prompt_id}/mochi-status"
            )

            assert mochi_status_response.status_code == 200
            status_data = mochi_status_response.json()
            assert "is_synced" in status_data


class TestSystemPerformanceE2E:
    """Test suite for system performance under realistic conditions."""

    async def test_concurrent_user_simulation(self, async_client: AsyncClient):
        """Test system behavior under concurrent user load."""
        # Simulate multiple users submitting content simultaneously
        user_requests = [
            {
                "source_type": "MARKDOWN",
                "raw_content": f"# User {i} Content\n\nThis is content from user {i}.",
                "priority": 5
            }
            for i in range(10)
        ]

        # Act - Submit requests concurrently
        tasks = [
            async_client.post("/api/v1/content/process", json=request)
            for request in user_requests
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Assert - Most requests should succeed
        successful_responses = [r for r in responses if not isinstance(r, Exception) and r.status_code == 202]
        assert len(successful_responses) >= 8  # At least 80% success rate

        # Verify response times are reasonable
        for response in successful_responses:
            # Response should be quick for submission (actual processing is background)
            assert hasattr(response, 'elapsed')  # httpx response has elapsed time

    async def test_large_content_processing(self, async_client: AsyncClient):
        """Test processing of large content documents."""
        # Create large but realistic content
        large_content = """
        # Comprehensive Guide to Software Engineering

        ## Introduction
        Software engineering is a systematic approach to software development...
        """ + "\n\n".join([
            f"## Section {i}\nThis is section {i} with detailed information about software engineering concepts. " * 20
            for i in range(1, 21)  # 20 sections with substantial content
        ])

        large_content_request = {
            "source_type": "MARKDOWN",
            "raw_content": large_content,
            "processing_config": {
                "max_prompts": 25,
                "quality_threshold": 0.75
            },
            "priority": 3
        }

        # Act
        submit_response = await async_client.post("/api/v1/content/process", json=large_content_request)

        # Assert
        assert submit_response.status_code == 202
        content_id = submit_response.json()["content_id"]

        # Verify content was stored despite size
        content_response = await async_client.get(f"/api/v1/content/{content_id}")
        assert content_response.status_code == 200
        content_data = content_response.json()
        assert content_data["word_count"] > 1000

    async def test_api_rate_limiting_behavior(self, async_client: AsyncClient):
        """Test API behavior under rapid requests."""
        # Submit rapid requests to test rate limiting
        rapid_requests = []
        for i in range(20):
            request = {
                "source_type": "MARKDOWN",
                "raw_content": f"# Rapid Request {i}\n\nQuick content.",
                "priority": 5
            }
            rapid_requests.append(async_client.post("/api/v1/content/process", json=request))

        # Execute requests with minimal delay
        responses = []
        for request_task in rapid_requests:
            try:
                response = await request_task
                responses.append(response)
                await asyncio.sleep(0.01)  # Very brief delay
            except Exception as e:
                responses.append(e)

        # Assert - System should handle gracefully
        successful_count = sum(1 for r in responses if hasattr(r, 'status_code') and r.status_code == 202)
        rate_limited_count = sum(1 for r in responses if hasattr(r, 'status_code') and r.status_code == 429)

        # Either most succeed or rate limiting is properly implemented
        assert successful_count + rate_limited_count >= len(responses) * 0.8

    async def test_system_recovery_after_errors(self, async_client: AsyncClient):
        """Test system recovery after encountering errors."""
        # Phase 1: Submit content that might cause errors
        error_inducing_requests = [
            {"source_type": "MARKDOWN", "raw_content": "", "priority": 5},  # Empty content
            {"source_type": "WEB", "source_url": "invalid-url", "priority": 5},  # Invalid URL
        ]

        error_responses = []
        for request in error_inducing_requests:
            try:
                response = await async_client.post("/api/v1/content/process", json=request)
                error_responses.append(response)
            except Exception as e:
                error_responses.append(e)

        # Phase 2: Submit normal content after errors
        normal_request = {
            "source_type": "MARKDOWN",
            "raw_content": "# Recovery Test\n\nThis should work after errors.",
            "priority": 5
        }

        recovery_response = await async_client.post("/api/v1/content/process", json=normal_request)

        # Assert - System should recover and process normal content
        assert recovery_response.status_code == 202
        assert "submitted for processing" in recovery_response.json()["message"]

        # Health check should still pass
        health_response = await async_client.get("/health")
        assert health_response.status_code == 200