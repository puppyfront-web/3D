"""Company schemas."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CompanyBase(BaseModel):
    name: str = Field(..., max_length=255)
    industry: Optional[str] = Field(None, max_length=100)
    website: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    logo_url: Optional[str] = Field(None, max_length=500)


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    industry: Optional[str] = Field(None, max_length=100)
    website: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    logo_url: Optional[str] = Field(None, max_length=500)


class CompanyOut(CompanyBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
