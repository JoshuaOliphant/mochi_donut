# Integration Tests for Content Processing Workflow
"""
Integration tests for complete content processing workflow from ingestion
to prompt generation, testing the full pipeline end-to-end.
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import Content, Prompt, AgentExecution, ProcessingStatus, SourceType, PromptType, AgentType
from app.repositories.content import ContentRepository
from app.repositories.prompt import PromptRepository
from app.services.content_processor import ContentProcessorService
from app.schemas.content import ContentProcessingRequest


class TestContentIngestionWorkflow:
    """Test suite for content ingestion and initial processing."""

    async def test_complete_url_processing_workflow(self, async_client: AsyncClient, db_session: AsyncSession):
        """Test complete workflow from URL submission to content storage."""
        # Arrange
        request_data = {
            "source_url": "https://httpbin.org/html",  # Reliable test URL
            "source_type": "WEB",
            "processing_config": {"max_prompts": 5},
            "priority": 5
        }

        # Act - Submit content for processing
        submit_response = await async_client.post("/api/v1/content/process", json=request_data)

        # Assert - Content submission successful
        assert submit_response.status_code == 202
        submit_data = submit_response.json()
        content_id = submit_data["content_id"]

        # Wait briefly for background processing to start
        await asyncio.sleep(0.1)

        # Verify content was created in database
        content_repo = ContentRepository(db_session)
        content = await content_repo.get(uuid.UUID(content_id))
        assert content is not None
        assert content.source_url == request_data["source_url"]
        assert content.source_type == SourceType.WEB
        assert content.processing_status in [ProcessingStatus.PENDING, ProcessingStatus.PROCESSING]

    async def test_raw_content_processing_workflow(self, async_client: AsyncClient, db_session: AsyncSession):
        """Test complete workflow with raw markdown content."""
        # Arrange
        markdown_content = """
        # Test-Driven Development Guide

        ## Introduction
        Test-Driven Development (TDD) is a software development methodology where tests are written before the actual code.

        ## Core Principles
        1. **Red**: Write a failing test
        2. **Green**: Write the minimal code to make the test pass
        3. **Refactor**: Improve the code while keeping tests green

        ## Benefits
        - Improved code quality
        - Better software design
        - Increased confidence in changes
        - Documentation through tests

        ## Best Practices
        - Keep tests simple and focused
        - Write one test at a time
        - Refactor regularly
        """

        request_data = {
            "source_type": "MARKDOWN",
            "raw_content": markdown_content,
            "processing_config": {"max_prompts": 8, "quality_threshold": 0.7},
            "priority": 3
        }

        # Act - Submit content for processing
        submit_response = await async_client.post("/api/v1/content/process", json=request_data)

        # Assert - Content submission successful
        assert submit_response.status_code == 202
        submit_data = submit_response.json()
        content_id = submit_data["content_id"]

        # Verify content properties
        content_repo = ContentRepository(db_session)
        content = await content_repo.get(uuid.UUID(content_id))
        assert content is not None
        assert content.markdown_content == markdown_content
        assert content.word_count > 0
        assert content.estimated_reading_time > 0
        assert "TDD" in content.markdown_content

    async def test_duplicate_content_detection(self, async_client: AsyncClient, db_session: AsyncSession):
        """Test that duplicate content is properly detected and handled."""
        # Arrange
        content_text = "# Unique Test Content\n\nThis content should be detected as duplicate."
        request_data = {
            "source_type": "MARKDOWN",
            "raw_content": content_text,
            "priority": 5
        }

        # Act - Submit same content twice
        first_response = await async_client.post("/api/v1/content/process", json=request_data)
        second_response = await async_client.post("/api/v1/content/process", json=request_data)

        # Assert
        assert first_response.status_code == 202
        assert second_response.status_code == 202

        first_data = first_response.json()
        second_data = second_response.json()

        # Should detect duplicate and reference existing content
        assert first_data["content_id"] == second_data["content_id"]
        assert "already exists" in second_data["message"]

    async def test_content_validation_errors(self, async_client: AsyncClient):
        """Test content validation and error handling."""
        # Test empty content
        empty_request = {
            "source_type": "MARKDOWN",
            "raw_content": "",
            "priority": 5
        }

        empty_response = await async_client.post("/api/v1/content/process", json=empty_request)
        assert empty_response.status_code == 422

        # Test missing source
        missing_source_request = {
            "source_type": "WEB",
            "priority": 5
            # Missing both source_url and raw_content
        }

        missing_response = await async_client.post("/api/v1/content/process", json=missing_source_request)
        assert missing_response.status_code == 422

        # Test invalid priority
        invalid_priority_request = {
            "source_type": "MARKDOWN",
            "raw_content": "# Valid content",
            "priority": 15  # Invalid: > 10
        }

        priority_response = await async_client.post("/api/v1/content/process", json=invalid_priority_request)
        assert priority_response.status_code == 422

    async def test_batch_content_processing_workflow(self, async_client: AsyncClient, db_session: AsyncSession):
        """Test batch processing of multiple content items."""
        # Arrange
        batch_request = {
            "items": [
                {
                    "source_type": "MARKDOWN",
                    "raw_content": "# Article 1\n\nContent about machine learning basics.",
                    "priority": 5
                },
                {
                    "source_type": "MARKDOWN",
                    "raw_content": "# Article 2\n\nAdvanced machine learning concepts.",
                    "priority": 3
                },
                {
                    "source_type": "MARKDOWN",
                    "raw_content": "# Article 3\n\nMachine learning in practice.",
                    "priority": 7
                }
            ],
            "batch_config": {"parallel_processing": True}
        }

        # Act
        batch_response = await async_client.post("/api/v1/content/batch", json=batch_request)

        # Assert
        assert batch_response.status_code == 202
        batch_data = batch_response.json()
        assert batch_data["total_items"] == 3
        assert batch_data["accepted_items"] <= 3
        assert len(batch_data["results"]) == 3

        # Verify all content items were created
        content_repo = ContentRepository(db_session)
        for result in batch_data["results"]:
            if result["processing_status"] != "FAILED":
                content = await content_repo.get(uuid.UUID(result["content_id"]))
                assert content is not None
                assert "machine learning" in content.markdown_content.lower()


class TestAIProcessingWorkflow:
    """Test suite for AI agent processing workflow."""

    @pytest.fixture
    async def processed_content(self, db_session: AsyncSession, sample_content_data):
        """Create content ready for AI processing."""
        content_data = {
            **sample_content_data,
            "processing_status": ProcessingStatus.PENDING,
            "markdown_content": """
            # Artificial Intelligence Fundamentals

            ## What is AI?
            Artificial Intelligence (AI) refers to the simulation of human intelligence in machines.

            ## Types of AI
            1. **Narrow AI**: Designed for specific tasks
            2. **General AI**: Human-level intelligence across domains
            3. **Super AI**: Intelligence exceeding human capabilities

            ## Machine Learning
            Machine Learning is a subset of AI that enables systems to learn from data.

            ### Supervised Learning
            - Uses labeled training data
            - Examples: classification, regression

            ### Unsupervised Learning
            - Finds patterns in unlabeled data
            - Examples: clustering, dimensionality reduction
            """,
            "content_hash": "ai_content_hash" + "x" * 48
        }

        content = Content(**content_data)
        db_session.add(content)
        await db_session.commit()
        await db_session.refresh(content)
        return content

    async def test_content_analysis_stage(self, db_session: AsyncSession, processed_content: Content):
        """Test content analysis and concept extraction stage."""
        # Arrange
        content_repo = ContentRepository(db_session)

        # Simulate content analysis agent execution
        analysis_execution = AgentExecution(
            content_id=processed_content.id,
            agent_type=AgentType.CONTENT_ANALYSIS,
            execution_id="analysis_test_123",
            step_number=1,
            status="completed",
            model_used="gpt-5-nano",
            input_tokens=150,
            output_tokens=80,
            execution_time_ms=1200,
            cost_usd=0.01,
            input_data={"content_length": len(processed_content.markdown_content)},
            output_data={
                "key_concepts": [
                    {"concept": "Artificial Intelligence", "importance": 0.95},
                    {"concept": "Machine Learning", "importance": 0.90},
                    {"concept": "Supervised Learning", "importance": 0.75},
                    {"concept": "Unsupervised Learning", "importance": 0.70}
                ],
                "complexity_level": "intermediate",
                "estimated_prompts": 8
            }
        )

        db_session.add(analysis_execution)
        await db_session.commit()

        # Act - Verify analysis results
        executions = await content_repo.get_agent_executions(processed_content.id)
        analysis_exec = next((e for e in executions if e.agent_type == AgentType.CONTENT_ANALYSIS), None)

        # Assert
        assert analysis_exec is not None
        assert analysis_exec.status == "completed"
        assert "key_concepts" in analysis_exec.output_data
        assert len(analysis_exec.output_data["key_concepts"]) == 4
        assert analysis_exec.cost_usd > 0

    async def test_prompt_generation_stage(self, db_session: AsyncSession, processed_content: Content):
        """Test prompt generation from extracted concepts."""
        # Arrange
        prompt_repo = PromptRepository(db_session)

        # Simulate generated prompts based on content
        generated_prompts = [
            {
                "content_id": processed_content.id,
                "question": "What does AI stand for and what does it refer to?",
                "answer": "AI stands for Artificial Intelligence and refers to the simulation of human intelligence in machines.",
                "prompt_type": PromptType.FACTUAL,
                "confidence_score": 0.92,
                "difficulty_level": 2,
                "source_context": "Introduction section about AI definition"
            },
            {
                "content_id": processed_content.id,
                "question": "Explain the three main types of AI and their characteristics.",
                "answer": "The three types are: 1) Narrow AI - designed for specific tasks, 2) General AI - human-level intelligence across domains, 3) Super AI - intelligence exceeding human capabilities.",
                "prompt_type": PromptType.CONCEPTUAL,
                "confidence_score": 0.88,
                "difficulty_level": 3,
                "source_context": "Types of AI section"
            },
            {
                "content_id": processed_content.id,
                "question": "Compare supervised and unsupervised learning approaches.",
                "answer": "Supervised learning uses labeled training data for tasks like classification and regression, while unsupervised learning finds patterns in unlabeled data for tasks like clustering and dimensionality reduction.",
                "prompt_type": PromptType.CONCEPTUAL,
                "confidence_score": 0.85,
                "difficulty_level": 4,
                "source_context": "Machine Learning subsections"
            }
        ]

        # Create prompts in database
        for prompt_data in generated_prompts:
            prompt = Prompt(**prompt_data)
            db_session.add(prompt)

        await db_session.commit()

        # Act - Verify prompts were generated
        content_prompts = await prompt_repo.get_by_content_id(processed_content.id)

        # Assert
        assert len(content_prompts) >= 3
        assert any(p.prompt_type == PromptType.FACTUAL for p in content_prompts)
        assert any(p.prompt_type == PromptType.CONCEPTUAL for p in content_prompts)
        assert all(p.confidence_score >= 0.8 for p in content_prompts)

    async def test_quality_review_stage(self, db_session: AsyncSession, sample_prompt: Prompt):
        """Test quality review and validation stage."""
        # Arrange - Create quality metrics for the prompt
        from app.db.models import QualityMetric, QualityMetricType

        quality_metrics = [
            QualityMetric(
                prompt_id=sample_prompt.id,
                metric_type=QualityMetricType.FOCUS_SPECIFICITY,
                score=0.85,
                weight=1.0,
                evaluator_model="gpt-5-standard",
                reasoning="Question is focused on specific AI concepts"
            ),
            QualityMetric(
                prompt_id=sample_prompt.id,
                metric_type=QualityMetricType.PRECISION_CLARITY,
                score=0.90,
                weight=1.0,
                evaluator_model="gpt-5-standard",
                reasoning="Answer is clear and precise"
            ),
            QualityMetric(
                prompt_id=sample_prompt.id,
                metric_type=QualityMetricType.OVERALL_QUALITY,
                score=0.87,
                weight=1.0,
                evaluator_model="gpt-5-standard",
                reasoning="High quality prompt meeting Matuschak principles"
            )
        ]

        for metric in quality_metrics:
            db_session.add(metric)

        await db_session.commit()

        # Act - Verify quality metrics
        await db_session.refresh(sample_prompt)

        # Assert
        assert len(sample_prompt.quality_metrics) >= 3
        overall_metric = next((m for m in sample_prompt.quality_metrics
                              if m.metric_type == QualityMetricType.OVERALL_QUALITY), None)
        assert overall_metric is not None
        assert overall_metric.score >= 0.8

    async def test_processing_completion_workflow(self, db_session: AsyncSession, processed_content: Content):
        """Test complete processing workflow from start to finish."""
        # Arrange
        content_repo = ContentRepository(db_session)

        # Act - Update content to completed status
        await content_repo.update(processed_content.id, {
            "processing_status": ProcessingStatus.COMPLETED,
            "processed_at": datetime.now(timezone.utc),
            "metadata": {
                **processed_content.metadata,
                "processing_completed": True,
                "total_prompts_generated": 5,
                "average_quality_score": 0.87,
                "processing_duration_ms": 3500
            }
        })

        # Verify completion
        completed_content = await content_repo.get(processed_content.id)

        # Assert
        assert completed_content.processing_status == ProcessingStatus.COMPLETED
        assert completed_content.processed_at is not None
        assert completed_content.metadata["processing_completed"] is True
        assert completed_content.metadata["total_prompts_generated"] == 5
        assert completed_content.metadata["average_quality_score"] >= 0.8


class TestErrorRecoveryWorkflow:
    """Test suite for error handling and recovery in processing workflow."""

    async def test_processing_failure_handling(self, db_session: AsyncSession, sample_content_data):
        """Test handling of processing failures."""
        # Arrange - Create content with failed processing
        failed_content_data = {
            **sample_content_data,
            "processing_status": ProcessingStatus.FAILED,
            "content_hash": "failed_content_hash" + "x" * 46,
            "metadata": {
                "error": "AI service timeout",
                "failed_at": datetime.now(timezone.utc).isoformat(),
                "retry_count": 2
            }
        }

        content = Content(**failed_content_data)
        db_session.add(content)
        await db_session.commit()

        # Act - Verify failure state
        content_repo = ContentRepository(db_session)
        failed_content = await content_repo.get(content.id)

        # Assert
        assert failed_content.processing_status == ProcessingStatus.FAILED
        assert "error" in failed_content.metadata
        assert failed_content.metadata["retry_count"] == 2

    async def test_agent_execution_failure_tracking(self, db_session: AsyncSession, sample_content: Content):
        """Test tracking of individual agent execution failures."""
        # Arrange - Create failed agent execution
        failed_execution = AgentExecution(
            content_id=sample_content.id,
            agent_type=AgentType.PROMPT_GENERATION,
            execution_id="failed_exec_456",
            step_number=2,
            status="failed",
            model_used="gpt-5-mini",
            input_tokens=200,
            execution_time_ms=5000,
            error_message="Rate limit exceeded",
            input_data={"concepts": ["AI", "ML"]},
            metadata={"retry_attempt": 1}
        )

        db_session.add(failed_execution)
        await db_session.commit()

        # Act - Verify failure tracking
        content_repo = ContentRepository(db_session)
        executions = await content_repo.get_agent_executions(sample_content.id)
        failed_exec = next((e for e in executions if e.status == "failed"), None)

        # Assert
        assert failed_exec is not None
        assert failed_exec.error_message == "Rate limit exceeded"
        assert failed_exec.metadata["retry_attempt"] == 1

    async def test_partial_processing_recovery(self, db_session: AsyncSession, sample_content: Content):
        """Test recovery from partial processing failures."""
        # Arrange - Simulate partial processing state
        content_repo = ContentRepository(db_session)

        # Update content to processing state
        await content_repo.update(sample_content.id, {
            "processing_status": ProcessingStatus.PROCESSING,
            "metadata": {
                "analysis_completed": True,
                "generation_completed": False,
                "quality_review_completed": False,
                "last_step": "content_analysis"
            }
        })

        # Act - Verify partial state
        partial_content = await content_repo.get(sample_content.id)

        # Assert
        assert partial_content.processing_status == ProcessingStatus.PROCESSING
        assert partial_content.metadata["analysis_completed"] is True
        assert partial_content.metadata["generation_completed"] is False
        assert partial_content.metadata["last_step"] == "content_analysis"


class TestWorkflowPerformance:
    """Test suite for workflow performance and scalability."""

    async def test_processing_time_tracking(self, db_session: AsyncSession, sample_content: Content):
        """Test tracking of processing time metrics."""
        # Arrange
        start_time = datetime.now(timezone.utc)

        # Simulate timed executions
        agent_executions = [
            AgentExecution(
                content_id=sample_content.id,
                agent_type=AgentType.CONTENT_ANALYSIS,
                execution_id="perf_test_1",
                step_number=1,
                status="completed",
                execution_time_ms=1200,
                started_at=start_time,
                completed_at=start_time + timedelta(milliseconds=1200)
            ),
            AgentExecution(
                content_id=sample_content.id,
                agent_type=AgentType.PROMPT_GENERATION,
                execution_id="perf_test_1",
                step_number=2,
                status="completed",
                execution_time_ms=2800,
                started_at=start_time + timedelta(milliseconds=1200),
                completed_at=start_time + timedelta(milliseconds=4000)
            )
        ]

        for execution in agent_executions:
            db_session.add(execution)

        await db_session.commit()

        # Act - Calculate total processing time
        total_time = sum(e.execution_time_ms for e in agent_executions)

        # Assert
        assert total_time == 4000  # 1200 + 2800 ms
        assert all(e.completed_at > e.started_at for e in agent_executions)

    async def test_cost_tracking_workflow(self, db_session: AsyncSession, sample_content: Content):
        """Test tracking of processing costs."""
        # Arrange - Create executions with cost data
        cost_executions = [
            AgentExecution(
                content_id=sample_content.id,
                agent_type=AgentType.CONTENT_ANALYSIS,
                execution_id="cost_test_1",
                step_number=1,
                status="completed",
                model_used="gpt-5-nano",
                input_tokens=100,
                output_tokens=50,
                cost_usd=0.005  # Based on nano pricing
            ),
            AgentExecution(
                content_id=sample_content.id,
                agent_type=AgentType.PROMPT_GENERATION,
                execution_id="cost_test_1",
                step_number=2,
                status="completed",
                model_used="gpt-5-mini",
                input_tokens=200,
                output_tokens=120,
                cost_usd=0.025  # Based on mini pricing
            )
        ]

        for execution in cost_executions:
            db_session.add(execution)

        await db_session.commit()

        # Act - Calculate total cost
        total_cost = sum(e.cost_usd for e in cost_executions)

        # Assert
        assert total_cost == 0.030  # $0.005 + $0.025
        assert all(e.cost_usd > 0 for e in cost_executions)

    async def test_concurrent_processing_workflow(self, async_client: AsyncClient):
        """Test concurrent processing of multiple content items."""
        # Arrange
        concurrent_requests = [
            {
                "source_type": "MARKDOWN",
                "raw_content": f"# Concurrent Content {i}\n\nTest content for concurrent processing.",
                "priority": 5
            }
            for i in range(3)
        ]

        # Act - Submit requests concurrently
        tasks = [
            async_client.post("/api/v1/content/process", json=request)
            for request in concurrent_requests
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Assert
        successful_responses = [r for r in responses if not isinstance(r, Exception)]
        assert len(successful_responses) >= 1

        for response in successful_responses:
            assert response.status_code == 202
            data = response.json()
            assert "content_id" in data
            assert data["processing_status"] == "PENDING"