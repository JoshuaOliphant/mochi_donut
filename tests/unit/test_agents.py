# Unit Tests for AI Agents - DEPRECATED
"""
DEPRECATED: These tests are for legacy LangChain/LangGraph agents that have been removed.

The system has migrated to Claude Agent SDK. For current agent tests, see:
- tests/unit/test_claude_agents.py (New Claude SDK agent tests)
- tests/integration/test_content_processor.py (ContentProcessorService integration tests)

Legacy agents removed:
- OrchestratorAgent (replaced by ContentProcessorService)
- ContentAnalysisAgent (replaced by 'content-analyzer' subagent)
- PromptGenerationAgent (replaced by 'prompt-generator' subagent)
- QualityReviewAgent (replaced by 'quality-reviewer' subagent)
- RefinementAgent (replaced by 'refinement-agent' subagent)

This file is kept temporarily for reference but will be removed in Phase 1 cleanup.
"""

import pytest
from datetime import datetime, timezone
from typing import Dict, Any, List
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

# DEPRECATED: Legacy LangGraph agents removed
# from app.agents.orchestrator import OrchestratorAgent
# from app.agents.content_analyzer import ContentAnalysisAgent
# from app.agents.prompt_generator import PromptGenerationAgent
# from app.agents.quality_reviewer import QualityReviewAgent
# from app.agents.refinement_agent import RefinementAgent
from app.agents.service import AgentService
from app.agents.config import AgentConfig
from app.db.models import Content, Prompt, AgentExecution, AgentType, PromptType
from app.integrations.openai_client import OpenAIClient
from app.repositories.content import ContentRepository
from app.repositories.prompt import PromptRepository

# Mark all tests in this file as skip with deprecation message
pytestmark = pytest.mark.skip(
    reason="Legacy LangGraph agent tests deprecated. Use test_claude_agents.py for Claude SDK tests."
)


class TestOrchestratorAgent:
    """Test suite for OrchestratorAgent coordination logic."""

    @pytest.fixture
    def mock_openai_client(self):
        """Mock OpenAI client."""
        client = AsyncMock(spec=OpenAIClient)
        return client

    @pytest.fixture
    def mock_agent_config(self):
        """Mock agent configuration."""
        config = AgentConfig(
            model_name="gpt-5-nano",
            temperature=0.1,
            max_tokens=1000,
            timeout_seconds=30
        )
        return config

    @pytest.fixture
    def orchestrator_agent(self, mock_openai_client, mock_agent_config):
        """Create OrchestratorAgent with mocked dependencies."""
        return OrchestratorAgent(
            openai_client=mock_openai_client,
            config=mock_agent_config
        )

    async def test_orchestrate_content_processing(self, orchestrator_agent, sample_content):
        """Test orchestrating complete content processing pipeline."""
        # Arrange
        processing_config = {
            "max_prompts": 10,
            "quality_threshold": 0.8,
            "enable_refinement": True
        }

        # Mock the orchestration result
        mock_result = {
            "execution_id": "exec_123",
            "content_id": str(sample_content.id),
            "steps_completed": [
                "content_analysis",
                "prompt_generation",
                "quality_review",
                "refinement"
            ],
            "prompts_generated": 8,
            "average_quality_score": 0.85,
            "processing_time_ms": 3500,
            "status": "completed"
        }

        with patch.object(orchestrator_agent, '_execute_processing_pipeline', return_value=mock_result):
            # Act
            result = await orchestrator_agent.orchestrate_content_processing(
                sample_content,
                processing_config
            )

            # Assert
            assert result["status"] == "completed"
            assert result["prompts_generated"] == 8
            assert result["average_quality_score"] == 0.85
            assert len(result["steps_completed"]) == 4

    async def test_determine_processing_strategy(self, orchestrator_agent, sample_content):
        """Test determining optimal processing strategy based on content."""
        # Arrange
        sample_content.word_count = 1500
        sample_content.source_type = "WEB"
        sample_content.metadata = {"complexity": "medium"}

        # Act
        strategy = await orchestrator_agent.determine_processing_strategy(sample_content)

        # Assert
        assert "max_prompts" in strategy
        assert "quality_threshold" in strategy
        assert "parallel_processing" in strategy
        assert isinstance(strategy["max_prompts"], int)
        assert 0.0 <= strategy["quality_threshold"] <= 1.0

    async def test_monitor_agent_performance(self, orchestrator_agent):
        """Test monitoring individual agent performance."""
        # Arrange
        execution_id = "exec_123"
        agent_executions = [
            AgentExecution(
                agent_type=AgentType.CONTENT_ANALYSIS,
                execution_id=execution_id,
                step_number=1,
                status="completed",
                execution_time_ms=1200,
                input_tokens=150,
                output_tokens=80
            ),
            AgentExecution(
                agent_type=AgentType.PROMPT_GENERATION,
                execution_id=execution_id,
                step_number=2,
                status="completed",
                execution_time_ms=2800,
                input_tokens=200,
                output_tokens=120
            )
        ]

        # Act
        performance_metrics = orchestrator_agent.analyze_agent_performance(agent_executions)

        # Assert
        assert "total_execution_time" in performance_metrics
        assert "agent_breakdown" in performance_metrics
        assert performance_metrics["total_execution_time"] == 4000  # 1200 + 2800
        assert len(performance_metrics["agent_breakdown"]) == 2

    async def test_handle_agent_failure(self, orchestrator_agent):
        """Test handling individual agent failures."""
        # Arrange
        failed_execution = AgentExecution(
            agent_type=AgentType.PROMPT_GENERATION,
            execution_id="exec_fail",
            step_number=2,
            status="failed",
            error_message="Token limit exceeded"
        )

        # Act
        recovery_strategy = orchestrator_agent.determine_recovery_strategy(failed_execution)

        # Assert
        assert "action" in recovery_strategy
        assert "retry_config" in recovery_strategy
        assert recovery_strategy["action"] in ["retry", "skip", "fallback"]

    async def test_resource_optimization(self, orchestrator_agent, sample_content):
        """Test AI model selection and resource optimization."""
        # Arrange
        content_complexity = {
            "word_count": sample_content.word_count,
            "reading_level": "intermediate",
            "technical_content": True
        }

        # Act
        model_selection = orchestrator_agent.optimize_model_selection(content_complexity)

        # Assert
        assert "analysis_model" in model_selection
        assert "generation_model" in model_selection
        assert "review_model" in model_selection
        assert model_selection["analysis_model"] in ["gpt-5-nano", "gpt-5-mini", "gpt-5-standard"]


class TestContentAnalysisAgent:
    """Test suite for ContentAnalysisAgent concept extraction."""

    @pytest.fixture
    def mock_openai_client(self):
        """Mock OpenAI client."""
        client = AsyncMock(spec=OpenAIClient)
        return client

    @pytest.fixture
    def content_analysis_agent(self, mock_openai_client):
        """Create ContentAnalysisAgent with mocked dependencies."""
        return ContentAnalysisAgent(openai_client=mock_openai_client)

    async def test_extract_key_concepts(self, content_analysis_agent, mock_openai_client, sample_content):
        """Test extracting key concepts from content."""
        # Arrange
        mock_analysis_result = {
            "key_concepts": [
                {
                    "concept": "Test-Driven Development",
                    "importance": 0.95,
                    "context": "Primary software development methodology",
                    "related_terms": ["TDD", "unit testing", "red-green-refactor"]
                },
                {
                    "concept": "Unit Testing",
                    "importance": 0.85,
                    "context": "Foundation of TDD approach",
                    "related_terms": ["test cases", "assertions", "mocking"]
                }
            ],
            "content_complexity": "intermediate",
            "learning_objectives": [
                "Understand TDD principles",
                "Apply TDD in development"
            ],
            "estimated_learning_time": 30  # minutes
        }

        mock_openai_client.analyze_content.return_value = mock_analysis_result

        # Act
        result = await content_analysis_agent.extract_key_concepts(sample_content)

        # Assert
        assert len(result["key_concepts"]) == 2
        assert result["key_concepts"][0]["concept"] == "Test-Driven Development"
        assert result["key_concepts"][0]["importance"] == 0.95
        assert result["content_complexity"] == "intermediate"

        # Verify OpenAI was called with correct parameters
        mock_openai_client.analyze_content.assert_called_once()
        call_args = mock_openai_client.analyze_content.call_args[0]
        assert sample_content.markdown_content in str(call_args)

    async def test_identify_learning_objectives(self, content_analysis_agent, mock_openai_client, sample_content):
        """Test identifying learning objectives from content."""
        # Arrange
        mock_objectives_result = {
            "primary_objectives": [
                "Understand the principles of Test-Driven Development",
                "Learn the red-green-refactor cycle"
            ],
            "secondary_objectives": [
                "Apply TDD in real projects",
                "Write effective unit tests"
            ],
            "prerequisite_knowledge": [
                "Basic programming concepts",
                "Understanding of software testing"
            ],
            "difficulty_level": 3,  # 1-5 scale
            "estimated_mastery_time": "2-3 hours"
        }

        mock_openai_client.identify_learning_objectives.return_value = mock_objectives_result

        # Act
        result = await content_analysis_agent.identify_learning_objectives(sample_content)

        # Assert
        assert len(result["primary_objectives"]) == 2
        assert len(result["secondary_objectives"]) == 2
        assert result["difficulty_level"] == 3
        assert "TDD" in result["primary_objectives"][0]

    async def test_analyze_content_structure(self, content_analysis_agent, sample_content):
        """Test analyzing content structure and organization."""
        # Arrange
        sample_content.markdown_content = """
        # Main Topic: Test-Driven Development

        ## Introduction
        TDD is a development methodology...

        ## Core Principles
        1. Write failing test
        2. Write minimal code
        3. Refactor

        ## Benefits
        - Better code quality
        - Reduced bugs

        ## Examples
        ```python
        def test_example():
            assert True
        ```
        """

        # Act
        structure_analysis = content_analysis_agent.analyze_content_structure(sample_content)

        # Assert
        assert "sections" in structure_analysis
        assert "code_examples" in structure_analysis
        assert "lists" in structure_analysis
        assert structure_analysis["sections"] >= 4  # Main topic + 4 sections
        assert structure_analysis["code_examples"] >= 1

    async def test_extract_concepts_with_context(self, content_analysis_agent, mock_openai_client, sample_content):
        """Test extracting concepts with contextual information."""
        # Arrange
        mock_contextual_result = {
            "concepts_with_context": [
                {
                    "concept": "Red-Green-Refactor",
                    "definition": "The three-phase TDD cycle",
                    "context_in_document": "Core methodology section",
                    "learning_importance": "high",
                    "conceptual_relationships": ["TDD", "Unit Testing"],
                    "example_usage": "Write failing test (red), make it pass (green), improve code (refactor)"
                }
            ],
            "concept_map": {
                "TDD": ["Red-Green-Refactor", "Unit Testing", "Code Quality"],
                "Testing": ["Assertions", "Mocking", "Test Cases"]
            }
        }

        mock_openai_client.extract_concepts_with_context.return_value = mock_contextual_result

        # Act
        result = await content_analysis_agent.extract_concepts_with_context(sample_content)

        # Assert
        assert "concepts_with_context" in result
        assert "concept_map" in result
        assert result["concepts_with_context"][0]["learning_importance"] == "high"
        assert "TDD" in result["concept_map"]


class TestPromptGenerationAgent:
    """Test suite for PromptGenerationAgent prompt creation."""

    @pytest.fixture
    def mock_openai_client(self):
        """Mock OpenAI client."""
        client = AsyncMock(spec=OpenAIClient)
        return client

    @pytest.fixture
    def prompt_generation_agent(self, mock_openai_client):
        """Create PromptGenerationAgent with mocked dependencies."""
        return PromptGenerationAgent(openai_client=mock_openai_client)

    async def test_generate_prompts_from_concepts(self, prompt_generation_agent, mock_openai_client):
        """Test generating prompts from extracted concepts."""
        # Arrange
        concepts = [
            {
                "concept": "Test-Driven Development",
                "importance": 0.95,
                "context": "Primary methodology"
            },
            {
                "concept": "Red-Green-Refactor",
                "importance": 0.85,
                "context": "TDD cycle"
            }
        ]

        mock_prompts_result = {
            "generated_prompts": [
                {
                    "question": "What are the three phases of the TDD cycle?",
                    "answer": "The three phases are: Red (write failing test), Green (make test pass), Refactor (improve code)",
                    "type": "factual",
                    "concept": "Red-Green-Refactor",
                    "difficulty": 2,
                    "confidence": 0.9
                },
                {
                    "question": "Explain the benefits of Test-Driven Development.",
                    "answer": "TDD benefits include better code quality, reduced bugs, improved design, and increased confidence in changes",
                    "type": "conceptual",
                    "concept": "Test-Driven Development",
                    "difficulty": 3,
                    "confidence": 0.85
                }
            ],
            "generation_metadata": {
                "total_concepts_processed": 2,
                "prompts_per_concept": {"Test-Driven Development": 1, "Red-Green-Refactor": 1},
                "generation_time_ms": 2500
            }
        }

        mock_openai_client.generate_prompts_from_concepts.return_value = mock_prompts_result

        # Act
        result = await prompt_generation_agent.generate_prompts_from_concepts(
            concepts,
            max_prompts=10
        )

        # Assert
        assert len(result["generated_prompts"]) == 2
        assert result["generated_prompts"][0]["type"] == "factual"
        assert result["generated_prompts"][1]["type"] == "conceptual"
        assert result["generation_metadata"]["total_concepts_processed"] == 2

    async def test_generate_different_prompt_types(self, prompt_generation_agent, mock_openai_client):
        """Test generating different types of prompts."""
        # Arrange
        concept = {
            "concept": "Unit Testing",
            "context": "Testing individual components"
        }

        prompt_types = [PromptType.FACTUAL, PromptType.PROCEDURAL, PromptType.CONCEPTUAL]

        for prompt_type in prompt_types:
            mock_result = {
                "question": f"Test {prompt_type.value} question",
                "answer": f"Test {prompt_type.value} answer",
                "type": prompt_type.value,
                "confidence": 0.8
            }

            mock_openai_client.generate_specific_prompt_type.return_value = mock_result

            # Act
            result = await prompt_generation_agent.generate_specific_prompt_type(
                concept,
                prompt_type
            )

            # Assert
            assert result["type"] == prompt_type.value
            assert f"{prompt_type.value}" in result["question"]

    async def test_adjust_prompt_difficulty(self, prompt_generation_agent, mock_openai_client):
        """Test adjusting prompt difficulty levels."""
        # Arrange
        base_prompt = {
            "question": "What is TDD?",
            "answer": "Test-Driven Development",
            "difficulty": 1
        }

        target_difficulties = [2, 3, 4, 5]

        for difficulty in target_difficulties:
            mock_adjusted = {
                **base_prompt,
                "question": f"Level {difficulty} TDD question",
                "answer": f"Level {difficulty} detailed answer",
                "difficulty": difficulty
            }

            mock_openai_client.adjust_prompt_difficulty.return_value = mock_adjusted

            # Act
            result = await prompt_generation_agent.adjust_prompt_difficulty(
                base_prompt,
                target_difficulty=difficulty
            )

            # Assert
            assert result["difficulty"] == difficulty
            assert f"Level {difficulty}" in result["question"]

    async def test_generate_cloze_deletion_prompts(self, prompt_generation_agent, mock_openai_client):
        """Test generating cloze deletion style prompts."""
        # Arrange
        content_sentence = "Test-Driven Development follows the red-green-refactor cycle."

        mock_cloze_result = {
            "cloze_prompts": [
                {
                    "question": "Test-Driven Development follows the ___-___-___ cycle.",
                    "answer": "red-green-refactor",
                    "type": "cloze_deletion",
                    "difficulty": 2
                },
                {
                    "question": "___ follows the red-green-refactor cycle.",
                    "answer": "Test-Driven Development",
                    "type": "cloze_deletion",
                    "difficulty": 1
                }
            ]
        }

        mock_openai_client.generate_cloze_deletion.return_value = mock_cloze_result

        # Act
        result = await prompt_generation_agent.generate_cloze_deletion_prompts(
            content_sentence,
            num_variations=2
        )

        # Assert
        assert len(result["cloze_prompts"]) == 2
        assert all(p["type"] == "cloze_deletion" for p in result["cloze_prompts"])
        assert "___" in result["cloze_prompts"][0]["question"]


class TestQualityReviewAgent:
    """Test suite for QualityReviewAgent prompt validation."""

    @pytest.fixture
    def mock_openai_client(self):
        """Mock OpenAI client."""
        client = AsyncMock(spec=OpenAIClient)
        return client

    @pytest.fixture
    def quality_review_agent(self, mock_openai_client):
        """Create QualityReviewAgent with mocked dependencies."""
        return QualityReviewAgent(openai_client=mock_openai_client)

    async def test_evaluate_prompt_quality(self, quality_review_agent, mock_openai_client, sample_prompt):
        """Test evaluating individual prompt quality."""
        # Arrange
        mock_evaluation = {
            "quality_metrics": {
                "focus_specificity": 0.85,
                "precision_clarity": 0.90,
                "cognitive_load": 0.75,
                "retrieval_practice": 0.80,
                "overall_quality": 0.82
            },
            "matuschak_compliance": {
                "focused_and_specific": True,
                "precise_language": True,
                "appropriate_cognitive_load": True,
                "enables_retrieval_practice": True,
                "score": 0.85
            },
            "feedback": {
                "strengths": [
                    "Clear and specific question",
                    "Precise answer without ambiguity"
                ],
                "improvements": [
                    "Could include more challenging follow-up",
                    "Consider adding context"
                ],
                "recommendation": "approve_with_minor_edits"
            }
        }

        mock_openai_client.evaluate_prompt_quality.return_value = mock_evaluation

        # Act
        result = await quality_review_agent.evaluate_prompt_quality(sample_prompt)

        # Assert
        assert result["quality_metrics"]["overall_quality"] == 0.82
        assert result["matuschak_compliance"]["score"] == 0.85
        assert len(result["feedback"]["strengths"]) == 2
        assert result["feedback"]["recommendation"] == "approve_with_minor_edits"

    async def test_batch_quality_review(self, quality_review_agent, mock_openai_client):
        """Test batch quality review of multiple prompts."""
        # Arrange
        prompts = [
            Prompt(id=uuid.uuid4(), question="Question 1", answer="Answer 1"),
            Prompt(id=uuid.uuid4(), question="Question 2", answer="Answer 2"),
            Prompt(id=uuid.uuid4(), question="Question 3", answer="Answer 3")
        ]

        mock_batch_evaluation = {
            "batch_results": [
                {"prompt_id": str(prompts[0].id), "overall_quality": 0.85, "recommendation": "approve"},
                {"prompt_id": str(prompts[1].id), "overall_quality": 0.65, "recommendation": "needs_revision"},
                {"prompt_id": str(prompts[2].id), "overall_quality": 0.90, "recommendation": "approve"}
            ],
            "batch_statistics": {
                "average_quality": 0.8,
                "approval_rate": 0.67,
                "needs_revision_count": 1,
                "total_prompts": 3
            }
        }

        mock_openai_client.batch_evaluate_prompts.return_value = mock_batch_evaluation

        # Act
        result = await quality_review_agent.batch_quality_review(prompts)

        # Assert
        assert len(result["batch_results"]) == 3
        assert result["batch_statistics"]["average_quality"] == 0.8
        assert result["batch_statistics"]["approval_rate"] == 0.67

    async def test_check_matuschak_principles(self, quality_review_agent, sample_prompt):
        """Test checking compliance with Andy Matuschak's principles."""
        # Act
        compliance_check = quality_review_agent.check_matuschak_principles(sample_prompt)

        # Assert
        assert "focused_and_specific" in compliance_check
        assert "precise_language" in compliance_check
        assert "appropriate_cognitive_load" in compliance_check
        assert "enables_retrieval_practice" in compliance_check
        assert isinstance(compliance_check["focused_and_specific"], bool)

    async def test_identify_quality_issues(self, quality_review_agent):
        """Test identifying specific quality issues in prompts."""
        # Arrange
        problematic_prompt = Prompt(
            id=uuid.uuid4(),
            question="What is it?",  # Too vague
            answer="It is a thing.",  # Too vague
            prompt_type=PromptType.FACTUAL
        )

        # Act
        issues = quality_review_agent.identify_quality_issues(problematic_prompt)

        # Assert
        assert "vague_question" in issues
        assert "ambiguous_answer" in issues
        assert len(issues) >= 2


class TestRefinementAgent:
    """Test suite for RefinementAgent prompt improvement."""

    @pytest.fixture
    def mock_openai_client(self):
        """Mock OpenAI client."""
        client = AsyncMock(spec=OpenAIClient)
        return client

    @pytest.fixture
    def refinement_agent(self, mock_openai_client):
        """Create RefinementAgent with mocked dependencies."""
        return RefinementAgent(openai_client=mock_openai_client)

    async def test_refine_prompt_based_on_feedback(self, refinement_agent, mock_openai_client, sample_prompt):
        """Test refining prompt based on quality feedback."""
        # Arrange
        quality_feedback = {
            "strengths": ["Clear question structure"],
            "improvements": [
                "Make question more specific",
                "Add context to answer",
                "Increase difficulty level"
            ],
            "overall_quality": 0.75
        }

        mock_refined_prompt = {
            "refined_question": "What are the specific benefits of implementing Test-Driven Development in software projects?",
            "refined_answer": "TDD provides specific benefits including: improved code quality through early bug detection, better software design through testable code architecture, increased developer confidence when making changes, and reduced debugging time.",
            "improvements_made": [
                "Added specificity to question",
                "Expanded answer with concrete benefits",
                "Increased detail level"
            ],
            "quality_improvement": 0.15,  # From 0.75 to 0.90
            "new_difficulty_level": 3
        }

        mock_openai_client.refine_prompt.return_value = mock_refined_prompt

        # Act
        result = await refinement_agent.refine_prompt_based_on_feedback(
            sample_prompt,
            quality_feedback
        )

        # Assert
        assert "refined_question" in result
        assert "improvements_made" in result
        assert result["quality_improvement"] == 0.15
        assert len(result["improvements_made"]) == 3

    async def test_iterative_refinement(self, refinement_agent, mock_openai_client, sample_prompt):
        """Test iterative prompt refinement until quality threshold."""
        # Arrange
        target_quality = 0.9
        max_iterations = 3

        # Mock multiple refinement iterations
        refinement_responses = [
            {"refined_prompt": {"question": "Iteration 1", "answer": "Answer 1"}, "quality_score": 0.8},
            {"refined_prompt": {"question": "Iteration 2", "answer": "Answer 2"}, "quality_score": 0.85},
            {"refined_prompt": {"question": "Iteration 3", "answer": "Answer 3"}, "quality_score": 0.92}
        ]

        mock_openai_client.iterative_refine.side_effect = refinement_responses

        # Act
        result = await refinement_agent.iterative_refinement(
            sample_prompt,
            target_quality=target_quality,
            max_iterations=max_iterations
        )

        # Assert
        assert result["final_quality_score"] >= target_quality
        assert result["iterations_completed"] <= max_iterations
        assert "refinement_history" in result

    async def test_optimize_for_retrieval_practice(self, refinement_agent, mock_openai_client, sample_prompt):
        """Test optimizing prompts for effective retrieval practice."""
        # Arrange
        mock_optimized_prompt = {
            "optimized_question": "Describe the three phases of the TDD cycle and explain what happens in each phase.",
            "optimized_answer": "The TDD cycle has three phases: 1) Red - Write a failing test that defines the desired functionality, 2) Green - Write the minimal code needed to make the test pass, 3) Refactor - Improve the code structure while keeping tests passing.",
            "retrieval_optimizations": [
                "Added multi-part question structure",
                "Required active recall of sequence",
                "Encouraged elaborative explanation"
            ],
            "cognitive_load_score": 0.7,  # Appropriate difficulty
            "retrieval_effectiveness": 0.9
        }

        mock_openai_client.optimize_for_retrieval.return_value = mock_optimized_prompt

        # Act
        result = await refinement_agent.optimize_for_retrieval_practice(sample_prompt)

        # Assert
        assert "optimized_question" in result
        assert "retrieval_optimizations" in result
        assert result["retrieval_effectiveness"] == 0.9


class TestAgentService:
    """Test suite for AgentService coordination and management."""

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
    def agent_service(self, mock_content_repo, mock_prompt_repo):
        """Create AgentService with mocked dependencies."""
        return AgentService(
            content_repo=mock_content_repo,
            prompt_repo=mock_prompt_repo
        )

    async def test_execute_complete_pipeline(self, agent_service, sample_content):
        """Test executing complete agent processing pipeline."""
        # Arrange
        processing_config = {
            "max_prompts": 8,
            "quality_threshold": 0.8,
            "enable_refinement": True
        }

        # Mock pipeline execution
        with patch.object(agent_service, '_coordinate_agents') as mock_coordinate:
            mock_coordinate.return_value = {
                "execution_id": "pipeline_123",
                "prompts_generated": 6,
                "average_quality": 0.85,
                "status": "completed"
            }

            # Act
            result = await agent_service.execute_complete_pipeline(
                sample_content,
                processing_config
            )

            # Assert
            assert result["status"] == "completed"
            assert result["prompts_generated"] == 6
            assert result["average_quality"] == 0.85

    async def test_agent_performance_monitoring(self, agent_service):
        """Test monitoring agent performance metrics."""
        # Arrange
        execution_id = "perf_test_123"

        # Act
        performance_data = await agent_service.get_agent_performance_metrics(execution_id)

        # Assert
        assert "execution_summary" in performance_data
        assert "agent_timings" in performance_data
        assert "resource_usage" in performance_data
        assert "quality_metrics" in performance_data

    async def test_error_handling_and_recovery(self, agent_service, sample_content):
        """Test agent error handling and recovery strategies."""
        # Arrange
        processing_config = {"max_prompts": 5}

        # Mock agent failure
        with patch.object(agent_service, '_coordinate_agents') as mock_coordinate:
            mock_coordinate.side_effect = Exception("Agent execution failed")

            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                await agent_service.execute_complete_pipeline(
                    sample_content,
                    processing_config
                )

            assert "Agent execution failed" in str(exc_info.value)

    async def test_agent_configuration_validation(self, agent_service):
        """Test validation of agent configurations."""
        # Arrange
        valid_config = {
            "model_name": "gpt-5-mini",
            "temperature": 0.7,
            "max_tokens": 1000,
            "timeout_seconds": 30
        }

        invalid_config = {
            "model_name": "invalid-model",
            "temperature": 2.0,  # Invalid: > 1.0
            "max_tokens": -100,  # Invalid: negative
        }

        # Act & Assert
        assert agent_service.validate_agent_config(valid_config) is True

        with pytest.raises(ValueError):
            agent_service.validate_agent_config(invalid_config)


class TestAgentIntegration:
    """Test suite for agent integration and workflow patterns."""

    async def test_agent_communication_patterns(self):
        """Test communication patterns between agents."""
        # This test would verify that agents can pass data correctly
        # between pipeline stages in a real LangGraph implementation

        # Arrange
        mock_orchestrator = AsyncMock()
        mock_analyzer = AsyncMock()
        mock_generator = AsyncMock()

        # Simulate data flow
        analysis_output = {"concepts": ["concept1", "concept2"]}
        generation_output = {"prompts": ["prompt1", "prompt2"]}

        mock_analyzer.extract_key_concepts.return_value = analysis_output
        mock_generator.generate_prompts_from_concepts.return_value = generation_output

        # Act - Simulate pipeline flow
        concepts = await mock_analyzer.extract_key_concepts(MagicMock())
        prompts = await mock_generator.generate_prompts_from_concepts(concepts["concepts"])

        # Assert
        assert concepts == analysis_output
        assert prompts == generation_output

    async def test_agent_state_management(self):
        """Test agent state management in LangGraph workflows."""
        # This test would verify proper state management between workflow steps
        # In a real implementation, this would test LangGraph state handling

        # Arrange
        workflow_state = {
            "content_id": str(uuid.uuid4()),
            "current_step": "analysis",
            "analysis_results": None,
            "generation_results": None,
            "quality_results": None
        }

        # Act - Simulate state updates
        workflow_state["current_step"] = "generation"
        workflow_state["analysis_results"] = {"concepts": ["test"]}

        # Assert
        assert workflow_state["current_step"] == "generation"
        assert workflow_state["analysis_results"]["concepts"] == ["test"]

    async def test_parallel_agent_execution(self):
        """Test parallel execution of independent agents."""
        # This test would verify that agents can run in parallel when appropriate
        # For example, quality review of multiple prompts simultaneously

        # Arrange
        prompts = [MagicMock() for _ in range(5)]
        mock_quality_agent = AsyncMock()

        # Mock parallel evaluation
        async def mock_evaluate(prompt):
            return {"quality_score": 0.8, "prompt_id": str(prompt.id)}

        mock_quality_agent.evaluate_prompt_quality.side_effect = mock_evaluate

        # Act - Simulate parallel execution
        import asyncio
        tasks = [mock_quality_agent.evaluate_prompt_quality(p) for p in prompts]
        results = await asyncio.gather(*tasks)

        # Assert
        assert len(results) == 5
        assert all(r["quality_score"] == 0.8 for r in results)

    async def test_agent_retry_mechanisms(self):
        """Test agent retry mechanisms for transient failures."""
        # Arrange
        mock_agent = AsyncMock()
        call_count = 0

        async def failing_then_succeeding(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Transient failure")
            return {"success": True}

        mock_agent.process_content.side_effect = failing_then_succeeding

        # Act - Simulate retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                result = await mock_agent.process_content()
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(0.1)  # Brief delay between retries

        # Assert
        assert result["success"] is True
        assert call_count == 3