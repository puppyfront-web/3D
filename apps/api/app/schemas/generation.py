"""Generation task and output schemas."""

import uuid
from datetime import datetime
from typing import List, Optional

from app.schemas.common import APIBaseModel
from pydantic import Field


class GenerationTaskCreate(APIBaseModel):
    project_id: uuid.UUID
    type: str = Field(..., max_length=100)
    prompt_used: Optional[str] = None


class GenerationTaskUpdate(APIBaseModel):
    status: Optional[str] = Field(None, max_length=50)
    error_message: Optional[str] = None


class GenerationOutputCreate(APIBaseModel):
    task_id: uuid.UUID
    content_type: str = Field(default="text/plain", max_length=100)
    content: str
    used_cases: Optional[List[str]] = Field(default_factory=list)
    used_documents: Optional[List[str]] = Field(default_factory=list)
    used_chunks: Optional[List[str]] = Field(default_factory=list)
    used_sop_version: Optional[str] = Field(None, max_length=50)


class GenerationOutputOut(APIBaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    content_type: str
    content: str
    used_cases: Optional[List[str]] = None
    used_documents: Optional[List[str]] = None
    used_chunks: Optional[List[str]] = None
    used_sop_version: Optional[str] = None
    sections_meta: Optional[List[dict]] = None
    version: int = 1
    parent_output_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime


class GenerationTaskOut(APIBaseModel):
    model_config = {
        "protected_namespaces": (),  # Allow "model_used" field without warning
    }
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


class ProposalGenerationRequest(APIBaseModel):
    """Request to generate a proposal via the agent pipeline."""

    project_id: uuid.UUID
    sop_workflow_id: Optional[uuid.UUID] = None
    prompt_template_id: Optional[uuid.UUID] = None
    proposal_template_id: Optional[uuid.UUID] = None
    visual_style_id: Optional[uuid.UUID] = None
    additional_instructions: Optional[str] = None


class VisualPromptRequest(APIBaseModel):
    """Request to generate a visual design prompt."""

    project_id: uuid.UUID
    style_preferences: Optional[str] = None
    target_audience: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None


class DirectImageRequest(APIBaseModel):
    """Request to directly generate an image from a prompt (no project required)."""

    prompt: str = Field(..., min_length=1, max_length=4000)
    negative_prompt: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None


class ProposalContentUpdate(APIBaseModel):
    """Update proposal content (human edit) or sections metadata."""

    content: Optional[str] = None
    sections_meta: Optional[List[dict]] = None


class ProposalSectionStatusUpdate(APIBaseModel):
    """Update a single section's review status."""

    status: str = Field(..., pattern=r"^(draft|review|approved)$")
    reviewed_by: Optional[str] = None


# ── Quality Review Checklist ──


class ChecklistItem(APIBaseModel):
    """A single item in a quality review checklist."""

    id: str
    description: str
    status: str  # pass / warning / fail / pending
    comment: Optional[str] = None


class ChecklistGroup(APIBaseModel):
    """A group of related checklist items."""

    id: str
    category: str
    items: List[ChecklistItem]
