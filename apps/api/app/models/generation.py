"""GenerationTask and GenerationOutput models."""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class GenerationTask(Base):
    """An AI generation task record."""

    __tablename__ = "generation_tasks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    prompt_used: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model_used: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="generation_tasks", lazy="selectin")
    outputs: Mapped[List["GenerationOutput"]] = relationship(
        back_populates="task", lazy="selectin", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<GenerationTask {self.type} ({self.status})>"


class GenerationOutput(Base):
    """Output produced by a generation task."""

    __tablename__ = "generation_outputs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("generation_tasks.id"), nullable=False, index=True
    )
    content_type: Mapped[str] = mapped_column(String(100), default="text/plain", nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    used_cases: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    used_documents: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    used_chunks: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    used_sop_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Section-level metadata for human-in-the-loop review
    sections_meta: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True, default=list,
        comment="[{id, title, order, status, reviewed_by, reviewed_at}]"
    )
    version: Mapped[int] = mapped_column(default=1, server_default="1", nullable=False)
    parent_output_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("generation_outputs.id"), nullable=True,
        comment="Previous version output ID for version history"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    task: Mapped["GenerationTask"] = relationship(back_populates="outputs", lazy="selectin")

    def __repr__(self) -> str:
        return f"<GenerationOutput {self.id}>"
