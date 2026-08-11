"""Eval API schemas."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field

from app.schemas.common import APIBaseModel


class EvalSetCreate(APIBaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    project_id: Optional[uuid.UUID] = None


class EvalSetOut(APIBaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    project_id: Optional[uuid.UUID] = None
    status: str
    created_at: datetime
    updated_at: datetime


class EvalCaseCreate(APIBaseModel):
    query: str
    expected_chunk_ids: List[str] = Field(default_factory=list)
    expected_document_ids: List[str] = Field(default_factory=list)
    expected_keywords: List[str] = Field(default_factory=list)
    must_not_keywords: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    source: str = "manual"


class EvalCaseFromLab(APIBaseModel):
    set_id: uuid.UUID
    query: str
    pick_rank: int = 0
    top_k_snapshot: List[Dict[str, Any]] = Field(default_factory=list)


class EvalCaseOut(APIBaseModel):
    id: uuid.UUID
    set_id: uuid.UUID
    query: str
    expected_chunk_ids: Optional[List[str]] = None
    expected_document_ids: Optional[List[str]] = None
    expected_keywords: Optional[List[str]] = None
    must_not_keywords: Optional[List[str]] = None
    notes: Optional[str] = None
    source: str
    created_at: datetime
    updated_at: datetime


class EvalImportTemplate(APIBaseModel):
    template_id: str = "b2b-smoke-v1"
    name: Optional[str] = None
    project_id: Optional[uuid.UUID] = None


class EvalRunCreate(APIBaseModel):
    set_id: uuid.UUID
    config_overrides: Optional[Dict[str, Any]] = None


class EvalRunOut(APIBaseModel):
    id: uuid.UUID
    set_id: uuid.UUID
    status: str
    config_snapshot_json: Optional[Dict[str, Any]] = None
    metrics_json: Optional[Dict[str, Any]] = None
    per_case_results_json: Optional[List[Dict[str, Any]]] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
