"""Shared schemas used across the application."""

from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

T = TypeVar("T")


def _to_camel(name: str) -> str:
    """Convert snake_case to camelCase for API serialization."""
    return to_camel(name)


class APIBaseModel(BaseModel):
    """Base model for all API schemas.

    - Python code uses snake_case (standard convention)
    - API output serializes to camelCase (JavaScript convention)
    - API input accepts both camelCase and snake_case
    """

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=_to_camel,
        populate_by_name=True,  # Accept both snake_case and camelCase on input
    )


class PaginationParams(APIBaseModel):
    """Pagination query parameters."""

    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")


class PaginatedResponse(APIBaseModel, Generic[T]):
    """Paginated list response wrapper."""

    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int


class Response(APIBaseModel, Generic[T]):
    """Standard API response wrapper."""

    success: bool = True
    message: str = "OK"
    data: Optional[T] = None


class ErrorResponse(APIBaseModel):
    """Error response schema."""

    success: bool = False
    message: str
    detail: Optional[Any] = None


class BulkDeleteRequest(APIBaseModel):
    """Request body for bulk deletion."""

    ids: List[str] = Field(..., min_length=1, description="List of UUIDs to delete")


class IDResponse(APIBaseModel):
    """Minimal response returning only an ID."""

    id: str


class ImportResponse(APIBaseModel):
    """Response for entity import operations."""

    imported: int
    failed: int
    skipped: int = 0
    updated: int = 0
    errors: List[str] = Field(default_factory=list)
    message: str = ""
