"""Project schemas."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.company import CompanyOut
from app.schemas.user import UserOut


class ProjectBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    priority: Optional[str] = Field(None, max_length=50)


class ProjectCreate(ProjectBase):
    company_id: uuid.UUID
    owner_id: uuid.UUID
    status: str = Field(default="draft", max_length=50)


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    company_id: Optional[uuid.UUID] = None
    owner_id: Optional[uuid.UUID] = None
    status: Optional[str] = Field(None, max_length=50)
    priority: Optional[str] = Field(None, max_length=50)


class ProjectOut(ProjectBase):
    id: uuid.UUID
    company_id: uuid.UUID
    owner_id: uuid.UUID
    status: str
    created_at: datetime
    updated_at: datetime
    company: Optional[CompanyOut] = None
    owner: Optional[UserOut] = None

    class Config:
        from_attributes = True


class ProjectStatusUpdate(BaseModel):
    status: str = Field(..., max_length=50, description="New status value")
