# ABOUTME: Claude SDK workflow schemas for content processing with multi-agent orchestration
# ABOUTME: Defines request/response models for Claude Agent SDK-based content processing and prompt generation

from datetime import datetime
from typing import Dict, Any, Optional, List
import uuid

from pydantic import BaseModel, Field, validator

from app.db.models import PromptStatus


class SubagentResult(BaseModel):
    """Schema for tracking individual subagent execution results."""

    agent_name: str = Field(..., description="Name of the subagent (e.g., 'content_analyzer', 'prompt_generator')")
    status: str = Field(..., description="Execution status: 'success', 'failed', 'skipped'")
    execution_time_seconds: float = Field(..., ge=0, description="Time taken for subagent execution")
    input_tokens: int = Field(0, ge=0, description="Number of input tokens consumed")
    output_tokens: int = Field(0, ge=0, description="Number of output tokens generated")
    cost_usd: float = Field(0.0, ge=0, description="Cost in USD for this subagent execution")
    output: Optional[Dict[str, Any]] = Field(None, description="Subagent output data")
    error: Optional[str] = Field(None, description="Error message if execution failed")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "agent_name": "content_analyzer",
                "status": "success",
                "execution_time_seconds": 2.45,
                "input_tokens": 1250,
                "output_tokens": 450,
                "cost_usd": 0.0085,
                "output": {
                    "key_concepts": ["machine learning", "neural networks"],
                    "difficulty_level": 3,
                    "recommended_prompt_count": 8
                },
                "error": None,
                "metadata": {"model": "gpt-5-nano"}
            }
        }


class WorkflowMetrics(BaseModel):
    """Schema for tracking overall workflow execution metrics."""

    total_execution_time_seconds: float = Field(..., ge=0, description="Total workflow execution time")
    total_input_tokens: int = Field(0, ge=0, description="Total input tokens across all subagents")
    total_output_tokens: int = Field(0, ge=0, description="Total output tokens across all subagents")
    total_cost_usd: float = Field(0.0, ge=0, description="Total cost in USD for workflow execution")
    subagent_count: int = Field(0, ge=0, description="Number of subagents executed")
    successful_subagents: int = Field(0, ge=0, description="Number of successful subagent executions")
    failed_subagents: int = Field(0, ge=0, description="Number of failed subagent executions")
    iteration_count: int = Field(1, ge=1, description="Number of refinement iterations performed")
    average_quality_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Average quality score across prompts")
    quality_scores: List[float] = Field(default_factory=list, description="Individual quality scores")
    model_breakdown: Optional[Dict[str, Dict[str, Any]]] = Field(
        None,
        description="Cost and token breakdown by model (e.g., gpt-5-nano, gpt-5-mini)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "total_execution_time_seconds": 12.34,
                "total_input_tokens": 5200,
                "total_output_tokens": 2800,
                "total_cost_usd": 0.0425,
                "subagent_count": 4,
                "successful_subagents": 4,
                "failed_subagents": 0,
                "iteration_count": 2,
                "average_quality_score": 0.87,
                "quality_scores": [0.85, 0.89, 0.91, 0.83],
                "model_breakdown": {
                    "gpt-5-nano": {
                        "input_tokens": 2000,
                        "output_tokens": 800,
                        "cost_usd": 0.0140
                    },
                    "gpt-5-mini": {
                        "input_tokens": 2400,
                        "output_tokens": 1600,
                        "cost_usd": 0.0200
                    },
                    "gpt-5-standard": {
                        "input_tokens": 800,
                        "output_tokens": 400,
                        "cost_usd": 0.0085
                    }
                }
            }
        }


class ContentProcessRequest(BaseModel):
    """Schema for Claude SDK content processing requests."""

    url: str = Field(..., min_length=1, max_length=2048, description="URL of content to process")
    quality_threshold: float = Field(
        0.8,
        ge=0.0,
        le=1.0,
        description="Minimum quality score threshold (0.0-1.0)"
    )
    max_iterations: int = Field(
        3,
        ge=1,
        le=10,
        description="Maximum number of refinement iterations"
    )
    auto_approve: bool = Field(
        False,
        description="Auto-approve prompts meeting quality threshold"
    )
    target_prompt_count: Optional[int] = Field(
        10,
        ge=1,
        le=50,
        description="Target number of prompts to generate"
    )
    mochi_deck_id: Optional[str] = Field(
        None,
        max_length=255,
        description="Mochi deck ID for card creation"
    )
    processing_config: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional processing configuration"
    )

    @validator("url")
    def validate_url(cls, v: str) -> str:
        """Validate URL format."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

    @validator("quality_threshold")
    def validate_quality_threshold(cls, v: float) -> float:
        """Validate quality threshold is reasonable."""
        if v < 0.5:
            raise ValueError("Quality threshold should be at least 0.5 for meaningful filtering")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://example.com/article-about-machine-learning",
                "quality_threshold": 0.85,
                "max_iterations": 3,
                "auto_approve": False,
                "target_prompt_count": 12,
                "mochi_deck_id": "deck_abc123",
                "processing_config": {
                    "enable_caching": True,
                    "difficulty_range": [2, 4]
                }
            }
        }


class PromptSummary(BaseModel):
    """Lightweight prompt summary for response payloads."""

    id: uuid.UUID
    front_content: str = Field(..., max_length=200, description="Truncated front content")
    back_content: str = Field(..., max_length=200, description="Truncated back content")
    quality_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    status: PromptStatus
    iteration: int = Field(1, ge=1, description="Iteration number in which prompt was generated")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "front_content": "What is the primary advantage of using neural networks for...",
                "back_content": "Neural networks excel at learning complex, non-linear...",
                "quality_score": 0.89,
                "status": "approved",
                "iteration": 1
            }
        }


class ContentProcessResponse(BaseModel):
    """Schema for Claude SDK content processing responses."""

    content_id: uuid.UUID = Field(..., description="UUID of the created content record")
    workflow_id: str = Field(..., description="Unique identifier for this workflow execution")
    status: str = Field(..., description="Workflow status: 'completed', 'failed', 'partial'")
    prompts_generated: int = Field(0, ge=0, description="Number of prompts successfully generated")
    prompts_approved: int = Field(0, ge=0, description="Number of prompts meeting quality threshold")
    avg_quality_score: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Average quality score across all generated prompts"
    )
    cost_usd: float = Field(0.0, ge=0, description="Total cost in USD for workflow execution")
    processing_time_seconds: float = Field(..., ge=0, description="Total processing time in seconds")
    workflow_metrics: WorkflowMetrics = Field(..., description="Detailed workflow execution metrics")
    subagent_results: List[SubagentResult] = Field(
        default_factory=list,
        description="Results from individual subagent executions"
    )
    prompts: List[PromptSummary] = Field(
        default_factory=list,
        description="Summary of generated prompts"
    )
    error: Optional[str] = Field(None, description="Error message if workflow failed")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "content_id": "550e8400-e29b-41d4-a716-446655440000",
                "workflow_id": "wf_abc123xyz",
                "status": "completed",
                "prompts_generated": 12,
                "prompts_approved": 10,
                "avg_quality_score": 0.87,
                "cost_usd": 0.0425,
                "processing_time_seconds": 12.34,
                "workflow_metrics": {
                    "total_execution_time_seconds": 12.34,
                    "total_input_tokens": 5200,
                    "total_output_tokens": 2800,
                    "total_cost_usd": 0.0425,
                    "subagent_count": 4,
                    "successful_subagents": 4,
                    "failed_subagents": 0,
                    "iteration_count": 2,
                    "average_quality_score": 0.87,
                    "quality_scores": [0.85, 0.89, 0.91, 0.83, 0.88, 0.86, 0.90, 0.84, 0.87, 0.85],
                    "model_breakdown": {
                        "gpt-5-nano": {"input_tokens": 2000, "output_tokens": 800, "cost_usd": 0.0140},
                        "gpt-5-mini": {"input_tokens": 2400, "output_tokens": 1600, "cost_usd": 0.0200},
                        "gpt-5-standard": {"input_tokens": 800, "output_tokens": 400, "cost_usd": 0.0085}
                    }
                },
                "subagent_results": [
                    {
                        "agent_name": "content_analyzer",
                        "status": "success",
                        "execution_time_seconds": 2.45,
                        "input_tokens": 1250,
                        "output_tokens": 450,
                        "cost_usd": 0.0085,
                        "output": {"key_concepts": ["machine learning", "neural networks"]},
                        "error": None,
                        "metadata": {"model": "gpt-5-nano"}
                    }
                ],
                "prompts": [
                    {
                        "id": "660e8400-e29b-41d4-a716-446655440001",
                        "front_content": "What is the primary advantage of using neural networks...",
                        "back_content": "Neural networks excel at learning complex patterns...",
                        "quality_score": 0.89,
                        "status": "approved",
                        "iteration": 1
                    }
                ],
                "error": None,
                "metadata": {
                    "source_url": "https://example.com/article",
                    "content_hash": "abc123def456",
                    "processing_timestamp": "2025-01-15T10:30:00Z"
                }
            }
        }


class WorkflowStatusRequest(BaseModel):
    """Schema for checking workflow execution status."""

    workflow_id: str = Field(..., description="Unique workflow identifier")

    class Config:
        json_schema_extra = {
            "example": {
                "workflow_id": "wf_abc123xyz"
            }
        }


class WorkflowStatusResponse(BaseModel):
    """Schema for workflow status responses."""

    workflow_id: str
    status: str = Field(..., description="Current status: 'running', 'completed', 'failed'")
    progress: float = Field(0.0, ge=0.0, le=1.0, description="Progress percentage (0.0-1.0)")
    current_stage: Optional[str] = Field(None, description="Current workflow stage")
    started_at: datetime
    completed_at: Optional[datetime] = None
    elapsed_seconds: float = Field(0.0, ge=0)
    estimated_remaining_seconds: Optional[float] = Field(None, ge=0)

    class Config:
        json_schema_extra = {
            "example": {
                "workflow_id": "wf_abc123xyz",
                "status": "running",
                "progress": 0.65,
                "current_stage": "quality_review",
                "started_at": "2025-01-15T10:30:00Z",
                "completed_at": None,
                "elapsed_seconds": 8.5,
                "estimated_remaining_seconds": 4.2
            }
        }
