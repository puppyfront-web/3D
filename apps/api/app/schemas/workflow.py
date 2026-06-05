"""SOP Workflow schemas."""

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class SOPStep(BaseModel):
    """A single step in an SOP workflow."""

    order: int
    name: str
    description: str
    agent: str
    inputs: List[str] = Field(default_factory=list)


class SOPWorkflowBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    version: str = Field(default="1.0", max_length=50)
    steps: Optional[List[SOPStep]] = Field(default_factory=list)
    is_active: bool = True


class SOPWorkflowCreate(SOPWorkflowBase):
    pass


class SOPWorkflowUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    version: Optional[str] = Field(None, max_length=50)
    steps: Optional[List[SOPStep]] = None
    is_active: Optional[bool] = None


class SOPWorkflowOut(SOPWorkflowBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
