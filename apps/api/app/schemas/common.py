"""Shared schemas used across the application."""

from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Pagination query parameters."""

    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated list response wrapper."""

    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int

    class Config:
        from_attributes = True


class Response(BaseModel, Generic[T]):
    """Standard API response wrapper."""

    success: bool = True
    message: str = "OK"
    data: Optional[T] = None

    class Config:
        from_attributes = True


class ErrorResponse(BaseModel):
    """Error response schema."""

    success: bool = False
    message: str
    detail: Optional[Any] = None


class BulkDeleteRequest(BaseModel):
    """Request body for bulk deletion."""

    ids: List[str] = Field(..., min_length=1, description="List of UUIDs to delete")


class IDResponse(BaseModel):
    """Minimal response returning only an ID."""

    id: str
