# Prompt Schemas - Pydantic Models for Type Safety
"""
Pydantic schemas for Prompt model with quality metrics and Mochi integration
support for request/response validation in FastAPI.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
import uuid

from pydantic import BaseModel, Field, validator

from app.db.models import PromptType, QualityMetricType, PromptStatus


# Base schemas
class PromptBase(BaseModel):
    """Base schema with common prompt fields."""

    front_content: str = Field(..., min_length=1, max_length=2000)
    back_content: str = Field(..., min_length=1, max_length=5000)
    prompt_type: PromptType
    difficulty_level: Optional[int] = Field(None, ge=1, le=5)
    concepts: Optional[List[str]] = None
    quality_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    metadata: Optional[Dict[str, Any]] = None

    # Legacy fields for backward compatibility
    question: Optional[str] = Field(None, min_length=1, max_length=2000)
    answer: Optional[str] = Field(None, min_length=1, max_length=5000)
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    source_context: Optional[str] = Field(None, max_length=1000)
    tags: Optional[List[str]] = None

    @validator("question", "answer")
    def validate_text_fields(cls, v: str) -> str:
        """Validate text fields are not empty."""
        if not v.strip():
            raise ValueError("Text field cannot be empty")
        return v.strip()

    @validator("tags")
    def validate_tags(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate tags are not empty and reasonable length."""
        if v:
            # Remove empty tags and limit length
            valid_tags = [tag.strip() for tag in v if tag.strip()]
            if len(valid_tags) > 20:
                raise ValueError("Cannot have more than 20 tags")
            return valid_tags[:20]
        return v


class PromptCreate(PromptBase):
    """Schema for creating new prompts."""

    content_id: uuid.UUID


class PromptUpdate(BaseModel):
    """Schema for updating existing prompts."""

    question: Optional[str] = Field(None, min_length=1, max_length=2000)
    answer: Optional[str] = Field(None, min_length=1, max_length=5000)
    prompt_type: Optional[PromptType] = None
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    difficulty_level: Optional[int] = Field(None, ge=1, le=5)
    source_context: Optional[str] = Field(None, max_length=1000)
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    edit_reason: Optional[str] = Field(None, max_length=500)

    @validator("question", "answer")
    def validate_text_fields(cls, v: Optional[str]) -> Optional[str]:
        """Validate text fields are not empty if provided."""
        if v is not None and not v.strip():
            raise ValueError("Text field cannot be empty")
        return v.strip() if v else v


class PromptInDB(PromptBase):
    """Schema for prompts as stored in database."""

    id: uuid.UUID
    content_id: uuid.UUID
    version: int
    is_edited: bool
    edit_reason: Optional[str] = None
    mochi_card_id: Optional[str] = None
    mochi_deck_id: Optional[str] = None
    mochi_status: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    edited_at: Optional[datetime] = None
    sent_to_mochi_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PromptResponse(PromptInDB):
    """Schema for prompt API responses."""

    quality_score: Optional[float] = Field(
        None, description="Overall quality score from metrics"
    )
    needs_review: Optional[bool] = Field(
        None, description="Whether prompt needs quality review"
    )


class PromptSummary(BaseModel):
    """Lightweight schema for prompt listings."""

    id: uuid.UUID
    question: str = Field(..., max_length=200)  # Truncated for summaries
    prompt_type: PromptType
    confidence_score: Optional[float]
    is_edited: bool
    mochi_card_id: Optional[str]
    created_at: datetime
    quality_score: Optional[float] = None

    class Config:
        from_attributes = True


class PromptWithQuality(PromptResponse):
    """Schema for prompts with quality metrics."""

    quality_metrics: List["QualityMetricResponse"] = Field(default_factory=list)

    class Config:
        from_attributes = True


# Quality metric schemas
class QualityMetricBase(BaseModel):
    """Base schema for quality metrics."""

    metric_type: QualityMetricType
    score: float = Field(..., ge=0.0, le=1.0)
    weight: float = Field(1.0, ge=0.0, le=10.0)
    evaluator_model: Optional[str] = Field(None, max_length=100)
    reasoning: Optional[str] = None
    feedback: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class QualityMetricCreate(QualityMetricBase):
    """Schema for creating quality metrics."""

    prompt_id: uuid.UUID
    evaluation_prompt: Optional[str] = None


class QualityMetricUpdate(BaseModel):
    """Schema for updating quality metrics."""

    score: Optional[float] = Field(None, ge=0.0, le=1.0)
    weight: Optional[float] = Field(None, ge=0.0, le=10.0)
    reasoning: Optional[str] = None
    feedback: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class QualityMetricInDB(QualityMetricBase):
    """Schema for quality metrics as stored in database."""

    id: uuid.UUID
    prompt_id: uuid.UUID
    evaluation_prompt: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class QualityMetricResponse(QualityMetricInDB):
    """Schema for quality metric API responses."""
    pass


# Prompt generation and processing schemas
class PromptGenerationRequest(BaseModel):
    """Schema for prompt generation requests."""

    content_id: uuid.UUID
    target_count: Optional[int] = Field(10, ge=1, le=50)
    prompt_types: Optional[List[PromptType]] = None
    difficulty_levels: Optional[List[int]] = Field(None, ge=1, le=5)
    generation_config: Optional[Dict[str, Any]] = None

    @validator("target_count")
    def validate_target_count(cls, v: int) -> int:
        """Validate target count is reasonable."""
        if not 1 <= v <= 50:
            raise ValueError("Target count must be between 1 and 50")
        return v


class PromptGenerationResponse(BaseModel):
    """Schema for prompt generation responses."""

    content_id: uuid.UUID
    total_generated: int
    prompts: List[PromptResponse]
    generation_stats: Optional[Dict[str, Any]] = None


class PromptBatchUpdate(BaseModel):
    """Schema for batch prompt updates."""

    prompt_updates: List[Dict[str, Any]] = Field(..., min_items=1, max_items=100)

    @validator("prompt_updates")
    def validate_batch_size(cls, v: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate batch size is reasonable."""
        if len(v) > 100:
            raise ValueError("Batch size cannot exceed 100 prompts")
        return v


class PromptBatchUpdateResponse(BaseModel):
    """Schema for batch update responses."""

    total_items: int
    updated_items: int
    failed_items: int
    results: List[Dict[str, Any]]


# Mochi integration schemas
class MochiCardRequest(BaseModel):
    """Schema for Mochi card creation requests."""

    prompt_id: uuid.UUID
    deck_id: Optional[str] = None
    additional_fields: Optional[Dict[str, Any]] = None


class MochiCardResponse(BaseModel):
    """Schema for Mochi card creation responses."""

    prompt_id: uuid.UUID
    mochi_card_id: str
    mochi_deck_id: Optional[str] = None
    status: str
    created_at: datetime


class MochiBatchSyncRequest(BaseModel):
    """Schema for batch Mochi synchronization."""

    prompt_ids: List[uuid.UUID] = Field(..., min_items=1, max_items=50)
    deck_id: Optional[str] = None
    sync_config: Optional[Dict[str, Any]] = None

    @validator("prompt_ids")
    def validate_batch_size(cls, v: List[uuid.UUID]) -> List[uuid.UUID]:
        """Validate batch size is reasonable."""
        if len(v) > 50:
            raise ValueError("Batch size cannot exceed 50 prompts")
        return v


class MochiBatchSyncResponse(BaseModel):
    """Schema for batch sync responses."""

    total_prompts: int
    synced_prompts: int
    failed_prompts: int
    results: List[MochiCardResponse]


# Search and filtering schemas
class PromptSearchRequest(BaseModel):
    """Schema for prompt search requests."""

    query: str = Field(..., min_length=1, max_length=500)
    content_id: Optional[uuid.UUID] = None
    prompt_types: Optional[List[PromptType]] = None
    min_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    max_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    is_edited: Optional[bool] = None
    has_mochi_card: Optional[bool] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    limit: Optional[int] = Field(50, ge=1, le=1000)
    offset: Optional[int] = Field(0, ge=0)

    @validator("query")
    def validate_query(cls, v: str) -> str:
        """Validate search query is not empty."""
        if not v.strip():
            raise ValueError("Search query cannot be empty")
        return v.strip()

    @validator("max_confidence")
    def validate_confidence_range(cls, v: Optional[float], values) -> Optional[float]:
        """Validate confidence range is logical."""
        min_conf = values.get("min_confidence")
        if v is not None and min_conf is not None and v < min_conf:
            raise ValueError("max_confidence must be greater than min_confidence")
        return v


class PromptSearchResponse(BaseModel):
    """Schema for prompt search responses."""

    total_count: int
    results: List[PromptSummary]
    facets: Optional[Dict[str, Any]] = None


# Statistics schemas
class PromptStatistics(BaseModel):
    """Schema for prompt statistics."""

    total_prompts: int
    type_distribution: Dict[str, int]
    quality_stats: Dict[str, float]
    mochi_sync_stats: Dict[str, int]
    recent_activity: Dict[str, int]
    editing_patterns: Optional[Dict[str, Any]] = None


# Additional schemas for service layer integration

class PromptCreateRequest(BaseModel):
    """Schema for creating prompts via service layer."""

    content_id: uuid.UUID
    front_content: str = Field(..., min_length=1, max_length=2000)
    back_content: str = Field(..., min_length=1, max_length=5000)
    prompt_type: PromptType
    difficulty_level: Optional[int] = Field(None, ge=1, le=5)
    concepts: Optional[List[str]] = None
    quality_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    metadata: Optional[Dict[str, Any]] = None


class PromptUpdateRequest(BaseModel):
    """Schema for updating prompts via service layer."""

    front_content: Optional[str] = Field(None, min_length=1, max_length=2000)
    back_content: Optional[str] = Field(None, min_length=1, max_length=5000)
    difficulty_level: Optional[int] = Field(None, ge=1, le=5)
    concepts: Optional[List[str]] = None
    quality_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    status: Optional[PromptStatus] = None
    metadata: Optional[Dict[str, Any]] = None


class PromptResponse(BaseModel):
    """Schema for prompt service responses."""

    id: uuid.UUID
    content_id: uuid.UUID
    front_content: str
    back_content: str
    prompt_type: PromptType
    difficulty_level: Optional[int]
    concepts: Optional[List[str]]
    quality_score: Optional[float]
    status: PromptStatus
    created_at: datetime
    updated_at: datetime
    metadata: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True


class PromptBatchCreateRequest(BaseModel):
    """Schema for batch prompt creation."""

    prompts: List[PromptCreateRequest] = Field(..., min_items=1, max_items=50)


class MochiCardRequest(BaseModel):
    """Schema for Mochi card creation requests."""

    prompt_id: uuid.UUID
    deck_id: Optional[str] = None
    template_id: Optional[str] = None
    tags: Optional[List[str]] = None


class MochiCardBatchRequest(BaseModel):
    """Schema for batch Mochi card creation."""

    prompt_ids: List[uuid.UUID] = Field(..., min_items=1, max_items=50)
    deck_id: Optional[str] = None
    template_id: Optional[str] = None
    tags: Optional[List[str]] = None
    max_concurrent: Optional[int] = Field(3, ge=1, le=10)


# Forward reference resolution (if needed)
PromptWithQuality.model_rebuild()