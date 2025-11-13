# LangGraph Workflow Implementation
"""
LangGraph-based workflow for multi-agent prompt generation.
Provides a graph-based approach to orchestrating the agent workflow with proper state management.
"""

import logging
from typing import Dict, Any, List, Literal
from datetime import datetime
import uuid

try:
    from langgraph.graph import StateGraph, END
    from langgraph.graph.message import add_messages
    LANGGRAPH_AVAILABLE = True
except ImportError:
    # Fallback if langgraph is not available
    StateGraph = None
    END = "END"
    add_messages = None
    LANGGRAPH_AVAILABLE = False

from .base import AgentState, AgentStatus, CostTracker, AgentError
from .content_analyzer import ContentAnalyzerAgent
from .prompt_generator import PromptGeneratorAgent
from .quality_reviewer import QualityReviewerAgent
from .refinement_agent import RefinementAgent


logger = logging.getLogger(__name__)


class PromptGenerationWorkflow:
    """
    LangGraph-based workflow for prompt generation.

    This class provides a graph-based approach to orchestrating the multi-agent
    prompt generation process with proper state transitions and error handling.
    """

    def __init__(
        self,
        quality_threshold: float = 0.7,
        max_iterations: int = 3
    ):
        self.quality_threshold = quality_threshold
        self.max_iterations = max_iterations

        # Initialize agents
        self.content_analyzer = ContentAnalyzerAgent()
        self.prompt_generator = PromptGeneratorAgent()
        self.quality_reviewer = QualityReviewerAgent(quality_threshold)
        self.refinement_agent = RefinementAgent()

        # Build the workflow graph
        self.workflow = self._build_workflow_graph()

    def _build_workflow_graph(self):
        """Build the LangGraph workflow graph."""
        if not LANGGRAPH_AVAILABLE:
            logger.warning("LangGraph not available, using fallback orchestrator")
            return None

        # Define the workflow graph
        workflow = StateGraph(AgentState)

        # Add nodes for each stage
        workflow.add_node("analyze_content", self._analyze_content_node)
        workflow.add_node("generate_prompts", self._generate_prompts_node)
        workflow.add_node("review_quality", self._review_quality_node)
        workflow.add_node("refine_prompts", self._refine_prompts_node)
        workflow.add_node("finalize_results", self._finalize_results_node)

        # Define the workflow edges
        workflow.set_entry_point("analyze_content")

        # Content analysis always leads to prompt generation
        workflow.add_edge("analyze_content", "generate_prompts")

        # Prompt generation always leads to quality review
        workflow.add_edge("generate_prompts", "review_quality")

        # Quality review leads to refinement or finalization based on conditions
        workflow.add_conditional_edges(
            "review_quality",
            self._should_refine_or_finish,
            {
                "refine": "refine_prompts",
                "finish": "finalize_results"
            }
        )

        # Refinement leads back to quality review or finalization
        workflow.add_conditional_edges(
            "refine_prompts",
            self._should_iterate_or_finish,
            {
                "iterate": "review_quality",
                "finish": "finalize_results"
            }
        )

        # Finalization is the end
        workflow.add_edge("finalize_results", END)

        return workflow.compile()

    async def execute(
        self,
        content_id: str,
        content_text: str,
        content_metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Execute the workflow for prompt generation.

        Args:
            content_id: Unique identifier for the content
            content_text: The content to process
            content_metadata: Additional metadata about the content

        Returns:
            Dict containing the workflow results
        """
        if not LANGGRAPH_AVAILABLE or not self.workflow:
            logger.info("Using fallback orchestrator workflow")
            from .orchestrator import OrchestratorAgent
            orchestrator = OrchestratorAgent(self.quality_threshold, self.max_iterations)
            return await orchestrator.execute_workflow(content_id, content_text, content_metadata)

        # Initialize workflow state
        initial_state: AgentState = {
            "workflow_id": str(uuid.uuid4()),
            "content_id": content_id,
            "content_text": content_text,
            "content_metadata": content_metadata or {},
            "started_at": datetime.now(),
            "current_step": "initialization",
            "iteration_count": 0,
            "max_iterations": self.max_iterations,
            "quality_threshold": self.quality_threshold,
            "retry_count": 0,
            "max_retries": 3,
            "errors": [],
            "cost_tracker": CostTracker(),
            "status": AgentStatus.RUNNING
        }

        try:
            logger.info(f"Starting LangGraph workflow for content {content_id}")

            # Execute the workflow
            final_state = await self.workflow.ainvoke(initial_state)

            # Mark as completed
            final_state["status"] = AgentStatus.COMPLETED
            final_state["completed_at"] = datetime.now()

            logger.info(
                f"Workflow completed successfully. "
                f"Total cost: ${final_state['cost_tracker'].total_cost:.4f}"
            )

            return self._format_workflow_result(final_state)

        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")

            # Create error result
            error_state = {
                **initial_state,
                "status": AgentStatus.FAILED,
                "completed_at": datetime.now(),
                "errors": [
                    {
                        "stage": initial_state.get("current_step", "unknown"),
                        "error": str(e),
                        "timestamp": datetime.now().isoformat()
                    }
                ]
            }

            return self._format_workflow_result(error_state, failed=True)

    async def _analyze_content_node(self, state: AgentState) -> AgentState:
        """Content analysis node."""
        state["current_step"] = "content_analysis"
        logger.info("Executing content analysis node")

        try:
            return await self.content_analyzer.execute(state)
        except Exception as e:
            raise AgentError(f"Content analysis failed: {str(e)}", "content_analyzer")

    async def _generate_prompts_node(self, state: AgentState) -> AgentState:
        """Prompt generation node."""
        state["current_step"] = "prompt_generation"
        logger.info("Executing prompt generation node")

        try:
            return await self.prompt_generator.execute(state)
        except Exception as e:
            raise AgentError(f"Prompt generation failed: {str(e)}", "prompt_generator")

    async def _review_quality_node(self, state: AgentState) -> AgentState:
        """Quality review node."""
        state["current_step"] = "quality_review"
        logger.info("Executing quality review node")

        try:
            return await self.quality_reviewer.execute(state)
        except Exception as e:
            raise AgentError(f"Quality review failed: {str(e)}", "quality_reviewer")

    async def _refine_prompts_node(self, state: AgentState) -> AgentState:
        """Prompt refinement node."""
        state["current_step"] = "prompt_refinement"
        state["iteration_count"] = state.get("iteration_count", 0) + 1

        logger.info(f"Executing refinement node (iteration {state['iteration_count']})")

        try:
            refined_state = await self.refinement_agent.execute(state)

            # Update generated_prompts with refined versions for next iteration
            if "refined_prompts" in refined_state:
                refined_state["generated_prompts"] = refined_state["refined_prompts"]

            return refined_state
        except Exception as e:
            raise AgentError(f"Prompt refinement failed: {str(e)}", "refinement_agent")

    async def _finalize_results_node(self, state: AgentState) -> AgentState:
        """Finalization node."""
        state["current_step"] = "finalization"
        logger.info("Executing finalization node")

        # Use refined prompts if available, otherwise use generated prompts
        final_prompts = state.get("refined_prompts") or state.get("generated_prompts", [])
        state["final_prompts"] = final_prompts

        # Calculate final metrics
        state["final_metrics"] = self._calculate_final_metrics(state)

        logger.info(
            f"Workflow finalized with {len(final_prompts)} prompts. "
            f"Final quality score: {state.get('overall_quality_score', 0.0):.2f}"
        )

        return state

    def _should_refine_or_finish(self, state: AgentState) -> Literal["refine", "finish"]:
        """Decide whether to refine prompts or finish workflow."""
        overall_quality = state.get("overall_quality_score", 0.0)
        prompts_needing_revision = state.get("prompts_needing_revision", [])
        iteration_count = state.get("iteration_count", 0)

        # Check if we've reached max iterations
        if iteration_count >= self.max_iterations:
            logger.info(f"Max iterations ({self.max_iterations}) reached, finishing workflow")
            return "finish"

        # Check if quality threshold is met and no prompts need revision
        if overall_quality >= self.quality_threshold and len(prompts_needing_revision) == 0:
            logger.info(
                f"Quality threshold met (score: {overall_quality:.2f}), finishing workflow"
            )
            return "finish"

        # Otherwise, refine prompts
        logger.info(
            f"Quality below threshold ({overall_quality:.2f} < {self.quality_threshold}) "
            f"or {len(prompts_needing_revision)} prompts need revision, continuing refinement"
        )
        return "refine"

    def _should_iterate_or_finish(self, state: AgentState) -> Literal["iterate", "finish"]:
        """Decide whether to iterate again or finish after refinement."""
        iteration_count = state.get("iteration_count", 0)

        # Always do one more quality review after refinement unless at max iterations
        if iteration_count >= self.max_iterations:
            logger.info("Max iterations reached after refinement, finishing workflow")
            return "finish"

        logger.info("Performing final quality review after refinement")
        return "iterate"

    def _calculate_final_metrics(self, state: AgentState) -> Dict[str, Any]:
        """Calculate final workflow metrics."""
        final_prompts = state.get("final_prompts", [])
        quality_scores = state.get("quality_scores", [])
        cost_tracker = state.get("cost_tracker", CostTracker())

        metrics = {
            "total_prompts": len(final_prompts),
            "iterations_completed": state.get("iteration_count", 0),
            "overall_quality_score": state.get("overall_quality_score", 0.0),
            "cost_summary": cost_tracker.get_summary(),
            "workflow_duration": None,
            "prompts_by_type": {},
            "quality_distribution": {}
        }

        # Calculate duration
        if state.get("started_at") and state.get("completed_at"):
            duration = state["completed_at"] - state["started_at"]
            metrics["workflow_duration"] = duration.total_seconds()

        # Analyze prompt types
        for prompt in final_prompts:
            prompt_type = str(prompt.get("prompt_type", "unknown"))
            metrics["prompts_by_type"][prompt_type] = metrics["prompts_by_type"].get(prompt_type, 0) + 1

        # Analyze quality distribution
        if quality_scores:
            scores = [score["overall_score"] for score in quality_scores]
            metrics["quality_distribution"] = {
                "min_score": min(scores),
                "max_score": max(scores),
                "avg_score": sum(scores) / len(scores),
                "above_threshold": len([s for s in scores if s >= self.quality_threshold])
            }

        return metrics

    def _format_workflow_result(self, state: AgentState, failed: bool = False) -> Dict[str, Any]:
        """Format the final workflow result."""
        result = {
            "workflow_id": state["workflow_id"],
            "content_id": state["content_id"],
            "status": "failed" if failed else "completed",
            "prompts": state.get("final_prompts", []),
            "metrics": state.get("final_metrics", {}),
            "metadata": {
                "started_at": state["started_at"].isoformat() if state.get("started_at") else None,
                "completed_at": state["completed_at"].isoformat() if state.get("completed_at") else None,
                "iterations": state.get("iteration_count", 0),
                "quality_threshold": self.quality_threshold,
                "errors": state.get("errors", []),
                "langgraph_enabled": LANGGRAPH_AVAILABLE
            }
        }

        # Add quality information if available
        if state.get("quality_scores"):
            result["quality_analysis"] = {
                "scores": state["quality_scores"],
                "overall_score": state.get("overall_quality_score"),
                "review_metadata": state.get("quality_review_metadata", {})
            }

        # Add refinement information if available
        if state.get("refinement_metadata"):
            result["refinement_analysis"] = state["refinement_metadata"]

        return result

    async def execute_preview(
        self,
        content_text: str,
        max_prompts: int = 5
    ) -> Dict[str, Any]:
        """
        Execute a preview workflow with limited prompt generation.

        Args:
            content_text: The content to analyze
            max_prompts: Maximum number of prompts to generate

        Returns:
            Dict containing preview results
        """
        try:
            # Quick content analysis
            analysis_result = await self.content_analyzer.analyze_content_preview(content_text)

            if "error" in analysis_result:
                return {"error": analysis_result["error"], "status": "failed"}

            # Generate a few sample prompts
            sample_prompt = await self.prompt_generator.generate_single_prompt(
                concept=analysis_result["key_concepts"][0] if analysis_result["key_concepts"] else "main concept",
                context=content_text[:1000],
                difficulty=analysis_result["difficulty_level"]
            )

            return {
                "status": "preview_completed",
                "analysis": analysis_result,
                "sample_prompt": sample_prompt,
                "estimated_prompts": min(analysis_result["recommended_prompt_count"], max_prompts),
                "preview": True
            }

        except Exception as e:
            logger.error(f"Preview workflow failed: {e}")
            return {
                "error": str(e),
                "status": "preview_failed"
            }