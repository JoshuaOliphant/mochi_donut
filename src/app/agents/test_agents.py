# Multi-Agent System Tests
"""
Comprehensive test suite for the multi-agent AI system.
Tests individual agents, workflow integration, and cost tracking.
"""

import pytest
import asyncio
import uuid
from datetime import datetime
from typing import Dict, Any, List
from unittest.mock import Mock, AsyncMock, patch

from .base import AgentBase, AgentState, CostTracker, AgentError
from .content_analyzer import ContentAnalyzerAgent
from .prompt_generator import PromptGeneratorAgent
from .quality_reviewer import QualityReviewerAgent
from .refinement_agent import RefinementAgent
from .orchestrator import OrchestratorAgent
from .workflow import PromptGenerationWorkflow
from .service import AgentOrchestratorService
from .config import agent_config


class TestAgentBase:
    """Test the base agent functionality."""

    @pytest.fixture
    def mock_agent(self):
        """Create a mock agent for testing."""
        class MockAgent(AgentBase):
            async def _execute_logic(self, state: AgentState) -> AgentState:
                # Simple mock implementation
                state["test_result"] = "success"
                return state

        return MockAgent(
            name="test_agent",
            model_name="gpt-5-mini",
            system_prompt="Test agent",
            max_retries=2
        )

    @pytest.mark.asyncio
    async def test_agent_execute_success(self, mock_agent):
        """Test successful agent execution."""
        state: AgentState = {
            "workflow_id": "test_workflow",
            "content_id": "test_content",
            "content_text": "Test content",
            "content_metadata": {},
            "started_at": datetime.now(),
            "current_step": "test",
            "iteration_count": 0,
            "max_iterations": 3,
            "quality_threshold": 0.7,
            "retry_count": 0,
            "max_retries": 3,
            "errors": [],
            "cost_tracker": CostTracker()
        }

        result = await mock_agent.execute(state)
        assert result["test_result"] == "success"
        assert result["current_step"] == "test_agent"

    @pytest.mark.asyncio
    async def test_agent_execute_with_retry(self, mock_agent):
        """Test agent execution with retry logic."""
        # Mock the agent to fail first time, succeed second time
        call_count = 0

        async def failing_logic(state):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("First attempt fails")
            state["test_result"] = "success_after_retry"
            return state

        mock_agent._execute_logic = failing_logic

        state: AgentState = {
            "workflow_id": "test_workflow",
            "content_id": "test_content",
            "content_text": "Test content",
            "content_metadata": {},
            "started_at": datetime.now(),
            "current_step": "test",
            "iteration_count": 0,
            "max_iterations": 3,
            "quality_threshold": 0.7,
            "retry_count": 0,
            "max_retries": 3,
            "errors": [],
            "cost_tracker": CostTracker()
        }

        result = await mock_agent.execute(state)
        assert result["test_result"] == "success_after_retry"
        assert call_count == 2
        assert len(result["errors"]) == 1


class TestCostTracker:
    """Test cost tracking functionality."""

    def test_cost_tracker_initialization(self):
        """Test cost tracker initialization."""
        tracker = CostTracker()
        assert tracker.total_cost == 0.0
        assert tracker.total_input_tokens == 0
        assert tracker.total_output_tokens == 0
        assert tracker.model_usage == {}

    def test_add_usage(self):
        """Test adding usage to cost tracker."""
        tracker = CostTracker()

        # Add usage for GPT-5-nano
        cost = tracker.add_usage("gpt-5-nano", 1000, 500)

        expected_cost = (1000 / 1_000_000) * 0.05 + (500 / 1_000_000) * 0.40
        assert abs(cost - expected_cost) < 0.0001
        assert tracker.total_cost == cost
        assert tracker.total_input_tokens == 1000
        assert tracker.total_output_tokens == 500

    def test_multiple_model_usage(self):
        """Test tracking usage across multiple models."""
        tracker = CostTracker()

        # Add usage for different models
        tracker.add_usage("gpt-5-nano", 1000, 500)
        tracker.add_usage("gpt-5-mini", 2000, 1000)

        assert len(tracker.model_usage) == 2
        assert "gpt-5-nano" in tracker.model_usage
        assert "gpt-5-mini" in tracker.model_usage

        summary = tracker.get_summary()
        assert summary["total_input_tokens"] == 3000
        assert summary["total_output_tokens"] == 1500


class TestContentAnalyzerAgent:
    """Test content analyzer agent."""

    @pytest.fixture
    def analyzer(self):
        return ContentAnalyzerAgent()

    @pytest.mark.asyncio
    async def test_content_analysis_preview(self, analyzer):
        """Test content analysis preview functionality."""
        content_text = """
        Machine learning is a subset of artificial intelligence that focuses on
        developing algorithms that can learn and make decisions from data.
        Key concepts include supervised learning, unsupervised learning, and
        reinforcement learning.
        """

        with patch.object(analyzer, '_call_llm') as mock_llm:
            # Mock LLM response
            from .content_analyzer import ConceptExtraction
            mock_response = ConceptExtraction(
                success=True,
                message="Analysis completed",
                confidence=0.85,
                key_concepts=[
                    "Machine learning",
                    "Artificial intelligence",
                    "Supervised learning",
                    "Unsupervised learning",
                    "Reinforcement learning"
                ],
                content_summary="Introduction to machine learning concepts and types",
                difficulty_level=3,
                content_type="educational_article",
                recommended_prompt_count=8,
                focus_areas=["Learning types", "AI relationship", "Algorithm concepts"]
            )
            mock_llm.return_value = mock_response

            result = await analyzer.analyze_content_preview(content_text)

            assert "key_concepts" in result
            assert len(result["key_concepts"]) == 5
            assert result["difficulty_level"] == 3
            assert result["recommended_prompt_count"] == 8


class TestPromptGeneratorAgent:
    """Test prompt generator agent."""

    @pytest.fixture
    def generator(self):
        return PromptGeneratorAgent()

    @pytest.mark.asyncio
    async def test_single_prompt_generation(self, generator):
        """Test generating a single prompt."""
        with patch.object(generator, '_call_llm') as mock_llm:
            from .prompt_generator import PromptGeneration, GeneratedPrompt

            mock_prompt = GeneratedPrompt(
                question="What is machine learning?",
                answer="Machine learning is a subset of AI that focuses on algorithms that learn from data",
                prompt_type="conceptual",
                confidence_score=0.9,
                difficulty_level=2,
                source_context="Introduction to AI concepts",
                tags=["AI", "machine learning", "concepts"],
                matuschak_principles=["focused_and_specific", "precise_language"]
            )

            mock_response = PromptGeneration(
                success=True,
                message="Generation completed",
                confidence=0.9,
                prompts=[mock_prompt],
                generation_strategy="concept_based",
                total_prompts=1,
                coverage_analysis={"concepts_covered": 1}
            )
            mock_llm.return_value = mock_response

            result = await generator.generate_single_prompt(
                concept="Machine learning",
                context="AI educational content",
                difficulty=2
            )

            assert result["question"] == "What is machine learning?"
            assert result["confidence_score"] == 0.9
            assert "AI" in result["tags"]


class TestQualityReviewerAgent:
    """Test quality reviewer agent."""

    @pytest.fixture
    def reviewer(self):
        return QualityReviewerAgent(quality_threshold=0.7)

    @pytest.mark.asyncio
    async def test_single_prompt_review(self, reviewer):
        """Test reviewing a single prompt."""
        prompt = {
            "question": "What is machine learning?",
            "answer": "A subset of AI that learns from data",
            "prompt_type": "conceptual",
            "difficulty_level": 2
        }

        with patch.object(reviewer, '_call_llm') as mock_llm:
            from .quality_reviewer import QualityReview, PromptQualityAssessment, QualityDimension

            mock_assessment = PromptQualityAssessment(
                prompt_index=0,
                overall_score=0.85,
                focused_and_specific=QualityDimension(
                    dimension="focused_and_specific",
                    score=0.9,
                    feedback="Well-focused question",
                    suggestions=[]
                ),
                precise_language=QualityDimension(
                    dimension="precise_language",
                    score=0.8,
                    feedback="Clear language",
                    suggestions=[]
                ),
                appropriate_cognitive_load=QualityDimension(
                    dimension="appropriate_cognitive_load",
                    score=0.85,
                    feedback="Appropriate complexity",
                    suggestions=[]
                ),
                meaningful_retrieval=QualityDimension(
                    dimension="meaningful_retrieval",
                    score=0.9,
                    feedback="Good for learning",
                    suggestions=[]
                ),
                contextual_cues=QualityDimension(
                    dimension="contextual_cues",
                    score=0.8,
                    feedback="Sufficient context",
                    suggestions=[]
                ),
                factual_accuracy=QualityDimension(
                    dimension="factual_accuracy",
                    score=0.9,
                    feedback="Accurate information",
                    suggestions=[]
                ),
                difficulty_appropriateness=QualityDimension(
                    dimension="difficulty_appropriateness",
                    score=0.85,
                    feedback="Appropriate difficulty",
                    suggestions=[]
                ),
                answer_completeness=QualityDimension(
                    dimension="answer_completeness",
                    score=0.8,
                    feedback="Complete answer",
                    suggestions=[]
                ),
                needs_revision=False,
                revision_priority="low",
                key_issues=[],
                strengths=["Clear question", "Good answer"]
            )

            mock_response = QualityReview(
                success=True,
                message="Review completed",
                confidence=0.9,
                assessments=[mock_assessment],
                batch_statistics={"average_score": 0.85},
                overall_batch_score=0.85,
                revision_recommendations=[],
                quality_trends={}
            )
            mock_llm.return_value = mock_response

            result = await reviewer.review_single_prompt(prompt)

            assert result["overall_score"] == 0.85
            assert not result["needs_revision"]
            assert "Clear question" in result["strengths"]


class TestWorkflowIntegration:
    """Test the complete workflow integration."""

    @pytest.fixture
    def workflow(self):
        return PromptGenerationWorkflow(quality_threshold=0.7, max_iterations=2)

    @pytest.mark.asyncio
    async def test_workflow_preview(self, workflow):
        """Test workflow preview functionality."""
        content_text = "Test content for preview"

        with patch.object(workflow.content_analyzer, 'analyze_content_preview') as mock_preview:
            mock_preview.return_value = {
                "key_concepts": ["concept1", "concept2"],
                "difficulty_level": 2,
                "recommended_prompt_count": 5
            }

            with patch.object(workflow.prompt_generator, 'generate_single_prompt') as mock_generate:
                mock_generate.return_value = {
                    "question": "Test question?",
                    "answer": "Test answer",
                    "confidence_score": 0.8
                }

                result = await workflow.execute_preview(content_text, max_prompts=3)

                assert result["status"] == "preview_completed"
                assert "analysis" in result
                assert "sample_prompt" in result
                assert result["estimated_prompts"] == 3


@pytest.mark.asyncio
async def test_full_workflow_execution():
    """Integration test for the complete workflow."""
    workflow = PromptGenerationWorkflow(quality_threshold=0.6, max_iterations=1)

    content_id = "test_content_123"
    content_text = """
    Python is a high-level programming language known for its simplicity and readability.
    It supports multiple programming paradigms including procedural, object-oriented,
    and functional programming. Python is widely used in web development, data science,
    artificial intelligence, and automation.
    """

    # Mock all agent calls to avoid actual LLM calls
    with patch.object(workflow.content_analyzer, 'execute') as mock_analyzer, \
         patch.object(workflow.prompt_generator, 'execute') as mock_generator, \
         patch.object(workflow.quality_reviewer, 'execute') as mock_reviewer:

        # Mock analyzer response
        async def mock_analyze(state):
            state["key_concepts"] = ["Python", "Programming paradigms", "Applications"]
            state["recommended_prompt_count"] = 5
            state["difficulty_level"] = 2
            return state
        mock_analyzer.side_effect = mock_analyze

        # Mock generator response
        async def mock_generate(state):
            state["generated_prompts"] = [
                {
                    "question": "What is Python?",
                    "answer": "A high-level programming language",
                    "prompt_type": "factual",
                    "confidence_score": 0.9
                }
            ]
            return state
        mock_generator.side_effect = mock_generate

        # Mock reviewer response
        async def mock_review(state):
            state["quality_scores"] = [{"overall_score": 0.8, "prompt_index": 0}]
            state["overall_quality_score"] = 0.8
            state["prompts_needing_revision"] = []
            return state
        mock_reviewer.side_effect = mock_review

        # Execute workflow
        result = await workflow.execute(content_id, content_text)

        assert result["status"] == "completed"
        assert len(result["prompts"]) == 1
        assert result["prompts"][0]["question"] == "What is Python?"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])