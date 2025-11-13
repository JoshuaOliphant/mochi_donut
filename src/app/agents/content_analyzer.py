# Content Analyzer Agent
"""
Content Analyzer Agent for extracting key concepts from content.
Uses GPT-5-nano for cost-optimized concept extraction and analysis.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import PydanticOutputParser

from .base import AgentBase, AgentState, OutputSchema


class ConceptExtraction(OutputSchema):
    """Schema for concept extraction output."""

    key_concepts: List[str] = Field(
        description="List of key concepts extracted from the content",
        min_items=1,
        max_items=20
    )
    content_summary: str = Field(
        description="Brief summary of the content",
        max_length=500
    )
    difficulty_level: int = Field(
        description="Estimated difficulty level (1-5)",
        ge=1,
        le=5
    )
    content_type: str = Field(
        description="Type of content (article, textbook, documentation, etc.)"
    )
    recommended_prompt_count: int = Field(
        description="Recommended number of prompts to generate",
        ge=1,
        le=50
    )
    focus_areas: List[str] = Field(
        description="Areas that should be emphasized in prompt generation",
        max_items=10
    )


class ContentAnalyzerAgent(AgentBase):
    """Agent responsible for analyzing content and extracting key concepts."""

    def __init__(self):
        system_prompt = """You are a content analysis expert specializing in educational material analysis for spaced repetition learning.

Your task is to analyze content and extract key concepts that would be valuable for creating flashcards following Andy Matuschak's principles:

1. **Concept Extraction**: Identify the most important concepts, facts, and relationships
2. **Difficulty Assessment**: Evaluate the complexity level of the material
3. **Content Classification**: Determine the type and structure of content
4. **Prompt Planning**: Recommend how many flashcards should be created and what areas to focus on

Guidelines:
- Focus on factual information, definitions, relationships, and principles
- Prioritize concepts that require active recall
- Identify both explicit and implicit knowledge
- Consider the cognitive load of individual concepts
- Prefer atomic concepts over complex, multi-part ideas
- Look for cause-and-effect relationships, comparisons, and categorizations

Output your analysis in the specified JSON format."""

        super().__init__(
            name="content_analyzer",
            model_name="gpt-5-nano",  # Cost-optimized model for analysis
            system_prompt=system_prompt,
            max_retries=3,
            timeout=30
        )

    async def _execute_logic(self, state: AgentState) -> AgentState:
        """Execute content analysis logic."""
        content_text = state.get("content_text", "")
        content_metadata = state.get("content_metadata", {})

        if not content_text:
            raise ValueError("No content text provided for analysis")

        # Prepare analysis prompt
        analysis_prompt = self._create_analysis_prompt(content_text, content_metadata)

        # Create parser for structured output
        parser = PydanticOutputParser(pydantic_object=ConceptExtraction)

        # Call LLM with structured output
        messages = [HumanMessage(content=analysis_prompt)]
        result = await self._call_llm(messages, parser=parser)

        # Validate and process results
        if not isinstance(result, ConceptExtraction):
            raise ValueError("Failed to get structured output from content analysis")

        # Update state with analysis results
        state["key_concepts"] = result.key_concepts
        state["content_summary"] = result.content_summary
        state["difficulty_level"] = result.difficulty_level
        state["content_type"] = result.content_type
        state["recommended_prompt_count"] = result.recommended_prompt_count
        state["focus_areas"] = result.focus_areas

        # Add analysis metadata
        if "analysis_metadata" not in state:
            state["analysis_metadata"] = {}

        state["analysis_metadata"].update({
            "analyzer_confidence": result.confidence,
            "analyzer_model": self.model_name,
            "concept_count": len(result.key_concepts),
            "analysis_timestamp": state.get("started_at").isoformat() if state.get("started_at") else None
        })

        self.logger.info(
            f"Content analysis complete: {len(result.key_concepts)} concepts extracted, "
            f"difficulty level {result.difficulty_level}, "
            f"recommended {result.recommended_prompt_count} prompts"
        )

        return state

    def _create_analysis_prompt(self, content_text: str, metadata: Dict[str, Any]) -> str:
        """Create the analysis prompt with content and metadata."""
        prompt_parts = [
            "Analyze the following content for key concepts that would be valuable for spaced repetition learning:",
            "",
            "CONTENT TO ANALYZE:",
            "=" * 50,
            content_text[:8000],  # Limit content length for token management
        ]

        if len(content_text) > 8000:
            prompt_parts.append("\n[Content truncated for analysis...]")

        if metadata:
            prompt_parts.extend([
                "",
                "CONTENT METADATA:",
                "-" * 20
            ])
            for key, value in metadata.items():
                prompt_parts.append(f"{key}: {value}")

        prompt_parts.extend([
            "",
            "ANALYSIS REQUIREMENTS:",
            "- Extract 5-20 key concepts that would make good flashcard topics",
            "- Prioritize concepts that require active recall and understanding",
            "- Consider both explicit facts and implicit relationships",
            "- Assess the overall difficulty level of the material",
            "- Recommend how many flashcards should be created",
            "- Identify focus areas for prompt generation",
            "",
            "Return your analysis in the required JSON format."
        ])

        return "\n".join(prompt_parts)

    async def analyze_content_preview(self, content_text: str) -> Dict[str, Any]:
        """Quick preview analysis without full workflow integration."""
        try:
            # Create minimal state for preview
            preview_state: AgentState = {
                "content_text": content_text,
                "content_metadata": {},
                "workflow_id": "preview",
                "current_step": "preview_analysis"
            }

            result_state = await self._execute_logic(preview_state)

            return {
                "key_concepts": result_state.get("key_concepts", []),
                "content_summary": result_state.get("content_summary", ""),
                "difficulty_level": result_state.get("difficulty_level", 1),
                "recommended_prompt_count": result_state.get("recommended_prompt_count", 5),
                "focus_areas": result_state.get("focus_areas", [])
            }

        except Exception as e:
            self.logger.error(f"Preview analysis failed: {e}")
            return {
                "error": str(e),
                "key_concepts": [],
                "content_summary": "Analysis failed",
                "difficulty_level": 1,
                "recommended_prompt_count": 5,
                "focus_areas": []
            }