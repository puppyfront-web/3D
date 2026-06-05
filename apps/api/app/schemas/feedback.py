"""Feedback schemas."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class FeedbackCreate(BaseModel):
    project_id: uuid.UUID
    generation_task_id: Optional[uuid.UUID] = None
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None
    category: Optional[str] = Field(None, max_length=100)


class FeedbackUpdate(BaseModel):
    rating: Optional[int] = Field(None, ge=1, le=5)
    comment: Optional[str] = None
    category: Optional[str] = Field(None, max_length=100)


class FeedbackOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID
    generation_task_id: Optional[uuid.UUID] = None
    rating: int
    comment: Optional[str] = None
    category: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
