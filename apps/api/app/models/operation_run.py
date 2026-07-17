"""OperationRun — parent record for a presale main-flow turn (P2 基础设施).

PRESALE_DELIVERY_SPEC §11.2 known-gap: the chat auto-fill path lacked a
unified parent record tying web_search + canvas_fill + skill_execute +
persist together; debugging meant cross-referencing 4 unrelated tables.
OperationRun is the minimal parent: one row per auto-fill turn, with a
denormalised ``steps`` JSON list carrying each stage's status + timing +
error. Child rows stay where they are (retrieval_logs, skill_executions,
GenerationOutput) — OperationRun is an index, not a replacement.

Scope (minimal P2): write-path only. A read-side admin view is deferred.
"""

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OperationRun(Base):
    """A single presale main-flow operation (e.g. one auto-fill turn).

    ``steps`` is a list of ``{step, status, started_at, ended_at, error}``
    dicts — one per stage (web_search / canvas_fill / skill_execute / persist
    / memory_write). ``status`` rolls up to the worst child status.
    """

    __tablename__ = "operation_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # operation kind: "auto_fill" (today) / "conversational" / "export"…
    operation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # running / completed / failed
    status: Mapped[str] = mapped_column(String(32), default="running", nullable=False)
    steps: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<OperationRun {self.operation_type} status={self.status}>"
