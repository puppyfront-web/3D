"""Schemas for the three new internal knowledge bases (PRD §12):

- IndustryMaterial (行业资料库)
- TalkingPoint (话术库)
- PricingExperience (报价经验库)
"""

import uuid
from datetime import datetime
from typing import Optional

from app.schemas.common import APIBaseModel
from pydantic import Field


# ── Industry materials ─────────────────────────────────────────────


class IndustryMaterialBase(APIBaseModel):
    title: str = Field(..., max_length=500)
    industry: Optional[str] = Field(None, max_length=100)
    category: Optional[str] = Field(None, max_length=100)
    content: Optional[str] = None
    source_url: Optional[str] = Field(None, max_length=1000)
    is_active: bool = True


class IndustryMaterialCreate(IndustryMaterialBase):
    pass


class IndustryMaterialUpdate(APIBaseModel):
    title: Optional[str] = Field(None, max_length=500)
    industry: Optional[str] = Field(None, max_length=100)
    category: Optional[str] = Field(None, max_length=100)
    content: Optional[str] = None
    source_url: Optional[str] = Field(None, max_length=1000)
    is_active: Optional[bool] = None


class IndustryMaterialOut(IndustryMaterialBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# ── Talking points ─────────────────────────────────────────────────


class TalkingPointBase(APIBaseModel):
    scenario: str = Field(..., max_length=255)
    title: str = Field(..., max_length=500)
    content: Optional[str] = None
    industry: Optional[str] = Field(None, max_length=100)
    tags: Optional[str] = None
    is_active: bool = True


class TalkingPointCreate(TalkingPointBase):
    pass


class TalkingPointUpdate(APIBaseModel):
    scenario: Optional[str] = Field(None, max_length=255)
    title: Optional[str] = Field(None, max_length=500)
    content: Optional[str] = None
    industry: Optional[str] = Field(None, max_length=100)
    tags: Optional[str] = None
    is_active: Optional[bool] = None


class TalkingPointOut(TalkingPointBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# ── Pricing experiences ────────────────────────────────────────────


class PricingExperienceBase(APIBaseModel):
    title: str = Field(..., max_length=500)
    industry: Optional[str] = Field(None, max_length=100)
    project_type: Optional[str] = Field(None, max_length=100)
    budget_range: Optional[str] = Field(None, max_length=100)
    duration: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None
    is_active: bool = True


class PricingExperienceCreate(PricingExperienceBase):
    pass


class PricingExperienceUpdate(APIBaseModel):
    title: Optional[str] = Field(None, max_length=500)
    industry: Optional[str] = Field(None, max_length=100)
    project_type: Optional[str] = Field(None, max_length=100)
    budget_range: Optional[str] = Field(None, max_length=100)
    duration: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class PricingExperienceOut(PricingExperienceBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
