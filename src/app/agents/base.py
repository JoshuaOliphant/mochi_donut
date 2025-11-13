# Agent Base Classes and Infrastructure
"""
Base classes and infrastructure for the multi-agent AI system.
Provides common functionality, state management, error handling, and cost tracking.
"""

import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TypedDict, Union
from datetime import datetime
from enum import Enum

from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.core.config import settings


class AgentError(Exception):
    """Base exception for agent-related errors."""

    def __init__(self, message: str, agent_name: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.agent_name = agent_name
        self.details = details or {}
        super().__init__(f"[{agent_name}] {message}")


class AgentStatus(Enum):
    """Agent execution status."""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class ModelConfig(BaseModel):
    """Configuration for LLM models."""
    name: str
    cost_per_input_token: float  # Cost per 1M input tokens
    cost_per_output_token: float  # Cost per 1M output tokens
    max_tokens: int = 4096
    temperature: float = 0.1
    model_kwargs: Dict[str, Any] = Field(default_factory=dict)


# Model configurations with 2025 pricing
MODEL_CONFIGS = {
    "gpt-5-nano": ModelConfig(
        name="gpt-5-nano",
        cost_per_input_token=0.05,
        cost_per_output_token=0.40,
        max_tokens=4096,
        temperature=0.1
    ),
    "gpt-5-mini": ModelConfig(
        name="gpt-5-mini",
        cost_per_input_token=0.25,
        cost_per_output_token=2.0,
        max_tokens=8192,
        temperature=0.1
    ),
    "gpt-5-standard": ModelConfig(
        name="gpt-5-standard",
        cost_per_input_token=1.25,
        cost_per_output_token=10.0,
        max_tokens=8192,
        temperature=0.1
    ),
    # Fallback to available models if GPT-5 series not available
    "gpt-4o-mini": ModelConfig(
        name="gpt-4o-mini",
        cost_per_input_token=0.15,
        cost_per_output_token=0.60,
        max_tokens=4096,
        temperature=0.1
    ),
    "gpt-4o": ModelConfig(
        name="gpt-4o",
        cost_per_input_token=2.50,
        cost_per_output_token=10.00,
        max_tokens=4096,
        temperature=0.1
    )
}


@dataclass
class CostTracker:
    """Tracks costs for model usage."""

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost: float = 0.0
    model_usage: Dict[str, Dict[str, Union[int, float]]] = field(default_factory=dict)

    def add_usage(self, model_name: str, input_tokens: int, output_tokens: int) -> float:
        """Add usage and calculate cost for a model call."""
        if model_name not in MODEL_CONFIGS:
            logging.warning(f"Unknown model {model_name}, using fallback cost calculation")
            config = MODEL_CONFIGS["gpt-4o"]  # Fallback
        else:
            config = MODEL_CONFIGS[model_name]

        # Calculate cost (rates are per 1M tokens)
        input_cost = (input_tokens / 1_000_000) * config.cost_per_input_token
        output_cost = (output_tokens / 1_000_000) * config.cost_per_output_token
        call_cost = input_cost + output_cost

        # Update totals
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost += call_cost

        # Update model-specific usage
        if model_name not in self.model_usage:
            self.model_usage[model_name] = {
                "input_tokens": 0,
                "output_tokens": 0,
                "cost": 0.0,
                "calls": 0
            }

        self.model_usage[model_name]["input_tokens"] += input_tokens
        self.model_usage[model_name]["output_tokens"] += output_tokens
        self.model_usage[model_name]["cost"] += call_cost
        self.model_usage[model_name]["calls"] += 1

        return call_cost

    def get_summary(self) -> Dict[str, Any]:
        """Get cost tracking summary."""
        return {
            "total_cost": round(self.total_cost, 4),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "model_breakdown": self.model_usage
        }


class AgentState(TypedDict, total=False):
    """Shared state between agents in the workflow."""

    # Input data
    content_id: str
    content_text: str
    content_metadata: Dict[str, Any]

    # Processing state
    current_step: str
    workflow_id: str
    started_at: datetime

    # Agent outputs
    key_concepts: List[str]
    generated_prompts: List[Dict[str, Any]]
    quality_scores: List[Dict[str, Any]]
    refined_prompts: List[Dict[str, Any]]

    # Quality and iteration tracking
    overall_quality_score: Optional[float]
    iteration_count: int
    max_iterations: int
    quality_threshold: float

    # Error handling
    errors: List[Dict[str, Any]]
    retry_count: int
    max_retries: int

    # Cost tracking
    cost_tracker: CostTracker

    # Final results
    final_prompts: List[Dict[str, Any]]
    status: AgentStatus
    completed_at: Optional[datetime]


class AgentBase(ABC):
    """Base class for all agents in the system."""

    def __init__(
        self,
        name: str,
        model_name: str,
        system_prompt: str,
        max_retries: int = 3,
        timeout: int = 60
    ):
        self.name = name
        self.model_name = model_name
        self.system_prompt = system_prompt
        self.max_retries = max_retries
        self.timeout = timeout
        self.logger = logging.getLogger(f"agent.{name}")

        # Initialize LLM
        self.llm = self._create_llm()

    def _create_llm(self) -> ChatOpenAI:
        """Create LLM instance with proper configuration."""
        config = MODEL_CONFIGS.get(self.model_name)
        if not config:
            self.logger.warning(f"Model {self.model_name} not found, falling back to gpt-4o-mini")
            config = MODEL_CONFIGS["gpt-4o-mini"]
            self.model_name = "gpt-4o-mini"

        return ChatOpenAI(
            model=config.name,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            request_timeout=self.timeout,
            **config.model_kwargs
        )

    async def execute(self, state: AgentState) -> AgentState:
        """Execute the agent with retry logic and error handling."""
        retry_count = 0
        last_error = None

        while retry_count <= self.max_retries:
            try:
                self.logger.info(f"Executing agent {self.name} (attempt {retry_count + 1})")

                # Update state
                state["current_step"] = self.name
                state["retry_count"] = retry_count

                # Execute the agent logic
                start_time = time.time()
                updated_state = await self._execute_logic(state)
                execution_time = time.time() - start_time

                self.logger.info(
                    f"Agent {self.name} completed successfully in {execution_time:.2f}s"
                )

                return updated_state

            except Exception as e:
                retry_count += 1
                last_error = e

                error_info = {
                    "agent": self.name,
                    "attempt": retry_count,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }

                if "errors" not in state:
                    state["errors"] = []
                state["errors"].append(error_info)

                self.logger.error(f"Agent {self.name} failed (attempt {retry_count}): {e}")

                if retry_count <= self.max_retries:
                    await self._handle_retry(state, retry_count, e)
                else:
                    break

        # All retries exhausted
        raise AgentError(
            f"Agent failed after {self.max_retries + 1} attempts",
            self.name,
            {"last_error": str(last_error), "total_attempts": retry_count}
        )

    @abstractmethod
    async def _execute_logic(self, state: AgentState) -> AgentState:
        """Implement the core agent logic."""
        pass

    async def _handle_retry(self, state: AgentState, attempt: int, error: Exception):
        """Handle retry logic. Can be overridden by subclasses."""
        # Exponential backoff
        wait_time = min(2 ** attempt, 30)  # Cap at 30 seconds
        self.logger.info(f"Retrying {self.name} in {wait_time} seconds...")
        await self._sleep(wait_time)

    async def _sleep(self, seconds: float):
        """Async sleep helper."""
        import asyncio
        await asyncio.sleep(seconds)

    async def _call_llm(
        self,
        messages: List[BaseMessage],
        parser: Optional[PydanticOutputParser] = None,
        **kwargs
    ) -> Union[str, BaseModel]:
        """Call LLM with cost tracking."""
        try:
            response = await self.llm.ainvoke(messages, **kwargs)

            # Track costs (using rough estimation if token counts not available)
            # Note: In production, you'd get actual token counts from the response
            input_tokens = sum(len(msg.content.split()) * 1.3 for msg in messages)  # Rough estimate
            output_tokens = len(response.content.split()) * 1.3  # Rough estimate

            # This would be replaced with actual token counts from the response
            # For now, using estimation

            if parser:
                return parser.parse(response.content)
            return response.content

        except Exception as e:
            self.logger.error(f"LLM call failed: {e}")
            raise AgentError(f"LLM call failed: {str(e)}", self.name)

    def _create_prompt_template(self, template: str) -> ChatPromptTemplate:
        """Create a chat prompt template."""
        return ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", template)
        ])

    def _add_cost_tracking(self, state: AgentState, cost: float):
        """Add cost tracking to state."""
        if "cost_tracker" not in state:
            state["cost_tracker"] = CostTracker()

        # In a real implementation, you'd track actual token usage
        # This is a simplified version
        state["cost_tracker"].total_cost += cost


class OutputSchema(BaseModel):
    """Base output schema for agent responses."""

    success: bool = Field(description="Whether the operation was successful")
    message: str = Field(description="Status message or error description")
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence score for the output"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the operation"
    )