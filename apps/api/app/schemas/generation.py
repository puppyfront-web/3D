"""Generation task and output schemas."""

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class GenerationTaskCreate(BaseModel):
    project_id: uuid.UUID
    type: str = Field(..., max_length=100)
    prompt_used: Optional[str] = None


class GenerationTaskUpdate(BaseModel):
    status: Optional[str] = Field(None, max_length=50)
    error_message: Optional[str] = None


class GenerationOutputCreate(BaseModel):
    task_id: uuid.UUID
    content_type: str = Field(default="text/plain", max_length=100)
    content: str
    used_cases: Optional[List[str]] = Field(default_factory=list)
    used_documents: Optional[List[str]] = Field(default_factory=list)
    used_chunks: Optional[List[str]] = Field(default_factory=list)
    used_sop_version: Optional[str] = Field(None, max_length=50)


class GenerationOutputOut(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    content_type: str
    content: str
    used_cases: Optional[List[str]] = None
    used_documents: Optional[List[str]] = None
    used_chunks: Optional[List[str]] = None
    used_sop_version: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class GenerationTaskOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    type: str
    status: str
    prompt_used: Optional[str] = None
    model_used: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    outputs: Optional[List[GenerationOutputOut]] = None

    class Config:
        from_attributes = True


class ProposalGenerationRequest(BaseModel):
    """Request to generate a proposal via the agent pipeline."""

    project_id: uuid.UUID
    sop_workflow_id: Optional[uuid.UUID] = None
    prompt_template_id: Optional[uuid.UUID] = None
    proposal_template_id: Optional[uuid.UUID] = None
    visual_style_id: Optional[uuid.UUID] = None
    additional_instructions: Optional[str] = None


class VisualPromptRequest(BaseModel):
    """Request to generate a visual design prompt."""

    project_id: uuid.UUID
    style_preferences: Optional[str] = None
    target_audience: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None


class DirectImageRequest(BaseModel):
    """Request to directly generate an image from a prompt (no project required)."""

    prompt: str = Field(..., min_length=1, max_length=4000)
    negative_prompt: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
