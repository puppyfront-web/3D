"""Canvas and version models for the infinite-canvas workspace.

This module implements the snapshot-based version model described in the
technical design (§5) and PRD §16:

    Project  1:N  ProjectVersion  1:1  Canvas  1:N  CanvasGroup
                                                  Canvas  1:N  CanvasNode  1:N  NodeSource
                                                  Canvas  1:N  CanvasEdge

Every confirmed change produces a new ProjectVersion whose ``snapshot``
captures the full canvas state (groups / nodes / edges / materials summary /
internal assets used / agent outputs / change logs). Historical versions are
read-only; restoring one creates a new draft based on its snapshot.

Note on style: existing models in this repo hand-write id/created_at/updated_at
columns rather than using the TimestampMixin/UUIDMixin defined in app.db.base.
We follow the same convention here for consistency.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ProjectVersion(Base):
    """Immutable snapshot of a project at a point in time.

    Each version owns a Canvas (groups/nodes/edges) and carries a full
    ``snapshot`` JSONB blob so historical versions can be viewed and restored
    independently of any diff replay.
    """

    __tablename__ = "project_versions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    version_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    change_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Self-reference: the version this one was branched/restored from.
    based_on_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("project_versions.id"), nullable=True
    )
    is_current: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )
    # Full snapshot: {canvas, groups, nodes, edges, materials_summary,
    # internal_assets_used, agent_outputs, change_logs}
    snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="versions")  # type: ignore[name-defined]
    canvas: Mapped[Optional["Canvas"]] = relationship(
        back_populates="version", uselist=False, lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<ProjectVersion v{self.version_no} of {self.project_id}>"


class Canvas(Base):
    """A single canvas attached to exactly one ProjectVersion (1:1)."""

    __tablename__ = "canvases"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project_versions.id"), nullable=False, unique=True, index=True
    )
    # {x, y, zoom} — last viewport so reopening a version feels continuous
    viewport: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Layout hints: auto-layout algo, grid snapping, theme, etc.
    layout_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    version: Mapped["ProjectVersion"] = relationship(back_populates="canvas")
    groups: Mapped[list["CanvasGroup"]] = relationship(
        back_populates="canvas", lazy="selectin", cascade="all, delete-orphan"
    )
    nodes: Mapped[list["CanvasNode"]] = relationship(
        back_populates="canvas", lazy="selectin", cascade="all, delete-orphan"
    )
    edges: Mapped[list["CanvasEdge"]] = relationship(
        back_populates="canvas", lazy="selectin", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Canvas for version {self.project_version_id}>"


class CanvasGroup(Base):
    """A top-level board section — the three default groups:
    company_intro / product_tech_scenarios / future_social_responsibility.
    """

    __tablename__ = "canvas_groups"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    canvas_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("canvases.id"), nullable=False, index=True
    )
    group_key: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    position: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    style: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    canvas: Mapped["Canvas"] = relationship(back_populates="groups")
    nodes: Mapped[list["CanvasNode"]] = relationship(
        back_populates="group", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<CanvasGroup {self.group_key}>"


class CanvasNode(Base):
    """A leaf node on the canvas. Carries AI-filled content and a status flag.

    ``content`` shape (JSON):
        {
          "extracted": [...],         # raw material pulled from uploads/web
          "planning": [...],          # planner-agent output
          "ui_suggestion": [...],     # UI-expert output
          "pending_questions": [...]  # missing-info / 待确认 items
        }

    ``status`` lifecycle:
        draft → filling → filled | pending_review
    """

    __tablename__ = "canvas_nodes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    canvas_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("canvases.id"), nullable=False, index=True
    )
    group_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("canvas_groups.id"), nullable=True, index=True
    )
    node_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    node_type: Mapped[str] = mapped_column(String(50), nullable=False, default="module_node")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    priority: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    position: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    content: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    canvas: Mapped["Canvas"] = relationship(back_populates="nodes")
    group: Mapped[Optional["CanvasGroup"]] = relationship(back_populates="nodes")
    sources: Mapped[list["NodeSource"]] = relationship(
        back_populates="node", lazy="selectin", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<CanvasNode {self.node_key or self.title} [{self.status}]>"


class CanvasEdge(Base):
    """A connection between two nodes on the same canvas."""

    __tablename__ = "canvas_edges"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    canvas_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("canvases.id"), nullable=False, index=True
    )
    source_node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("canvas_nodes.id"), nullable=False, index=True
    )
    target_node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("canvas_nodes.id"), nullable=False, index=True
    )
    edge_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Named metadata_json (not metadata) — 'metadata' is reserved by the
    # SQLAlchemy Declarative API. Same convention as DocumentChunk.metadata_json.
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    canvas: Mapped["Canvas"] = relationship(back_populates="edges")

    def __repr__(self) -> str:
        return f"<CanvasEdge {self.source_node_id} → {self.target_node_id}>"


class NodeSource(Base):
    """Provenance record for a single canvas node.

    Materializes the traceability already captured in SkillResult
    (used_cases / used_documents / used_chunks / used_external_sources) so a
    node's sources are queryable rather than buried in message metadata.

    ``source_type`` ∈ {uploaded_file, conversation, internal_sop, internal_case,
    internal_template, internal_ui, web_search, ai_completed, pending_user}

    ``source_ref_id`` is a soft reference (string UUID) — we do not build
    polymorphic foreign keys in MVP; resolution is handled in the application
    layer using source_type + source_name + quote.
    """

    __tablename__ = "node_sources"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("canvas_nodes.id"), nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_ref_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    source_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    confidence: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    quote: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Named metadata_json — 'metadata' is reserved by SQLAlchemy Declarative.
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    node: Mapped["CanvasNode"] = relationship(back_populates="sources")

    def __repr__(self) -> str:
        return f"<NodeSource {self.source_type}:{self.source_name}>"
