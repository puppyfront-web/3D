"""Pydantic schemas for the Skills API."""

from typing import Any, Dict, List, Optional

from app.schemas.common import APIBaseModel


class SkillManifestOut(APIBaseModel):
    """Skill manifest returned in API responses."""
    skill_id: str
    name: str
    description: Optional[str] = None
    category: str
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    required_services: Optional[List[str]] = None
    permissions: Optional[List[str]] = None
    visibility: str = "internal"
    version: str = "1.0.0"


class SkillOut(APIBaseModel):
    """Full skill record from database."""
    id: str
    skill_id: str
    name: str
    description: Optional[str] = None
    category: str
    manifest_json: Optional[Dict[str, Any]] = None
    input_schema_json: Optional[Dict[str, Any]] = None
    output_schema_json: Optional[Dict[str, Any]] = None
    visibility: str
    version: str
    status: str


class SkillExecuteRequest(APIBaseModel):
    """Request body for executing a skill."""
    input_data: Dict[str, Any]
    project_id: Optional[str] = None
    user_id: Optional[str] = None


class SkillExecutionOut(APIBaseModel):
    """Skill execution record."""
    id: str
    skill_id: str
    project_id: Optional[str] = None
    user_id: Optional[str] = None
    input_json: Optional[Dict[str, Any]] = None
    output_json: Optional[Dict[str, Any]] = None
    status: str
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None
    used_cases: Optional[List[str]] = None
    used_documents: Optional[List[str]] = None
    used_chunks: Optional[List[str]] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None
