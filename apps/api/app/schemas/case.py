"""Case schemas."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CaseBase(BaseModel):
    title: str = Field(..., max_length=500)
    client_name: str = Field(..., max_length=255)
    industry: Optional[str] = Field(None, max_length=100)
    challenge: Optional[str] = None
    solution: Optional[str] = None
    results: Optional[str] = None
    technologies: Optional[str] = None
    duration: Optional[str] = Field(None, max_length=100)
    team_size: Optional[int] = None
    budget_range: Optional[str] = Field(None, max_length=100)
    tags: Optional[str] = None


class CaseCreate(CaseBase):
    project_id: uuid.UUID
    is_published: bool = False


class CaseUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    client_name: Optional[str] = Field(None, max_length=255)
    industry: Optional[str] = Field(None, max_length=100)
    challenge: Optional[str] = None
    solution: Optional[str] = None
    results: Optional[str] = None
    technologies: Optional[str] = None
    duration: Optional[str] = Field(None, max_length=100)
    team_size: Optional[int] = None
    budget_range: Optional[str] = Field(None, max_length=100)
    quality_score: Optional[float] = None
    is_published: Optional[bool] = None
    tags: Optional[str] = None


class CaseOut(CaseBase):
    id: uuid.UUID
    project_id: uuid.UUID
    quality_score: Optional[float] = None
    is_published: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CaseQualityScore(BaseModel):
    """Quality score for a case study."""

    case_id: uuid.UUID
    score: float = Field(..., ge=0, le=100)
    details: Optional[dict] = None
