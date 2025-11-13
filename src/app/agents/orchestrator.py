# Orchestrator Agent
"""
Orchestrator Agent for coordinating the multi-agent workflow.
Manages the overall prompt generation process and agent coordination.
"""

import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum

from .base import AgentBase, AgentState, AgentStatus, CostTracker
from .content_analyzer import ContentAnalyzerAgent
from .prompt_generator import PromptGeneratorAgent
from .quality_reviewer import QualityReviewerAgent
from .refinement_agent import RefinementAgent


class WorkflowStage(Enum):
    """Stages in the prompt generation workflow."""
    INITIALIZATION = "initialization"
    CONTENT_ANALYSIS = "content_analysis"
    PROMPT_GENERATION = "prompt_generation"
    QUALITY_REVIEW = "quality_review"
    REFINEMENT = "refinement"
    FINAL_REVIEW = "final_review"
    COMPLETION = "completion"


class OrchestratorAgent(AgentBase):
    """
    Orchestrator agent that coordinates the multi-agent workflow.

    This agent manages the overall process flow, handles error recovery,
    and ensures quality standards are met before completion.
    """

    def __init__(
        self,
        quality_threshold: float = 0.7,
        max_iterations: int = 3,
        max_retries: int = 2
    ):
        system_prompt = """You are the orchestrator for a multi-agent prompt generation system.

Your responsibilities:
1. Coordinate the workflow between specialized agents
2. Monitor quality and determine when iterations are needed
3. Handle errors and recovery strategies
4. Ensure final output meets quality standards
5. Track costs and performance metrics

You do not generate content yourself - you delegate to specialized agents and manage the overall process."""

        self.quality_threshold = quality_threshold
        self.max_iterations = max_iterations
        self.content_analyzer = ContentAnalyzerAgent()
        self.prompt_generator = PromptGeneratorAgent()
        self.quality_reviewer = QualityReviewerAgent(quality_threshold)
        self.refinement_agent = RefinementAgent()

        super().__init__(
            name="orchestrator",
            model_name="gpt-5-mini",  # Simple coordination tasks
            system_prompt=system_prompt,
            max_retries=max_retries,
            timeout=30
        )

    async def execute_workflow(
        self,
        content_id: str,
        content_text: str,
        content_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute the complete prompt generation workflow.

        Args:
            content_id: Unique identifier for the content
            content_text: The content to process
            content_metadata: Additional metadata about the content

        Returns:
            Dict containing the final prompts and workflow metadata
        """
        workflow_id = str(uuid.uuid4())
        started_at = datetime.now()

        # Initialize workflow state
        state: AgentState = {
            "workflow_id": workflow_id,
            "content_id": content_id,
            "content_text": content_text,
            "content_metadata": content_metadata or {},
            "started_at": started_at,
            "current_step": WorkflowStage.INITIALIZATION.value,
            "iteration_count": 0,
            "max_iterations": self.max_iterations,
            "quality_threshold": self.quality_threshold,
            "retry_count": 0,
            "max_retries": self.max_retries,
            "errors": [],
            "cost_tracker": CostTracker(),
            "status": AgentStatus.RUNNING
        }

        try:
            self.logger.info(f"Starting workflow {workflow_id} for content {content_id}")

            # Execute workflow stages
            state = await self._execute_content_analysis(state)
            state = await self._execute_prompt_generation_loop(state)
            state = await self._finalize_workflow(state)

            # Mark as completed
            state["status"] = AgentStatus.COMPLETED
            state["completed_at"] = datetime.now()

            self.logger.info(
                f"Workflow {workflow_id} completed successfully. "
                f"Total cost: ${state['cost_tracker'].total_cost:.4f}"
            )

            return self._create_workflow_result(state)

        except Exception as e:
            state["status"] = AgentStatus.FAILED
            state["completed_at"] = datetime.now()

            error_info = {
                "stage": state["current_step"],
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            state["errors"].append(error_info)

            self.logger.error(f"Workflow {workflow_id} failed: {e}")

            # Return partial results if available
            return self._create_workflow_result(state, failed=True)

    async def _execute_content_analysis(self, state: AgentState) -> AgentState:
        """Execute content analysis stage."""
        state["current_step"] = WorkflowStage.CONTENT_ANALYSIS.value

        self.logger.info("Executing content analysis...")
        state = await self.content_analyzer.execute(state)

        # Validate analysis results
        if not state.get("key_concepts"):
            raise ValueError("Content analysis failed to extract key concepts")

        return state

    async def _execute_prompt_generation_loop(self, state: AgentState) -> AgentState:
        """Execute the iterative prompt generation and refinement loop."""
        iteration = 0

        while iteration < self.max_iterations:
            state["iteration_count"] = iteration + 1

            self.logger.info(f"Starting iteration {iteration + 1} of prompt generation")

            # Generate prompts
            state = await self._execute_prompt_generation(state)

            # Review quality
            state = await self._execute_quality_review(state)

            # Check if quality threshold is met
            overall_quality = state.get("overall_quality_score", 0.0)
            prompts_needing_revision = state.get("prompts_needing_revision", [])

            if overall_quality >= self.quality_threshold and len(prompts_needing_revision) == 0:
                self.logger.info(
                    f"Quality threshold met (score: {overall_quality:.2f}). "
                    "Stopping iteration loop."
                )
                break

            if iteration < self.max_iterations - 1:  # Don't refine on last iteration
                # Refine prompts that need improvement
                state = await self._execute_refinement(state)
            else:
                self.logger.warning(
                    f"Max iterations reached. Final quality score: {overall_quality:.2f}"
                )

            iteration += 1

        return state

    async def _execute_prompt_generation(self, state: AgentState) -> AgentState:
        """Execute prompt generation stage."""
        state["current_step"] = WorkflowStage.PROMPT_GENERATION.value

        self.logger.info("Executing prompt generation...")
        state = await self.prompt_generator.execute(state)

        # Validate generation results
        if not state.get("generated_prompts"):
            raise ValueError("Prompt generation failed to create prompts")

        return state

    async def _execute_quality_review(self, state: AgentState) -> AgentState:
        """Execute quality review stage."""
        state["current_step"] = WorkflowStage.QUALITY_REVIEW.value

        self.logger.info("Executing quality review...")
        state = await self.quality_reviewer.execute(state)

        # Validate review results
        if "quality_scores" not in state:
            raise ValueError("Quality review failed to generate scores")

        return state

    async def _execute_refinement(self, state: AgentState) -> AgentState:
        """Execute refinement stage."""
        state["current_step"] = WorkflowStage.REFINEMENT.value

        self.logger.info("Executing prompt refinement...")
        state = await self.refinement_agent.execute(state)

        # Update generated_prompts with refined versions for next iteration
        if "refined_prompts" in state:
            state["generated_prompts"] = state["refined_prompts"]

        return state

    async def _finalize_workflow(self, state: AgentState) -> AgentState:
        """Finalize the workflow and prepare final results."""
        state["current_step"] = WorkflowStage.COMPLETION.value

        # Use refined prompts if available, otherwise use generated prompts
        final_prompts = state.get("refined_prompts") or state.get("generated_prompts", [])
        state["final_prompts"] = final_prompts

        # Calculate final metrics
        state["final_metrics"] = self._calculate_final_metrics(state)

        self.logger.info(
            f"Workflow finalized with {len(final_prompts)} prompts. "
            f"Final quality score: {state.get('overall_quality_score', 0.0):.2f}"
        )

        return state

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
            prompt_type = prompt.get("prompt_type", "unknown")
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

    def _create_workflow_result(self, state: AgentState, failed: bool = False) -> Dict[str, Any]:
        """Create the final workflow result."""
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
                "errors": state.get("errors", [])
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

    async def _execute_logic(self, state: AgentState) -> AgentState:
        """Implementation required by base class - not used for orchestrator."""
        # The orchestrator uses execute_workflow instead of this method
        return state

    async def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """Get the current status of a workflow (for async tracking)."""
        # This would typically integrate with a workflow tracking system
        # For now, return a placeholder
        return {
            "workflow_id": workflow_id,
            "status": "unknown",
            "message": "Status tracking not implemented"
        }