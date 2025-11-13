# Content Schemas - Pydantic Models for Type Safety
"""
Pydantic schemas for Content model with request/response validation
and data transfer object patterns for FastAPI integration.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
import uuid

from pydantic import BaseModel, Field, validator

from app.db.models import SourceType, ProcessingStatus


# Base schemas
class ContentBase(BaseModel):
    """Base schema with common content fields."""

    source_url: Optional[str] = Field(None, max_length=2048)
    source_type: SourceType
    title: Optional[str] = Field(None, max_length=500)
    author: Optional[str] = Field(None, max_length=255)
    markdown_content: str = Field(..., min_length=1)
    word_count: Optional[int] = Field(None, ge=0)
    estimated_reading_time: Optional[int] = Field(None, ge=0)
    metadata: Optional[Dict[str, Any]] = None
    processing_config: Optional[Dict[str, Any]] = None

    @validator("source_url")
    def validate_source_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate source URL format."""
        if v and not v.startswith(("http://", "https://", "file://")):
            raise ValueError("Source URL must start with http://, https://, or file://")
        return v

    @validator("markdown_content")
    def validate_markdown_content(cls, v: str) -> str:
        """Validate markdown content is not empty."""
        if not v.strip():
            raise ValueError("Markdown content cannot be empty")
        return v


class ContentCreate(ContentBase):
    """Schema for creating new content."""

    content_hash: Optional[str] = Field(None, max_length=64)

    @validator("content_hash")
    def validate_content_hash(cls, v: Optional[str]) -> Optional[str]:
        """Validate content hash format."""
        if v and len(v) != 64:
            raise ValueError("Content hash must be 64 characters (SHA-256)")
        return v


class ContentUpdate(BaseModel):
    """Schema for updating existing content."""

    source_url: Optional[str] = Field(None, max_length=2048)
    title: Optional[str] = Field(None, max_length=500)
    author: Optional[str] = Field(None, max_length=255)
    markdown_content: Optional[str] = Field(None, min_length=1)
    word_count: Optional[int] = Field(None, ge=0)
    estimated_reading_time: Optional[int] = Field(None, ge=0)
    processing_status: Optional[ProcessingStatus] = None
    metadata: Optional[Dict[str, Any]] = None
    processing_config: Optional[Dict[str, Any]] = None

    @validator("source_url")
    def validate_source_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate source URL format."""
        if v and not v.startswith(("http://", "https://", "file://")):
            raise ValueError("Source URL must start with http://, https://, or file://")
        return v


class ContentInDB(ContentBase):
    """Schema for content as stored in database."""

    id: uuid.UUID
    content_hash: str = Field(..., max_length=64)
    raw_text: Optional[str] = None
    chroma_collection: Optional[str] = Field(None, max_length=255)
    chroma_document_id: Optional[str] = Field(None, max_length=255)
    processing_status: ProcessingStatus
    created_at: datetime
    updated_at: datetime
    processed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ContentResponse(ContentInDB):
    """Schema for content API responses."""

    prompt_count: Optional[int] = Field(None, description="Number of associated prompts")
    processing_stats: Optional[Dict[str, Any]] = Field(
        None, description="Processing statistics"
    )


class ContentSummary(BaseModel):
    """Lightweight schema for content listings."""

    id: uuid.UUID
    title: Optional[str]
    source_type: SourceType
    processing_status: ProcessingStatus
    word_count: Optional[int]
    estimated_reading_time: Optional[int]
    created_at: datetime
    updated_at: datetime
    prompt_count: Optional[int] = None

    class Config:
        from_attributes = True


class ContentWithPrompts(ContentResponse):
    """Schema for content with associated prompts."""

    prompts: List["PromptSummary"] = Field(default_factory=list)

    class Config:
        from_attributes = True


# Processing schemas
class ContentProcessingRequest(BaseModel):
    """Schema for content processing requests."""

    source_url: Optional[str] = Field(None, max_length=2048)
    source_type: SourceType
    raw_content: Optional[str] = None
    processing_config: Optional[Dict[str, Any]] = None
    priority: Optional[int] = Field(5, ge=1, le=10)

    @validator("priority")
    def validate_priority(cls, v: int) -> int:
        """Validate priority is within range."""
        if not 1 <= v <= 10:
            raise ValueError("Priority must be between 1 and 10")
        return v

    @validator("source_url", "raw_content")
    def validate_content_source(cls, v, values):
        """Ensure either source_url or raw_content is provided."""
        source_url = values.get("source_url")
        raw_content = v if "raw_content" in values else values.get("raw_content")

        if not source_url and not raw_content:
            raise ValueError("Either source_url or raw_content must be provided")
        return v


class ContentProcessingResponse(BaseModel):
    """Schema for content processing responses."""

    content_id: uuid.UUID
    processing_status: ProcessingStatus
    message: str
    estimated_completion: Optional[datetime] = None


class ContentBatchProcessingRequest(BaseModel):
    """Schema for batch content processing."""

    items: List[ContentProcessingRequest] = Field(..., min_items=1, max_items=100)
    batch_config: Optional[Dict[str, Any]] = None

    @validator("items")
    def validate_batch_size(cls, v: List[ContentProcessingRequest]) -> List[ContentProcessingRequest]:
        """Validate batch size is reasonable."""
        if len(v) > 100:
            raise ValueError("Batch size cannot exceed 100 items")
        return v


class ContentBatchProcessingResponse(BaseModel):
    """Schema for batch processing responses."""

    batch_id: str
    total_items: int
    accepted_items: int
    rejected_items: int
    results: List[ContentProcessingResponse]


# Search and filtering schemas
class ContentSearchRequest(BaseModel):
    """Schema for content search requests."""

    query: str = Field(..., min_length=1, max_length=500)
    source_types: Optional[List[SourceType]] = None
    processing_status: Optional[List[ProcessingStatus]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    min_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    similarity_threshold: Optional[float] = Field(0.7, ge=0.0, le=1.0)
    limit: Optional[int] = Field(50, ge=1, le=1000)
    offset: Optional[int] = Field(0, ge=0)

    @validator("query")
    def validate_query(cls, v: str) -> str:
        """Validate search query is not empty."""
        if not v.strip():
            raise ValueError("Search query cannot be empty")
        return v.strip()


class ContentSearchResponse(BaseModel):
    """Schema for content search responses."""

    query: str
    results: List[Dict[str, Any]]
    total_results: int
    similarity_threshold: float
    search_metadata: Dict[str, Any]


# Statistics schemas
class ContentStatistics(BaseModel):
    """Schema for content statistics."""

    total_content: int
    processing_stats: Dict[str, int]
    source_type_stats: Dict[str, int]
    recent_activity: Dict[str, int]
    quality_metrics: Optional[Dict[str, float]] = None


# Forward reference resolution
from app.schemas.prompt import PromptSummary

ContentWithPrompts.model_rebuild()