"""Visual style schemas."""

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ── Design specification sub-models ──


class MaterialCategory(BaseModel):
    """A material category within a design specification."""

    name: str = Field(description="材质类别标识，如 wood_elements")
    description: str = Field(description="材质描述")
    coverage: str = Field(default="", description="占比，如 30%")


class MaterialSpec(BaseModel):
    """Material specification parameters (材质规范)."""

    style: str = Field(default="", description="风格名称，如 北欧风")
    categories: List[MaterialCategory] = Field(default_factory=list)


class ColorTemperature(BaseModel):
    """Color temperature specification."""

    range: str = Field(default="", description="色温范围，如 2700K-3000K")
    description: str = Field(default="", description="色温描述，如 暖白到柔白")


class LightingLayer(BaseModel):
    """A lighting layer specification."""

    type: str = Field(description="ambient / task / accent")
    description: str = ""


class LightingSpec(BaseModel):
    """Lighting specification parameters (灯光规范)."""

    overall_atmosphere: str = Field(default="", description="整体氛围")
    color_temperature: Optional[ColorTemperature] = None
    lighting_layers: List[LightingLayer] = Field(default_factory=list)
    fixture_style: str = Field(default="", description="灯具风格")


# ── CRUD schemas ──


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
    material_spec: Optional[MaterialSpec] = None
    lighting_spec: Optional[LightingSpec] = None


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
    material_spec: Optional[MaterialSpec] = None
    lighting_spec: Optional[LightingSpec] = None


class VisualStyleOut(VisualStyleBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
