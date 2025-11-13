# Prompt Generator Agent
"""
Prompt Generator Agent for creating high-quality flashcard prompts.
Uses GPT-5-mini for balanced performance and cost, following Andy Matuschak's principles.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import PydanticOutputParser

from .base import AgentBase, AgentState, OutputSchema
from app.db.models import PromptType


class GeneratedPrompt(BaseModel):
    """Schema for a single generated prompt."""

    question: str = Field(
        description="The flashcard question",
        min_length=10,
        max_length=2000
    )
    answer: str = Field(
        description="The expected answer",
        min_length=5,
        max_length=5000
    )
    prompt_type: str = Field(
        description="Type of prompt (factual, conceptual, application, etc.)"
    )
    confidence_score: float = Field(
        description="Confidence in prompt quality",
        ge=0.0,
        le=1.0
    )
    difficulty_level: int = Field(
        description="Difficulty level (1-5)",
        ge=1,
        le=5
    )
    source_context: str = Field(
        description="Context from source material",
        max_length=1000
    )
    tags: List[str] = Field(
        description="Relevant tags for categorization",
        max_items=10
    )
    matuschak_principles: List[str] = Field(
        description="Which Matuschak principles this prompt follows",
        max_items=5
    )


class PromptGeneration(OutputSchema):
    """Schema for prompt generation output."""

    prompts: List[GeneratedPrompt] = Field(
        description="List of generated prompts",
        min_items=1,
        max_items=50
    )
    generation_strategy: str = Field(
        description="Strategy used for prompt generation"
    )
    total_prompts: int = Field(
        description="Total number of prompts generated"
    )
    coverage_analysis: Dict[str, Any] = Field(
        description="Analysis of concept coverage"
    )


class PromptGeneratorAgent(AgentBase):
    """Agent responsible for generating high-quality flashcard prompts."""

    def __init__(self):
        system_prompt = """You are an expert prompt writer specializing in spaced repetition flashcards following Andy Matuschak's principles.

Your task is to create high-quality flashcard prompts that promote effective learning and recall.

ANDY MATUSCHAK'S PROMPT WRITING PRINCIPLES:
1. **Focused and Specific**: Each prompt should target one specific piece of knowledge
2. **Precise Language**: Use clear, unambiguous language that cannot be misinterpreted
3. **Appropriate Cognitive Load**: Don't overload working memory with complex multi-part questions
4. **Meaningful Retrieval Practice**: Focus on understanding, not just memorization
5. **Contextual Cues**: Provide enough context for accurate recall without giving away the answer

PROMPT TYPES TO CREATE:
- **Factual**: Direct recall of facts, definitions, dates, names
- **Conceptual**: Understanding of concepts, principles, and relationships
- **Application**: Applying knowledge to solve problems or analyze situations
- **Comparison**: Similarities and differences between concepts
- **Causal**: Cause-and-effect relationships
- **Process**: Steps in procedures or methodologies

QUALITY GUIDELINES:
- Write questions that require active recall, not recognition
- Avoid yes/no questions unless they test important distinctions
- Use specific examples and scenarios when appropriate
- Ensure answers are objective and verifiable
- Create prompts at appropriate difficulty levels
- Include helpful context without making questions too easy

Generate prompts in the specified JSON format with confidence scores and principle alignment."""

        super().__init__(
            name="prompt_generator",
            model_name="gpt-5-mini",  # Balanced performance and cost
            system_prompt=system_prompt,
            max_retries=3,
            timeout=45
        )

    async def _execute_logic(self, state: AgentState) -> AgentState:
        """Execute prompt generation logic."""
        # Extract required information from state
        key_concepts = state.get("key_concepts", [])
        content_text = state.get("content_text", "")
        focus_areas = state.get("focus_areas", [])
        recommended_count = state.get("recommended_prompt_count", 10)
        difficulty_level = state.get("difficulty_level", 3)

        if not key_concepts:
            raise ValueError("No key concepts available for prompt generation")

        # Generate prompts
        generation_prompt = self._create_generation_prompt(
            key_concepts=key_concepts,
            content_text=content_text,
            focus_areas=focus_areas,
            target_count=recommended_count,
            difficulty_level=difficulty_level
        )

        # Create parser for structured output
        parser = PydanticOutputParser(pydantic_object=PromptGeneration)

        # Call LLM with structured output
        messages = [HumanMessage(content=generation_prompt)]
        result = await self._call_llm(messages, parser=parser)

        # Validate and process results
        if not isinstance(result, PromptGeneration):
            raise ValueError("Failed to get structured output from prompt generation")

        # Convert to format expected by the application
        generated_prompts = []
        for prompt in result.prompts:
            generated_prompts.append({
                "question": prompt.question,
                "answer": prompt.answer,
                "prompt_type": self._map_prompt_type(prompt.prompt_type),
                "confidence_score": prompt.confidence_score,
                "difficulty_level": prompt.difficulty_level,
                "source_context": prompt.source_context,
                "tags": prompt.tags,
                "metadata": {
                    "matuschak_principles": prompt.matuschak_principles,
                    "generator_model": self.model_name,
                    "generation_strategy": result.generation_strategy
                }
            })

        # Update state with generated prompts
        state["generated_prompts"] = generated_prompts
        state["prompt_generation_metadata"] = {
            "total_generated": result.total_prompts,
            "generation_strategy": result.generation_strategy,
            "coverage_analysis": result.coverage_analysis,
            "generator_confidence": result.confidence,
            "generator_model": self.model_name
        }

        self.logger.info(
            f"Prompt generation complete: {result.total_prompts} prompts generated "
            f"with average confidence {result.confidence:.2f}"
        )

        return state

    def _create_generation_prompt(
        self,
        key_concepts: List[str],
        content_text: str,
        focus_areas: List[str],
        target_count: int,
        difficulty_level: int
    ) -> str:
        """Create the prompt generation request."""
        prompt_parts = [
            f"Generate {target_count} high-quality flashcard prompts based on the following analysis:",
            "",
            "KEY CONCEPTS TO COVER:",
            "-" * 20
        ]

        for i, concept in enumerate(key_concepts, 1):
            prompt_parts.append(f"{i}. {concept}")

        if focus_areas:
            prompt_parts.extend([
                "",
                "FOCUS AREAS (prioritize these):",
                "-" * 30
            ])
            for area in focus_areas:
                prompt_parts.append(f"• {area}")

        prompt_parts.extend([
            "",
            f"TARGET DIFFICULTY LEVEL: {difficulty_level}/5",
            "",
            "SOURCE CONTENT (for context):",
            "=" * 40,
            content_text[:6000]  # Limit for token management
        ])

        if len(content_text) > 6000:
            prompt_parts.append("\n[Content truncated...]")

        prompt_parts.extend([
            "",
            "GENERATION REQUIREMENTS:",
            f"- Create exactly {target_count} prompts",
            "- Distribute prompts across different concept types",
            "- Follow Andy Matuschak's principles for each prompt",
            "- Ensure questions promote active recall",
            "- Include appropriate context without giving away answers",
            "- Assign confidence scores based on prompt quality",
            "- Tag prompts with relevant categories",
            "",
            "Return the prompts in the required JSON format."
        ])

        return "\n".join(prompt_parts)

    def _map_prompt_type(self, type_string: str) -> PromptType:
        """Map string type to database enum."""
        type_mapping = {
            "factual": PromptType.FACTUAL,
            "conceptual": PromptType.CONCEPTUAL,
            "application": PromptType.APPLICATION,
            "comparison": PromptType.COMPARISON,
            "causal": PromptType.CAUSAL,
            "process": PromptType.PROCESS
        }

        # Normalize the type string
        normalized = type_string.lower().strip()
        return type_mapping.get(normalized, PromptType.FACTUAL)

    async def generate_single_prompt(
        self,
        concept: str,
        context: str,
        difficulty: int = 3
    ) -> Dict[str, Any]:
        """Generate a single prompt for a specific concept."""
        try:
            generation_prompt = f"""Create one high-quality flashcard prompt for this concept:

CONCEPT: {concept}

CONTEXT:
{context[:2000]}

REQUIREMENTS:
- Follow Andy Matuschak's principles
- Target difficulty level: {difficulty}/5
- Provide confidence score
- Include relevant tags

Return in the specified JSON format with a single prompt."""

            parser = PydanticOutputParser(pydantic_object=PromptGeneration)
            messages = [HumanMessage(content=generation_prompt)]
            result = await self._call_llm(messages, parser=parser)

            if result.prompts:
                prompt = result.prompts[0]
                return {
                    "question": prompt.question,
                    "answer": prompt.answer,
                    "prompt_type": self._map_prompt_type(prompt.prompt_type),
                    "confidence_score": prompt.confidence_score,
                    "difficulty_level": prompt.difficulty_level,
                    "source_context": prompt.source_context,
                    "tags": prompt.tags,
                    "metadata": {
                        "matuschak_principles": prompt.matuschak_principles,
                        "generator_model": self.model_name
                    }
                }

        except Exception as e:
            self.logger.error(f"Single prompt generation failed: {e}")
            return {
                "error": str(e),
                "question": f"What is {concept}?",
                "answer": "Failed to generate answer",
                "prompt_type": PromptType.FACTUAL,
                "confidence_score": 0.0,
                "difficulty_level": difficulty,
                "source_context": "",
                "tags": ["error"],
                "metadata": {"error": str(e)}
            }