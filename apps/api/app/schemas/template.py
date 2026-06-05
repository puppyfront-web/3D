"""Template schemas (PromptTemplate + ProposalTemplate)."""

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# --- Prompt Template ---

class PromptTemplateBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    category: str = Field(..., max_length=100)
    template_text: str
    variables: Optional[List[str]] = Field(default_factory=list)
    is_default: bool = False


class PromptTemplateCreate(PromptTemplateBase):
    pass


class PromptTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    category: Optional[str] = Field(None, max_length=100)
    template_text: Optional[str] = None
    variables: Optional[List[str]] = None
    is_default: Optional[bool] = None


class PromptTemplateOut(PromptTemplateBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- Proposal Template ---

class ProposalTemplateBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    category: str = Field(..., max_length=100)
    sections: Optional[dict] = Field(default_factory=dict)
    is_default: bool = False


class ProposalTemplateCreate(ProposalTemplateBase):
    pass


class ProposalTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    category: Optional[str] = Field(None, max_length=100)
    sections: Optional[dict] = None
    is_default: Optional[bool] = None


class ProposalTemplateOut(ProposalTemplateBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
