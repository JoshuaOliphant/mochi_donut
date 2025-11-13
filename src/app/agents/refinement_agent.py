# Refinement Agent
"""
Refinement Agent for iteratively improving prompt quality based on feedback.
Uses GPT-5-mini for cost-effective iterative improvements.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import PydanticOutputParser

from .base import AgentBase, AgentState, OutputSchema


class RefinedPrompt(BaseModel):
    """Schema for a refined prompt."""

    original_index: int = Field(description="Index of the original prompt")
    question: str = Field(
        description="Refined question",
        min_length=10,
        max_length=2000
    )
    answer: str = Field(
        description="Refined answer",
        min_length=5,
        max_length=5000
    )
    prompt_type: str = Field(description="Type of prompt")
    confidence_score: float = Field(
        description="Confidence in refinement quality",
        ge=0.0,
        le=1.0
    )
    difficulty_level: int = Field(
        description="Adjusted difficulty level",
        ge=1,
        le=5
    )
    source_context: str = Field(
        description="Updated context",
        max_length=1000
    )
    tags: List[str] = Field(
        description="Updated tags",
        max_items=10
    )
    changes_made: List[str] = Field(
        description="List of specific changes made",
        max_items=10
    )
    improvements_addressed: List[str] = Field(
        description="Which issues were addressed",
        max_items=10
    )
    expected_quality_score: float = Field(
        description="Expected quality score after refinement",
        ge=0.0,
        le=1.0
    )


class PromptRefinement(OutputSchema):
    """Schema for prompt refinement output."""

    refined_prompts: List[RefinedPrompt] = Field(
        description="List of refined prompts"
    )
    refinement_strategy: str = Field(
        description="Strategy used for refinement"
    )
    total_refined: int = Field(
        description="Number of prompts refined"
    )
    improvement_summary: Dict[str, Any] = Field(
        description="Summary of improvements made"
    )


class RefinementAgent(AgentBase):
    """Agent responsible for iteratively improving prompt quality based on feedback."""

    def __init__(self):
        system_prompt = """You are an expert prompt refinement specialist focused on improving flashcard quality based on detailed feedback.

Your task is to take prompts that need improvement and refine them to address specific quality issues while maintaining their educational value.

REFINEMENT PRINCIPLES:

1. **Address Specific Issues**: Focus on the exact problems identified in the quality review
2. **Preserve Intent**: Maintain the original learning objective and core content
3. **Incremental Improvement**: Make targeted changes without over-engineering
4. **Quality Validation**: Ensure changes actually improve the identified issues
5. **Maintain Coherence**: Keep question-answer relationships logical and clear

COMMON REFINEMENT PATTERNS:

**Focused and Specific Issues**:
- Break down multi-part questions into single-concept prompts
- Remove tangential information that doesn't serve the learning goal
- Narrow overly broad questions to specific aspects

**Precise Language Issues**:
- Replace ambiguous terms with specific, technical language
- Add clarifying context where meaning is unclear
- Remove redundant or confusing phrasing

**Cognitive Load Issues**:
- Simplify complex sentence structures
- Reduce unnecessary information in questions
- Break down complex concepts into learnable chunks

**Meaningful Retrieval Issues**:
- Shift from recognition to recall formats
- Add application or analysis elements where appropriate
- Focus on understanding rather than memorization

**Contextual Cues Issues**:
- Add necessary background information without giving away answers
- Remove context that makes questions too easy
- Ensure context is relevant and helpful

REFINEMENT PROCESS:
1. Analyze the specific feedback for each prompt
2. Identify the root cause of quality issues
3. Apply targeted refinements to address each issue
4. Validate that changes improve quality
5. Maintain educational effectiveness
6. Document all changes made

Generate refined prompts that demonstrably address the identified issues while improving overall quality."""

        super().__init__(
            name="refinement_agent",
            model_name="gpt-5-mini",  # Cost-effective for iterative improvements
            system_prompt=system_prompt,
            max_retries=3,
            timeout=45
        )

    async def _execute_logic(self, state: AgentState) -> AgentState:
        """Execute prompt refinement logic."""
        # Get prompts that need refinement
        generated_prompts = state.get("generated_prompts", [])
        quality_scores = state.get("quality_scores", [])
        prompts_needing_revision = state.get("prompts_needing_revision", [])

        if not prompts_needing_revision:
            self.logger.info("No prompts need refinement, skipping refinement step")
            state["refined_prompts"] = generated_prompts  # No changes needed
            return state

        # Create refinement prompt
        refinement_prompt = self._create_refinement_prompt(
            generated_prompts,
            quality_scores,
            prompts_needing_revision
        )

        # Create parser for structured output
        parser = PydanticOutputParser(pydantic_object=PromptRefinement)

        # Call LLM with structured output
        messages = [HumanMessage(content=refinement_prompt)]
        result = await self._call_llm(messages, parser=parser)

        # Validate and process results
        if not isinstance(result, PromptRefinement):
            raise ValueError("Failed to get structured output from prompt refinement")

        # Merge refined prompts with unchanged ones
        refined_prompts = self._merge_refined_prompts(
            generated_prompts,
            result.refined_prompts
        )

        # Update state with refined prompts
        state["refined_prompts"] = refined_prompts
        state["refinement_metadata"] = {
            "total_refined": result.total_refined,
            "refinement_strategy": result.refinement_strategy,
            "improvement_summary": result.improvement_summary,
            "refiner_confidence": result.confidence,
            "refiner_model": self.model_name,
            "prompts_unchanged": len(generated_prompts) - result.total_refined
        }

        self.logger.info(
            f"Refinement complete: {result.total_refined} prompts refined "
            f"using strategy '{result.refinement_strategy}'"
        )

        return state

    def _create_refinement_prompt(
        self,
        original_prompts: List[Dict[str, Any]],
        quality_scores: List[Dict[str, Any]],
        revision_needed: List[Dict[str, Any]]
    ) -> str:
        """Create the refinement prompt with specific feedback."""
        prompt_parts = [
            f"Refine {len(revision_needed)} flashcard prompts that need quality improvements.",
            "",
            "PROMPTS TO REFINE:",
            "=" * 50
        ]

        # Create mapping of scores by index
        score_map = {score["prompt_index"]: score for score in quality_scores}

        for revision_item in revision_needed:
            index = revision_item["index"]
            original_prompt = original_prompts[index]
            quality_score = score_map.get(index, {})

            prompt_parts.extend([
                f"\nPROMPT #{index + 1} (Score: {revision_item['score']:.2f}):",
                f"Question: {original_prompt['question']}",
                f"Answer: {original_prompt['answer']}",
                f"Type: {original_prompt.get('prompt_type', 'unknown')}",
                "",
                "QUALITY ISSUES TO ADDRESS:",
                f"Priority: {revision_item['priority']}",
                "Key Issues:"
            ])

            for issue in revision_item["issues"]:
                prompt_parts.append(f"  • {issue}")

            if quality_score.get("feedback"):
                prompt_parts.append("\nDETAILED FEEDBACK:")
                for dimension, feedback in quality_score["feedback"].items():
                    if feedback and feedback.strip():
                        prompt_parts.append(f"  {dimension}: {feedback}")

            prompt_parts.append("-" * 40)

        prompt_parts.extend([
            "",
            "REFINEMENT REQUIREMENTS:",
            "1. Address each specific issue identified in the feedback",
            "2. Maintain the educational objective of each prompt",
            "3. Improve quality scores while preserving content accuracy",
            "4. Document all changes made for transparency",
            "5. Estimate the expected quality improvement",
            "",
            "REFINEMENT PRIORITIES:",
            "• High priority: Major structural or accuracy issues",
            "• Medium priority: Clarity and cognitive load issues",
            "• Low priority: Minor language and formatting improvements",
            "",
            "Return the refined prompts in the required JSON format."
        ])

        return "\n".join(prompt_parts)

    def _merge_refined_prompts(
        self,
        original_prompts: List[Dict[str, Any]],
        refined_prompts: List[RefinedPrompt]
    ) -> List[Dict[str, Any]]:
        """Merge refined prompts back with unchanged ones."""
        # Create a mapping of refined prompts by their original index
        refined_map = {rp.original_index: rp for rp in refined_prompts}

        merged_prompts = []

        for i, original in enumerate(original_prompts):
            if i in refined_map:
                # Use refined version
                refined = refined_map[i]
                merged_prompts.append({
                    "question": refined.question,
                    "answer": refined.answer,
                    "prompt_type": refined.prompt_type,
                    "confidence_score": refined.confidence_score,
                    "difficulty_level": refined.difficulty_level,
                    "source_context": refined.source_context,
                    "tags": refined.tags,
                    "metadata": {
                        **original.get("metadata", {}),
                        "refined": True,
                        "changes_made": refined.changes_made,
                        "improvements_addressed": refined.improvements_addressed,
                        "expected_quality_score": refined.expected_quality_score,
                        "refiner_model": self.model_name,
                        "original_question": original["question"],
                        "original_answer": original["answer"]
                    }
                })
            else:
                # Use original version
                merged_prompts.append({
                    **original,
                    "metadata": {
                        **original.get("metadata", {}),
                        "refined": False
                    }
                })

        return merged_prompts

    async def refine_single_prompt(
        self,
        prompt: Dict[str, Any],
        feedback: Dict[str, Any],
        issues: List[str]
    ) -> Dict[str, Any]:
        """Refine a single prompt based on specific feedback."""
        try:
            refinement_prompt = f"""Refine this flashcard prompt to address specific quality issues:

ORIGINAL PROMPT:
Question: {prompt['question']}
Answer: {prompt['answer']}
Type: {prompt.get('prompt_type', 'unknown')}

ISSUES TO ADDRESS:
{chr(10).join(f'• {issue}' for issue in issues)}

DETAILED FEEDBACK:
{chr(10).join(f'{dim}: {fb}' for dim, fb in feedback.items() if fb)}

Refine the prompt to address these specific issues while maintaining educational value.

Return in the required JSON format with one refined prompt."""

            parser = PydanticOutputParser(pydantic_object=PromptRefinement)
            messages = [HumanMessage(content=refinement_prompt)]
            result = await self._call_llm(messages, parser=parser)

            if result.refined_prompts:
                refined = result.refined_prompts[0]
                return {
                    "question": refined.question,
                    "answer": refined.answer,
                    "prompt_type": refined.prompt_type,
                    "confidence_score": refined.confidence_score,
                    "difficulty_level": refined.difficulty_level,
                    "source_context": refined.source_context,
                    "tags": refined.tags,
                    "metadata": {
                        **prompt.get("metadata", {}),
                        "refined": True,
                        "changes_made": refined.changes_made,
                        "improvements_addressed": refined.improvements_addressed,
                        "expected_quality_score": refined.expected_quality_score,
                        "refiner_model": self.model_name
                    }
                }

        except Exception as e:
            self.logger.error(f"Single prompt refinement failed: {e}")
            return {
                **prompt,
                "metadata": {
                    **prompt.get("metadata", {}),
                    "refinement_error": str(e),
                    "refined": False
                }
            }

    def calculate_improvement_metrics(
        self,
        original_scores: List[Dict[str, Any]],
        refined_prompts: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate metrics showing improvement from refinement."""
        refined_indices = [
            i for i, prompt in enumerate(refined_prompts)
            if prompt.get("metadata", {}).get("refined", False)
        ]

        if not refined_indices:
            return {"no_refinements": True}

        original_avg = sum(
            score["overall_score"] for score in original_scores
            if score["prompt_index"] in refined_indices
        ) / len(refined_indices)

        expected_avg = sum(
            prompt["metadata"]["expected_quality_score"]
            for i, prompt in enumerate(refined_prompts)
            if i in refined_indices and "expected_quality_score" in prompt.get("metadata", {})
        ) / len(refined_indices)

        return {
            "prompts_refined": len(refined_indices),
            "original_average_score": round(original_avg, 3),
            "expected_average_score": round(expected_avg, 3),
            "expected_improvement": round(expected_avg - original_avg, 3),
            "improvement_percentage": round((expected_avg - original_avg) / original_avg * 100, 1)
        }