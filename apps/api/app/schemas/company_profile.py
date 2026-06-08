"""CompanyProfile schemas."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Structured analysis sub-models ──


class SixViewDimension(BaseModel):
    """Single dimension of the Enterprise Six Views (企业六看)."""

    content: Dict[str, Any] = Field(default_factory=dict)


class SixViews(BaseModel):
    """Enterprise Six Views structured analysis."""

    backward_history: Optional[Dict[str, str]] = Field(
        None, description="向后看：发展历史（创始、起源、核心理念）"
    )
    forward_planning: Optional[Dict[str, str]] = Field(
        None, description="向前看：发展规划（战略、产品路线、市场拓展）"
    )
    left_competitors: Optional[Dict[str, Any]] = Field(
        None, description="向左看：竞争对手（对标企业、差异化）"
    )
    right_industry: Optional[Dict[str, str]] = Field(
        None, description="向右看：行业情况（趋势、市场格局）"
    )
    upward_policy: Optional[Dict[str, str]] = Field(
        None, description="向上看：政策背景（国家政策、地方政策）"
    )
    downward_niche: Optional[Dict[str, str]] = Field(
        None, description="向下看：生态位（核心优势、不可替代性）"
    )


class TechnologyLayer(BaseModel):
    """A single layer in the technology architecture."""

    name: str
    level: str = Field(description="top / middle / bottom")
    description: str = ""
    metaphor: str = Field("", description="拟人化比喻，如「神经网络」「指挥大脑」")


class TechnologyArchitecture(BaseModel):
    """Technology One-Page (技术一张图) layered architecture."""

    layers: List[TechnologyLayer] = Field(default_factory=list)
    core_technology_summary: str = ""
    visual_metaphor: str = ""


class BackgroundLevel(BaseModel):
    """A single level in the project background hierarchy."""

    title: str = ""
    content: str = ""


class ProjectBackground(BaseModel):
    """Three-level project background (项目背景)."""

    national_policy: Optional[BackgroundLevel] = Field(None, description="宏观：国家政策")
    city_or_industry: Optional[BackgroundLevel] = Field(None, description="中观：城市/行业实践")
    project_positioning: Optional[BackgroundLevel] = Field(None, description="微观：项目定位")


# ── CRUD schemas ──


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
    six_views: Optional[SixViews] = None
    technology_arch: Optional[TechnologyArchitecture] = None
    project_background: Optional[ProjectBackground] = None


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
