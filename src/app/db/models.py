# Database Models for Mochi Donut - SQLAlchemy 2.0 Async
"""
Production-ready SQLAlchemy 2.0 models with async patterns for the Mochi Donut
spaced repetition learning system. Follows FastAPI best practices and includes
proper indexing for performance optimization.
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import List, Optional
import uuid

from sqlalchemy import (
    JSON, Boolean, DateTime, Enum, Float, ForeignKey, Index, String, Text,
    UniqueConstraint, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all database models with async support."""
    pass


# Enums for type safety
class SourceType(PyEnum):
    """Content source types supported by the system."""
    WEB = "web"
    PDF = "pdf"
    YOUTUBE = "youtube"
    NOTION = "notion"
    RAINDROP = "raindrop"
    MARKDOWN = "markdown"


class PromptType(PyEnum):
    """Types of prompts following Andy Matuschak's patterns."""
    FACTUAL = "factual"
    PROCEDURAL = "procedural"
    CONCEPTUAL = "conceptual"
    OPEN_LIST = "open_list"
    CLOZE_DELETION = "cloze_deletion"


class ProcessingStatus(PyEnum):
    """Status of content processing through the system."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class QualityMetricType(PyEnum):
    """Quality metrics for prompt evaluation."""
    FOCUS_SPECIFICITY = "focus_specificity"
    PRECISION_CLARITY = "precision_clarity"
    COGNITIVE_LOAD = "cognitive_load"
    RETRIEVAL_PRACTICE = "retrieval_practice"
    OVERALL_QUALITY = "overall_quality"


class AgentType(PyEnum):
    """Types of AI agents in the system."""
    ORCHESTRATOR = "orchestrator"
    CONTENT_ANALYSIS = "content_analysis"
    PROMPT_GENERATION = "prompt_generation"
    QUALITY_REVIEW = "quality_review"
    REFINEMENT = "refinement"


# Core Models

class Content(Base):
    """
    Stores processed content from various sources with unified markdown format.
    Includes metadata for semantic search and duplicate detection.
    """
    __tablename__ = "contents"

    # Primary key and identification
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )

    # Source information
    source_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    source_type: Mapped[SourceType] = mapped_column(Enum(SourceType), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Content storage
    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    markdown_content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    # Vector database integration
    chroma_collection: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    chroma_document_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Processing metadata
    word_count: Mapped[Optional[int]] = mapped_column(nullable=True)
    estimated_reading_time: Mapped[Optional[int]] = mapped_column(nullable=True)  # minutes
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus),
        default=ProcessingStatus.PENDING
    )

    # Metadata and configuration
    content_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    processing_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Relationships
    prompts: Mapped[List["Prompt"]] = relationship(
        "Prompt",
        back_populates="content",
        cascade="all, delete-orphan"
    )
    agent_executions: Mapped[List["AgentExecution"]] = relationship(
        "AgentExecution",
        back_populates="content",
        cascade="all, delete-orphan"
    )

    # Indexes for performance
    __table_args__ = (
        Index("ix_content_source_type", "source_type"),
        Index("ix_content_status", "processing_status"),
        Index("ix_content_created_at", "created_at"),
        Index("ix_content_hash", "content_hash"),
        Index("ix_content_chroma", "chroma_collection", "chroma_document_id"),
    )


class Prompt(Base):
    """
    Generated flashcard prompts with quality metrics and versioning.
    Tracks relationship to source content and Mochi integration.
    """
    __tablename__ = "prompts"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )

    # Content relationship
    content_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contents.id", ondelete="CASCADE"),
        nullable=False
    )

    # Prompt content
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_type: Mapped[PromptType] = mapped_column(Enum(PromptType), nullable=False)

    # Quality and confidence
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    difficulty_level: Mapped[Optional[int]] = mapped_column(nullable=True)  # 1-5 scale

    # Versioning and editing
    version: Mapped[int] = mapped_column(default=1, nullable=False)
    is_edited: Mapped[bool] = mapped_column(Boolean, default=False)
    edit_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Mochi integration
    mochi_card_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mochi_deck_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mochi_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Context and metadata
    source_context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    prompt_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )
    edited_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    sent_to_mochi_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Relationships
    content: Mapped["Content"] = relationship("Content", back_populates="prompts")
    quality_metrics: Mapped[List["QualityMetric"]] = relationship(
        "QualityMetric",
        back_populates="prompt",
        cascade="all, delete-orphan"
    )
    user_interactions: Mapped[List["UserInteraction"]] = relationship(
        "UserInteraction",
        back_populates="prompt",
        cascade="all, delete-orphan"
    )

    # Indexes for performance
    __table_args__ = (
        Index("ix_prompt_content_id", "content_id"),
        Index("ix_prompt_type", "prompt_type"),
        Index("ix_prompt_confidence", "confidence_score"),
        Index("ix_prompt_mochi_card", "mochi_card_id"),
        Index("ix_prompt_created_at", "created_at"),
        Index("ix_prompt_content_type", "content_id", "prompt_type"),
    )


class QualityMetric(Base):
    """
    Quality assessment metrics for prompts based on Andy Matuschak's principles.
    Tracks multiple quality dimensions and feedback from LLM judges.
    """
    __tablename__ = "quality_metrics"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    # Prompt relationship
    prompt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prompts.id", ondelete="CASCADE"),
        nullable=False
    )

    # Metric details
    metric_type: Mapped[QualityMetricType] = mapped_column(
        Enum(QualityMetricType),
        nullable=False
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)  # 0.0 - 1.0
    weight: Mapped[float] = mapped_column(Float, default=1.0)

    # Evaluation details
    evaluator_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    evaluation_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Feedback and metadata
    feedback: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    metric_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    # Relationship
    prompt: Mapped["Prompt"] = relationship("Prompt", back_populates="quality_metrics")

    # Indexes
    __table_args__ = (
        Index("ix_quality_metric_prompt", "prompt_id"),
        Index("ix_quality_metric_type", "metric_type"),
        Index("ix_quality_metric_score", "score"),
        Index("ix_quality_metric_prompt_type", "prompt_id", "metric_type"),
    )


class AgentExecution(Base):
    """
    Tracks AI agent processing steps and performance for debugging and optimization.
    Records the complete execution chain for content processing.
    """
    __tablename__ = "agent_executions"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    # Content relationship
    content_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contents.id", ondelete="CASCADE"),
        nullable=True
    )

    # Execution details
    agent_type: Mapped[AgentType] = mapped_column(Enum(AgentType), nullable=False)
    execution_id: Mapped[str] = mapped_column(String(255), nullable=False)  # For grouping
    step_number: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)

    # Model and performance
    model_used: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    input_tokens: Mapped[Optional[int]] = mapped_column(nullable=True)
    output_tokens: Mapped[Optional[int]] = mapped_column(nullable=True)
    execution_time_ms: Mapped[Optional[int]] = mapped_column(nullable=True)
    cost_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Input/output data
    input_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    output_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Metadata
    execution_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Timestamps
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Relationship
    content: Mapped[Optional["Content"]] = relationship(
        "Content",
        back_populates="agent_executions"
    )

    # Indexes
    __table_args__ = (
        Index("ix_agent_execution_content", "content_id"),
        Index("ix_agent_execution_type", "agent_type"),
        Index("ix_agent_execution_id", "execution_id"),
        Index("ix_agent_execution_status", "status"),
        Index("ix_agent_execution_started", "started_at"),
    )


class UserInteraction(Base):
    """
    Tracks user feedback and interactions for continuous learning and improvement.
    Records editing patterns and preferences for system optimization.
    """
    __tablename__ = "user_interactions"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    # Prompt relationship
    prompt_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prompts.id", ondelete="CASCADE"),
        nullable=True
    )

    # Interaction details
    interaction_type: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)

    # Change tracking
    before_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    after_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    change_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # User feedback
    satisfaction_score: Mapped[Optional[int]] = mapped_column(nullable=True)  # 1-5
    feedback_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Session tracking
    session_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Metadata
    execution_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    # Relationship
    prompt: Mapped[Optional["Prompt"]] = relationship(
        "Prompt",
        back_populates="user_interactions"
    )

    # Indexes
    __table_args__ = (
        Index("ix_user_interaction_prompt", "prompt_id"),
        Index("ix_user_interaction_type", "interaction_type"),
        Index("ix_user_interaction_created", "created_at"),
        Index("ix_user_interaction_session", "session_id"),
    )


class ProcessingQueue(Base):
    """
    Queue for background processing tasks with priority and retry logic.
    Supports batch processing and handles failures gracefully.
    """
    __tablename__ = "processing_queue"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    # Task details
    task_type: Mapped[str] = mapped_column(String(100), nullable=False)
    priority: Mapped[int] = mapped_column(default=5, nullable=False)  # 1-10, lower is higher priority
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)

    # Input data
    input_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Processing results
    result_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Retry logic
    retry_count: Mapped[int] = mapped_column(default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(default=3, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Indexes
    __table_args__ = (
        Index("ix_queue_status_priority", "status", "priority"),
        Index("ix_queue_task_type", "task_type"),
        Index("ix_queue_scheduled", "scheduled_at"),
        Index("ix_queue_created", "created_at"),
    )