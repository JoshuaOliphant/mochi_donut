# Agent Configuration
"""
Configuration for the multi-agent AI system.
Centralizes all agent-related settings and provides validation.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, validator
from enum import Enum

from app.core.config import settings


class AgentModel(str, Enum):
    """Available AI models for agents."""
    GPT_5_NANO = "gpt-5-nano"
    GPT_5_MINI = "gpt-5-mini"
    GPT_5_STANDARD = "gpt-5-standard"
    GPT_4O_MINI = "gpt-4o-mini"  # Fallback
    GPT_4O = "gpt-4o"  # Fallback


class AgentType(str, Enum):
    """Types of agents in the system."""
    CONTENT_ANALYZER = "content_analyzer"
    PROMPT_GENERATOR = "prompt_generator"
    QUALITY_REVIEWER = "quality_reviewer"
    REFINEMENT_AGENT = "refinement_agent"
    ORCHESTRATOR = "orchestrator"


class ModelPricing(BaseModel):
    """Pricing configuration for a model."""
    input_cost_per_million: float = Field(description="Cost per 1M input tokens")
    output_cost_per_million: float = Field(description="Cost per 1M output tokens")
    max_tokens: int = Field(default=4096, description="Maximum output tokens")
    context_length: int = Field(default=128000, description="Maximum context length")


class AgentConfig(BaseModel):
    """Configuration for an individual agent."""
    name: str
    model: AgentModel
    description: str
    max_retries: int = Field(default=3, ge=0, le=10)
    timeout_seconds: int = Field(default=60, ge=10, le=300)
    temperature: float = Field(default=0.1, ge=0.0, le=1.0)
    enabled: bool = Field(default=True)
    custom_instructions: Optional[str] = None


class WorkflowConfig(BaseModel):
    """Configuration for the workflow system."""
    quality_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    max_iterations: int = Field(default=3, ge=1, le=10)
    enable_refinement: bool = Field(default=True)
    enable_streaming: bool = Field(default=True)
    cost_limit_per_workflow: float = Field(default=5.0, ge=0.1, le=100.0)

    @validator('quality_threshold')
    def validate_quality_threshold(cls, v):
        if v < 0.5:
            raise ValueError('Quality threshold should be at least 0.5 for meaningful results')
        return v


class MultiAgentSystemConfig(BaseModel):
    """Complete configuration for the multi-agent system."""

    # Model pricing (2025 rates)
    model_pricing: Dict[AgentModel, ModelPricing] = {
        AgentModel.GPT_5_NANO: ModelPricing(
            input_cost_per_million=0.05,
            output_cost_per_million=0.40,
            max_tokens=4096,
            context_length=128000
        ),
        AgentModel.GPT_5_MINI: ModelPricing(
            input_cost_per_million=0.25,
            output_cost_per_million=2.0,
            max_tokens=8192,
            context_length=128000
        ),
        AgentModel.GPT_5_STANDARD: ModelPricing(
            input_cost_per_million=1.25,
            output_cost_per_million=10.0,
            max_tokens=8192,
            context_length=128000
        ),
        AgentModel.GPT_4O_MINI: ModelPricing(
            input_cost_per_million=0.15,
            output_cost_per_million=0.60,
            max_tokens=4096,
            context_length=128000
        ),
        AgentModel.GPT_4O: ModelPricing(
            input_cost_per_million=2.50,
            output_cost_per_million=10.00,
            max_tokens=4096,
            context_length=128000
        )
    }

    # Agent configurations
    agents: Dict[AgentType, AgentConfig] = {
        AgentType.CONTENT_ANALYZER: AgentConfig(
            name="Content Analyzer",
            model=AgentModel.GPT_5_NANO,
            description="Analyzes content and extracts key concepts for prompt generation",
            max_retries=3,
            timeout_seconds=30,
            temperature=0.1
        ),
        AgentType.PROMPT_GENERATOR: AgentConfig(
            name="Prompt Generator",
            model=AgentModel.GPT_5_MINI,
            description="Generates high-quality flashcard prompts following Matuschak's principles",
            max_retries=3,
            timeout_seconds=45,
            temperature=0.1
        ),
        AgentType.QUALITY_REVIEWER: AgentConfig(
            name="Quality Reviewer",
            model=AgentModel.GPT_5_STANDARD,
            description="Reviews prompt quality using LLM-as-judge methodology",
            max_retries=2,
            timeout_seconds=60,
            temperature=0.0  # More deterministic for quality assessment
        ),
        AgentType.REFINEMENT_AGENT: AgentConfig(
            name="Refinement Agent",
            model=AgentModel.GPT_5_MINI,
            description="Refines prompts based on quality feedback",
            max_retries=3,
            timeout_seconds=45,
            temperature=0.1
        ),
        AgentType.ORCHESTRATOR: AgentConfig(
            name="Orchestrator",
            model=AgentModel.GPT_5_MINI,
            description="Coordinates the multi-agent workflow",
            max_retries=2,
            timeout_seconds=30,
            temperature=0.0
        )
    }

    # Workflow configuration
    workflow: WorkflowConfig = WorkflowConfig()

    # Feature flags
    enable_langgraph: bool = Field(default=True)
    enable_cost_tracking: bool = Field(default=True)
    enable_quality_metrics: bool = Field(default=True)
    enable_caching: bool = Field(default=True)

    # Performance settings
    concurrent_agents: int = Field(default=1, ge=1, le=5)
    batch_size: int = Field(default=10, ge=1, le=100)

    # Monitoring and logging
    log_level: str = Field(default="INFO")
    enable_telemetry: bool = Field(default=True)
    metrics_export_interval: int = Field(default=60, ge=10, le=300)


# Create default configuration
def get_agent_config() -> MultiAgentSystemConfig:
    """Get the default agent configuration with environment overrides."""
    config = MultiAgentSystemConfig()

    # Override with environment settings if available
    if hasattr(settings, 'AGENT_QUALITY_THRESHOLD'):
        config.workflow.quality_threshold = settings.AGENT_QUALITY_THRESHOLD

    if hasattr(settings, 'AGENT_MAX_ITERATIONS'):
        config.workflow.max_iterations = settings.AGENT_MAX_ITERATIONS

    if hasattr(settings, 'AGENT_COST_LIMIT'):
        config.workflow.cost_limit_per_workflow = settings.AGENT_COST_LIMIT

    # Disable expensive models in development
    if hasattr(settings, 'ENVIRONMENT') and settings.ENVIRONMENT == "development":
        # Use cheaper models for development
        config.agents[AgentType.QUALITY_REVIEWER].model = AgentModel.GPT_5_MINI
        config.workflow.cost_limit_per_workflow = 1.0

    return config


# Validation functions
def validate_model_availability(model: AgentModel) -> bool:
    """Validate that a model is available."""
    # In a real implementation, this would check API availability
    # For now, assume all models are available
    return True


def estimate_workflow_cost(
    content_length: int,
    target_prompts: int,
    config: MultiAgentSystemConfig
) -> Dict[str, Any]:
    """Estimate the cost of running a workflow."""
    # Rough token estimates
    content_tokens = content_length * 1.3  # Approximation

    costs = {}
    total_cost = 0.0

    # Content analysis cost (GPT-5-nano)
    analyzer_config = config.agents[AgentType.CONTENT_ANALYZER]
    analyzer_pricing = config.model_pricing[analyzer_config.model]

    analysis_input = content_tokens + 500  # Content + analysis prompt
    analysis_output = 300  # Estimated analysis output

    analysis_cost = (
        (analysis_input / 1_000_000) * analyzer_pricing.input_cost_per_million +
        (analysis_output / 1_000_000) * analyzer_pricing.output_cost_per_million
    )
    costs["content_analysis"] = analysis_cost
    total_cost += analysis_cost

    # Prompt generation cost (GPT-5-mini)
    generator_config = config.agents[AgentType.PROMPT_GENERATOR]
    generator_pricing = config.model_pricing[generator_config.model]

    generation_input = content_tokens * 0.5 + target_prompts * 50
    generation_output = target_prompts * 100

    generation_cost = (
        (generation_input / 1_000_000) * generator_pricing.input_cost_per_million +
        (generation_output / 1_000_000) * generator_pricing.output_cost_per_million
    )
    costs["prompt_generation"] = generation_cost
    total_cost += generation_cost

    # Quality review cost (GPT-5-standard)
    reviewer_config = config.agents[AgentType.QUALITY_REVIEWER]
    reviewer_pricing = config.model_pricing[reviewer_config.model]

    review_input = target_prompts * 150  # Each prompt with review instructions
    review_output = target_prompts * 100  # Quality feedback

    review_cost = (
        (review_input / 1_000_000) * reviewer_pricing.input_cost_per_million +
        (review_output / 1_000_000) * reviewer_pricing.output_cost_per_million
    )
    costs["quality_review"] = review_cost
    total_cost += review_cost

    # Refinement cost (assume 30% of prompts need refinement)
    refinement_ratio = 0.3
    refiner_config = config.agents[AgentType.REFINEMENT_AGENT]
    refiner_pricing = config.model_pricing[refiner_config.model]

    refinement_input = target_prompts * refinement_ratio * 200
    refinement_output = target_prompts * refinement_ratio * 100

    refinement_cost = (
        (refinement_input / 1_000_000) * refiner_pricing.input_cost_per_million +
        (refinement_output / 1_000_000) * refiner_pricing.output_cost_per_million
    )
    costs["refinement"] = refinement_cost
    total_cost += refinement_cost

    return {
        "estimated_total_cost": round(total_cost, 4),
        "cost_breakdown": {k: round(v, 4) for k, v in costs.items()},
        "within_budget": total_cost <= config.workflow.cost_limit_per_workflow,
        "cost_limit": config.workflow.cost_limit_per_workflow
    }


# Export the default configuration
agent_config = get_agent_config()