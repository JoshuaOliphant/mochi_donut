# Quality Reviewer Agent
"""
Quality Reviewer Agent for evaluating prompt quality against Matuschak's principles.
Uses GPT-5-standard for comprehensive quality assessment and LLM-as-judge evaluation.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import PydanticOutputParser

from .base import AgentBase, AgentState, OutputSchema
from app.db.models import QualityMetricType


class QualityDimension(BaseModel):
    """Schema for individual quality dimensions."""

    dimension: str = Field(description="Name of the quality dimension")
    score: float = Field(description="Score for this dimension (0.0-1.0)", ge=0.0, le=1.0)
    feedback: str = Field(description="Specific feedback for this dimension")
    suggestions: List[str] = Field(description="Improvement suggestions", max_items=5)


class PromptQualityAssessment(BaseModel):
    """Schema for assessing a single prompt's quality."""

    prompt_index: int = Field(description="Index of the prompt being assessed")
    overall_score: float = Field(description="Overall quality score (0.0-1.0)", ge=0.0, le=1.0)

    # Matuschak principle scores
    focused_and_specific: QualityDimension
    precise_language: QualityDimension
    appropriate_cognitive_load: QualityDimension
    meaningful_retrieval: QualityDimension
    contextual_cues: QualityDimension

    # Additional quality dimensions
    factual_accuracy: QualityDimension
    difficulty_appropriateness: QualityDimension
    answer_completeness: QualityDimension

    needs_revision: bool = Field(description="Whether the prompt needs revision")
    revision_priority: str = Field(description="Priority level: high, medium, low")
    key_issues: List[str] = Field(description="Main issues to address", max_items=5)
    strengths: List[str] = Field(description="Prompt strengths", max_items=5)


class QualityReview(OutputSchema):
    """Schema for complete quality review output."""

    assessments: List[PromptQualityAssessment] = Field(
        description="Individual prompt assessments"
    )
    batch_statistics: Dict[str, Any] = Field(
        description="Statistics for the entire batch"
    )
    overall_batch_score: float = Field(
        description="Overall quality score for the batch",
        ge=0.0,
        le=1.0
    )
    revision_recommendations: List[str] = Field(
        description="Batch-level recommendations"
    )
    quality_trends: Dict[str, Any] = Field(
        description="Analysis of quality patterns"
    )


class QualityReviewerAgent(AgentBase):
    """Agent responsible for comprehensive quality review of generated prompts."""

    def __init__(self, quality_threshold: float = 0.7):
        system_prompt = """You are an expert educational content reviewer specializing in spaced repetition flashcard quality assessment.

Your task is to evaluate flashcard prompts against Andy Matuschak's principles and educational best practices using an LLM-as-judge approach.

EVALUATION CRITERIA (Andy Matuschak's Principles):

1. **Focused and Specific** (0.0-1.0):
   - Does the prompt target exactly one specific piece of knowledge?
   - Is the scope appropriately narrow and well-defined?
   - Avoid multi-part questions that test multiple concepts

2. **Precise Language** (0.0-1.0):
   - Is the language clear and unambiguous?
   - Could the question be misinterpreted?
   - Are technical terms used correctly?

3. **Appropriate Cognitive Load** (0.0-1.0):
   - Does the prompt avoid overloading working memory?
   - Is the complexity appropriate for the learning goal?
   - Are unnecessary details removed?

4. **Meaningful Retrieval Practice** (0.0-1.0):
   - Does the prompt promote deep understanding vs. rote memorization?
   - Will answering this help long-term retention?
   - Is it worth remembering?

5. **Contextual Cues** (0.0-1.0):
   - Is there enough context for accurate recall?
   - Are context cues helpful but not giving away the answer?
   - Is the context relevant and not distracting?

ADDITIONAL QUALITY DIMENSIONS:

6. **Factual Accuracy** (0.0-1.0):
   - Is the information correct and up-to-date?
   - Is the answer complete and accurate?

7. **Difficulty Appropriateness** (0.0-1.0):
   - Is the difficulty level appropriate for the stated target?
   - Is the progression logical?

8. **Answer Completeness** (0.0-1.0):
   - Is the expected answer complete?
   - Are there multiple valid answers that should be accepted?

SCORING GUIDELINES:
- 0.9-1.0: Excellent quality, ready for production use
- 0.7-0.89: Good quality, minor improvements needed
- 0.5-0.69: Moderate quality, significant revision needed
- 0.3-0.49: Poor quality, major revision required
- 0.0-0.29: Unacceptable quality, needs complete rewrite

Provide detailed, actionable feedback for each dimension and overall improvement recommendations."""

        self.quality_threshold = quality_threshold

        super().__init__(
            name="quality_reviewer",
            model_name="gpt-5-standard",  # Premium model for thorough review
            system_prompt=system_prompt,
            max_retries=2,
            timeout=60
        )

    async def _execute_logic(self, state: AgentState) -> AgentState:
        """Execute quality review logic."""
        generated_prompts = state.get("generated_prompts", [])

        if not generated_prompts:
            raise ValueError("No generated prompts available for quality review")

        # Perform quality review
        review_prompt = self._create_review_prompt(generated_prompts)

        # Create parser for structured output
        parser = PydanticOutputParser(pydantic_object=QualityReview)

        # Call LLM with structured output
        messages = [HumanMessage(content=review_prompt)]
        result = await self._call_llm(messages, parser=parser)

        # Validate and process results
        if not isinstance(result, QualityReview):
            raise ValueError("Failed to get structured output from quality review")

        # Process assessments and create quality scores
        quality_scores = []
        prompts_needing_revision = []

        for assessment in result.assessments:
            # Create quality score entry
            quality_score = {
                "prompt_index": assessment.prompt_index,
                "overall_score": assessment.overall_score,
                "dimensions": {
                    "focused_and_specific": assessment.focused_and_specific.score,
                    "precise_language": assessment.precise_language.score,
                    "appropriate_cognitive_load": assessment.appropriate_cognitive_load.score,
                    "meaningful_retrieval": assessment.meaningful_retrieval.score,
                    "contextual_cues": assessment.contextual_cues.score,
                    "factual_accuracy": assessment.factual_accuracy.score,
                    "difficulty_appropriateness": assessment.difficulty_appropriateness.score,
                    "answer_completeness": assessment.answer_completeness.score
                },
                "feedback": {
                    "focused_and_specific": assessment.focused_and_specific.feedback,
                    "precise_language": assessment.precise_language.feedback,
                    "appropriate_cognitive_load": assessment.appropriate_cognitive_load.feedback,
                    "meaningful_retrieval": assessment.meaningful_retrieval.feedback,
                    "contextual_cues": assessment.contextual_cues.feedback,
                    "factual_accuracy": assessment.factual_accuracy.feedback,
                    "difficulty_appropriateness": assessment.difficulty_appropriateness.feedback,
                    "answer_completeness": assessment.answer_completeness.feedback
                },
                "needs_revision": assessment.needs_revision,
                "revision_priority": assessment.revision_priority,
                "key_issues": assessment.key_issues,
                "strengths": assessment.strengths,
                "reviewer_model": self.model_name
            }

            quality_scores.append(quality_score)

            # Track prompts that need revision
            if assessment.needs_revision or assessment.overall_score < self.quality_threshold:
                prompts_needing_revision.append({
                    "index": assessment.prompt_index,
                    "score": assessment.overall_score,
                    "priority": assessment.revision_priority,
                    "issues": assessment.key_issues
                })

        # Update state with quality review results
        state["quality_scores"] = quality_scores
        state["overall_quality_score"] = result.overall_batch_score
        state["prompts_needing_revision"] = prompts_needing_revision
        state["quality_review_metadata"] = {
            "batch_statistics": result.batch_statistics,
            "revision_recommendations": result.revision_recommendations,
            "quality_trends": result.quality_trends,
            "reviewer_confidence": result.confidence,
            "reviewer_model": self.model_name,
            "quality_threshold": self.quality_threshold,
            "prompts_above_threshold": len([s for s in quality_scores if s["overall_score"] >= self.quality_threshold]),
            "prompts_below_threshold": len(prompts_needing_revision)
        }

        self.logger.info(
            f"Quality review complete: {result.overall_batch_score:.2f} average score, "
            f"{len(prompts_needing_revision)} prompts need revision"
        )

        return state

    def _create_review_prompt(self, prompts: List[Dict[str, Any]]) -> str:
        """Create the quality review prompt."""
        prompt_parts = [
            f"Evaluate the quality of {len(prompts)} flashcard prompts against Andy Matuschak's principles.",
            "",
            "PROMPTS TO REVIEW:",
            "=" * 50
        ]

        for i, prompt in enumerate(prompts):
            prompt_parts.extend([
                f"\nPROMPT #{i + 1}:",
                f"Question: {prompt['question']}",
                f"Answer: {prompt['answer']}",
                f"Type: {prompt.get('prompt_type', 'unknown')}",
                f"Difficulty: {prompt.get('difficulty_level', 'unknown')}/5",
                f"Context: {prompt.get('source_context', 'N/A')[:200]}",
                "-" * 30
            ])

        prompt_parts.extend([
            "",
            "EVALUATION INSTRUCTIONS:",
            "1. Assess each prompt against all 8 quality dimensions",
            "2. Provide specific, actionable feedback for each dimension",
            "3. Assign accurate scores based on the guidelines",
            "4. Identify specific issues and strengths",
            "5. Determine revision needs and priorities",
            "6. Calculate batch-level statistics and trends",
            "",
            f"QUALITY THRESHOLD: {self.quality_threshold}",
            "Prompts below this threshold should be marked for revision.",
            "",
            "Return your comprehensive evaluation in the required JSON format."
        ])

        return "\n".join(prompt_parts)

    async def review_single_prompt(
        self,
        prompt: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Review a single prompt for quality."""
        try:
            review_prompt = f"""Evaluate this single flashcard prompt:

PROMPT TO REVIEW:
Question: {prompt['question']}
Answer: {prompt['answer']}
Type: {prompt.get('prompt_type', 'unknown')}
Difficulty: {prompt.get('difficulty_level', 'unknown')}/5

Assess against all quality dimensions and provide detailed feedback.

Return in the required JSON format with one assessment."""

            parser = PydanticOutputParser(pydantic_object=QualityReview)
            messages = [HumanMessage(content=review_prompt)]
            result = await self._call_llm(messages, parser=parser)

            if result.assessments:
                assessment = result.assessments[0]
                return {
                    "overall_score": assessment.overall_score,
                    "needs_revision": assessment.needs_revision,
                    "key_issues": assessment.key_issues,
                    "strengths": assessment.strengths,
                    "feedback": {
                        "focused_and_specific": assessment.focused_and_specific.feedback,
                        "precise_language": assessment.precise_language.feedback,
                        "appropriate_cognitive_load": assessment.appropriate_cognitive_load.feedback,
                        "meaningful_retrieval": assessment.meaningful_retrieval.feedback,
                        "contextual_cues": assessment.contextual_cues.feedback
                    },
                    "reviewer_model": self.model_name
                }

        except Exception as e:
            self.logger.error(f"Single prompt review failed: {e}")
            return {
                "error": str(e),
                "overall_score": 0.5,
                "needs_revision": True,
                "key_issues": ["Review failed"],
                "strengths": [],
                "feedback": {},
                "reviewer_model": self.model_name
            }

    def calculate_quality_metrics(self, quality_scores: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert quality scores to database quality metrics format."""
        metrics = []

        for score_data in quality_scores:
            # Create metrics for each dimension
            for dimension, score in score_data["dimensions"].items():
                metric_type = self._map_dimension_to_metric_type(dimension)

                metrics.append({
                    "metric_type": metric_type,
                    "score": score,
                    "weight": 1.0,  # Equal weighting for now
                    "evaluator_model": self.model_name,
                    "reasoning": score_data["feedback"].get(dimension, ""),
                    "feedback": {
                        "dimension": dimension,
                        "issues": score_data.get("key_issues", []),
                        "strengths": score_data.get("strengths", [])
                    },
                    "metadata": {
                        "prompt_index": score_data["prompt_index"],
                        "overall_score": score_data["overall_score"],
                        "needs_revision": score_data["needs_revision"]
                    }
                })

        return metrics

    def _map_dimension_to_metric_type(self, dimension: str) -> QualityMetricType:
        """Map quality dimension to database metric type."""
        mapping = {
            "focused_and_specific": QualityMetricType.CLARITY,
            "precise_language": QualityMetricType.PRECISION,
            "appropriate_cognitive_load": QualityMetricType.COGNITIVE_LOAD,
            "meaningful_retrieval": QualityMetricType.RETRIEVAL_STRENGTH,
            "contextual_cues": QualityMetricType.CONTEXT_SUFFICIENCY,
            "factual_accuracy": QualityMetricType.ACCURACY,
            "difficulty_appropriateness": QualityMetricType.DIFFICULTY_MATCH,
            "answer_completeness": QualityMetricType.COMPLETENESS
        }

        return mapping.get(dimension, QualityMetricType.OVERALL)