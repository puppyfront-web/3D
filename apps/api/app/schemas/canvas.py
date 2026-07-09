"""Canvas and version schemas for the infinite-canvas workspace.

Mirrors the models in app.models.canvas. All schemas inherit APIBaseModel so
snake_case Python fields serialize to camelCase on output and accept both
casing conventions on input (see app.schemas.common.APIBaseModel).
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field

from app.schemas.common import APIBaseModel


# ─── Node sources (provenance) ───────────────────────────────────────────────


class NodeSourceOut(APIBaseModel):
    id: uuid.UUID
    source_type: str
    source_ref_id: Optional[str] = None
    source_name: Optional[str] = None
    confidence: Optional[str] = None
    quote: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None
    created_at: datetime


# ─── Canvas nodes ────────────────────────────────────────────────────────────


class CanvasNodeOut(APIBaseModel):
    id: uuid.UUID
    canvas_id: uuid.UUID
    group_id: Optional[uuid.UUID] = None
    node_key: Optional[str] = None
    title: str
    node_type: str
    status: str
    priority: Optional[str] = None
    position: Optional[Dict[str, Any]] = None
    content: Optional[Dict[str, Any]] = None
    sources: List[NodeSourceOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class CanvasNodeUpdate(APIBaseModel):
    """Partial update of a node — manual edit (triggers a new version)."""

    title: Optional[str] = Field(None, max_length=255)
    status: Optional[str] = Field(None, max_length=50)
    priority: Optional[str] = Field(None, max_length=50)
    position: Optional[Dict[str, Any]] = None
    content: Optional[Dict[str, Any]] = None


class CanvasNodeCreate(APIBaseModel):
    """Body for POST /projects/:id/nodes — add a custom node to a board.

    PRD P1 #2: users can add nodes beyond the default 21. ``group_id`` places
    it under one of the three boards; ``title`` is required; ``node_key``
    defaults to a synthetic key so the AI-fill orchestrator can still route
    to it. ``position`` is optional (auto-stacked when omitted).
    """

    title: str = Field(..., min_length=1, max_length=255)
    group_id: uuid.UUID
    node_key: Optional[str] = Field(None, max_length=80)
    node_type: Optional[str] = Field("module_node", max_length=50)
    position: Optional[Dict[str, Any]] = None


# ─── Canvas groups ───────────────────────────────────────────────────────────


class CanvasGroupOut(APIBaseModel):
    id: uuid.UUID
    canvas_id: uuid.UUID
    group_key: str
    title: str
    description: Optional[str] = None
    position: Optional[Dict[str, Any]] = None
    style: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime


# ─── Canvas edges ────────────────────────────────────────────────────────────


class CanvasEdgeOut(APIBaseModel):
    id: uuid.UUID
    canvas_id: uuid.UUID
    source_node_id: uuid.UUID
    target_node_id: uuid.UUID
    edge_type: Optional[str] = None
    label: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None
    created_at: datetime


# ─── Canvas aggregate ────────────────────────────────────────────────────────


class CanvasOut(APIBaseModel):
    """Full canvas payload: viewport + groups + nodes + edges."""

    id: uuid.UUID
    project_version_id: uuid.UUID
    viewport: Optional[Dict[str, Any]] = None
    layout_config: Optional[Dict[str, Any]] = None
    groups: List[CanvasGroupOut] = Field(default_factory=list)
    nodes: List[CanvasNodeOut] = Field(default_factory=list)
    edges: List[CanvasEdgeOut] = Field(default_factory=list)
    created_at: datetime
    # Read-only flag for historical versions
    is_read_only: bool = False


# ─── Project versions ────────────────────────────────────────────────────────


class ProjectVersionOut(APIBaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    version_no: int
    version_name: Optional[str] = None
    change_summary: Optional[str] = None
    based_on_version_id: Optional[uuid.UUID] = None
    is_current: bool
    created_by: Optional[uuid.UUID] = None
    created_at: datetime
    # Related knowledge assets used by this version (PRD §16.3 / §23.6).
    # Populated from the version snapshot's related_materials /
    # related_internal_assets aggregates; empty for versions snapshotted before
    # this field was introduced.
    related_materials: Optional[List[str]] = None
    related_internal_assets: Optional[dict] = None
    # Per-node diff vs the prior version (PRD §16.3 变更节点). Each item:
    # {node_key, title, change: added|removed|content|status|title}. Empty for
    # the first version or snapshots predating this field.
    changed_nodes: Optional[List[dict]] = None


class ProjectVersionCreate(APIBaseModel):
    """Body for POST /projects/:id/versions — promote the current canvas to a
    new snapshot version. Optional explicit change summary; otherwise the
    service derives one from changed node ids.
    """

    version_name: Optional[str] = Field(None, max_length=255)
    change_summary: Optional[str] = None


class VersionRestoreOut(APIBaseModel):
    """Response of POST /versions/:id/restore — returns the freshly created
    current version (a new draft branched from the historical snapshot)."""

    new_version: ProjectVersionOut
    message: str
