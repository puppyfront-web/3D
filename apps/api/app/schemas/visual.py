"""Visual style schemas."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class VisualStyleBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    primary_color: str = Field(default="#1a73e8", max_length=20)
    secondary_color: Optional[str] = Field(None, max_length=20)
    accent_color: Optional[str] = Field(None, max_length=20)
    background_color: Optional[str] = Field(None, max_length=20)
    font_primary: Optional[str] = Field(None, max_length=100)
    font_secondary: Optional[str] = Field(None, max_length=100)
    layout: Optional[str] = Field(None, max_length=50)
    brand_guidelines: Optional[str] = None


class VisualStyleCreate(VisualStyleBase):
    pass


class VisualStyleUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    primary_color: Optional[str] = Field(None, max_length=20)
    secondary_color: Optional[str] = Field(None, max_length=20)
    accent_color: Optional[str] = Field(None, max_length=20)
    background_color: Optional[str] = Field(None, max_length=20)
    font_primary: Optional[str] = Field(None, max_length=100)
    font_secondary: Optional[str] = Field(None, max_length=100)
    layout: Optional[str] = Field(None, max_length=50)
    brand_guidelines: Optional[str] = None


class VisualStyleOut(VisualStyleBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
