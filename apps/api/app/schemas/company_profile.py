"""CompanyProfile schemas."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CompanyProfileBase(BaseModel):
    strengths: Optional[str] = None
    weaknesses: Optional[str] = None
    market_position: Optional[str] = None
    key_products: Optional[str] = None
    competitors: Optional[str] = None
    recent_news: Optional[str] = None
    culture: Optional[str] = None
    financials: Optional[str] = None
    raw_analysis: Optional[str] = None


class CompanyProfileCreate(CompanyProfileBase):
    company_id: uuid.UUID


class CompanyProfileUpdate(CompanyProfileBase):
    pass


class CompanyProfileOut(CompanyProfileBase):
    id: uuid.UUID
    company_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CompanyAnalysisRequest(BaseModel):
    """Request to trigger AI-powered company analysis."""

    company_id: uuid.UUID
    force_regenerate: bool = False
    context: Optional[str] = None
