"""Skill and SkillExecution models for the Skill Runtime system."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

try:
    from sqlalchemy import JSON
    HAS_JSON = True
except ImportError:
    HAS_JSON = False


class Skill(Base):
    """Registered skill definition with manifest metadata."""

    __tablename__ = "skills"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    skill_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)

    manifest_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    input_schema_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    output_schema_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    required_services_json: Mapped[Optional[List[str]]] = mapped_column(
        JSON, nullable=True
    )
    permissions_json: Mapped[Optional[List[str]]] = mapped_column(
        JSON, nullable=True
    )

    visibility: Mapped[str] = mapped_column(
        String(50), default="internal", nullable=False
    )
    version: Mapped[str] = mapped_column(
        String(50), default="1.0.0", nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(50), default="active", nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    executions: Mapped[List["SkillExecution"]] = relationship(
        back_populates="skill", lazy="selectin", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Skill {self.skill_id}>"


class SkillExecution(Base):
    """Execution log for a skill run."""

    __tablename__ = "skill_executions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    skill_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("skills.id"), nullable=False, index=True
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("projects.id"), nullable=True, index=True
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )

    input_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    output_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(50), default="running", nullable=False
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    used_cases: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    used_documents: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    used_chunks: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    skill: Mapped["Skill"] = relationship(back_populates="executions", lazy="selectin")
    project: Mapped[Optional["Project"]] = relationship(lazy="selectin")
    user: Mapped[Optional["User"]] = relationship(lazy="selectin")

    def __repr__(self) -> str:
        return f"<SkillExecution {self.id} skill={self.skill_id} status={self.status}>"
