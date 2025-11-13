# Common Schemas
"""
Common Pydantic schemas used across the application.
Includes base classes, enums, and shared response models.
"""

from datetime import datetime
from typing import Dict, Any, Optional, List, Generic, TypeVar
from pydantic import BaseModel, Field
import uuid

DataT = TypeVar('DataT')


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    class Config:
        from_attributes = True
        validate_assignment = True
        use_enum_values = True


class TimestampMixin(BaseModel):
    """Mixin for timestamp fields."""

    created_at: datetime
    updated_at: datetime


class UUIDMixin(BaseModel):
    """Mixin for UUID primary key."""

    id: uuid.UUID


class PaginationParams(BaseModel):
    """Pagination parameters schema."""

    skip: int = Field(0, ge=0, description="Number of items to skip")
    limit: int = Field(50, ge=1, le=1000, description="Number of items to return")


class PaginationResponse(BaseModel, Generic[DataT]):
    """Generic pagination response schema."""

    items: List[DataT]
    total: int
    skip: int
    limit: int
    has_next: bool

    @classmethod
    def create(
        cls,
        items: List[DataT],
        total: int,
        skip: int,
        limit: int
    ) -> "PaginationResponse[DataT]":
        """Create pagination response."""
        return cls(
            items=items,
            total=total,
            skip=skip,
            limit=limit,
            has_next=skip + limit < total
        )


class APIResponse(BaseModel, Generic[DataT]):
    """Standard API response wrapper."""

    success: bool
    message: str
    data: Optional[DataT] = None
    meta: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @classmethod
    def success_response(
        cls,
        data: Optional[DataT] = None,
        message: str = "Success",
        meta: Optional[Dict[str, Any]] = None
    ) -> "APIResponse[DataT]":
        """Create success response."""
        return cls(
            success=True,
            message=message,
            data=data,
            meta=meta
        )

    @classmethod
    def error_response(
        cls,
        message: str,
        meta: Optional[Dict[str, Any]] = None
    ) -> "APIResponse[None]":
        """Create error response."""
        return cls(
            success=False,
            message=message,
            data=None,
            meta=meta
        )


class HealthCheck(BaseModel):
    """Health check response schema."""

    status: str
    timestamp: datetime
    version: str
    environment: str
    services: Optional[Dict[str, str]] = None


class ErrorDetail(BaseModel):
    """Error detail schema."""

    type: str
    message: str
    field: Optional[str] = None
    code: Optional[str] = None


class ValidationError(BaseModel):
    """Validation error response schema."""

    detail: str
    errors: List[ErrorDetail]
    status_code: int
    timestamp: datetime
    path: str