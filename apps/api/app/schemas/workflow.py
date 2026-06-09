"""SOP Workflow schemas."""

import uuid
from datetime import datetime
from typing import List, Optional

from app.schemas.common import APIBaseModel
from pydantic import Field


# ── Enhanced step sub-models ──


class SOPStepRule(APIBaseModel):
    """A rule within an SOP step."""

    type: str = Field(default="general", description="general 或 custom")
    description: str


class SOPStepPrompt(APIBaseModel):
    """A numbered analysis question within an SOP step."""

    number: int
    question: str
    purpose: str = ""


class SOPStep(APIBaseModel):
    """A single step in an SOP workflow."""

    order: int
    name: str
    description: str
    agent: str
    inputs: List[str] = Field(default_factory=list)
    outputs: List[str] = Field(default_factory=list)
    stage: str = Field(default="analysis", description="所属阶段：analysis/planning/design/reference")
    rules: List[SOPStepRule] = Field(default_factory=list)
    prompts: List[SOPStepPrompt] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list, description="依赖的步骤名称")


class PipelineStage(APIBaseModel):
    """A pipeline stage definition."""

    stage: str = Field(description="阶段标识，如 enterprise_understanding")
    name: str = Field(description="阶段显示名，如 企业理解")
    description: str = Field(default="", description="阶段描述")


# ── CRUD schemas ──


class SOPWorkflowBase(APIBaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    version: str = Field(default="1.0", max_length=50)
    steps: Optional[List[SOPStep]] = Field(default_factory=list)
    pipeline_stages: Optional[List[PipelineStage]] = Field(
        default_factory=list, description="Pipeline 阶段定义"
    )
    is_active: bool = True


class SOPWorkflowCreate(SOPWorkflowBase):
    pass


class SOPWorkflowUpdate(APIBaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    version: Optional[str] = Field(None, max_length=50)
    steps: Optional[List[SOPStep]] = None
    pipeline_stages: Optional[List[PipelineStage]] = None
    is_active: Optional[bool] = None


class SOPWorkflowOut(SOPWorkflowBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
