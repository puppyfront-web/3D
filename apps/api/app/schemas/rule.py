"""Rule schemas (TechnicalRule + QualityRule)."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# --- Technical Rule ---

class TechnicalRuleBase(BaseModel):
    name: str = Field(..., max_length=255)
    category: str = Field(..., max_length=100)
    description: Optional[str] = None
    rule_text: str
    severity: str = Field(default="warning", max_length=50)
    is_active: bool = True


class TechnicalRuleCreate(TechnicalRuleBase):
    pass


class TechnicalRuleUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    category: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    rule_text: Optional[str] = None
    severity: Optional[str] = Field(None, max_length=50)
    is_active: Optional[bool] = None


class TechnicalRuleOut(TechnicalRuleBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- Quality Rule ---

class QualityRuleBase(BaseModel):
    name: str = Field(..., max_length=255)
    category: str = Field(..., max_length=100)
    description: Optional[str] = None
    rule_text: str
    weight: float = Field(default=1.0, ge=0, le=1.0)
    is_active: bool = True


class QualityRuleCreate(QualityRuleBase):
    pass


class QualityRuleUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    category: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    rule_text: Optional[str] = None
    weight: Optional[float] = Field(None, ge=0, le=1.0)
    is_active: Optional[bool] = None


class QualityRuleOut(QualityRuleBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
