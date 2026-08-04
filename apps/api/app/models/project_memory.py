"""Memory models — project-level and conversation-level memory for the presale
main flow (PRESALE_DELIVERY_SPEC §7.2).

Two scopes:

- ``ProjectMemory`` — project-wide digest keyed by ``memory_type`` (e.g.
  ``canvas_digest``, ``confirmed_facts``). Survives across conversations and
  threads so the agent does not re-ask already-confirmed information
  (P0 C1/C2 — "追问不失忆").
- ``ConversationState`` — per-conversation (optionally per-thread) ephemeral
  state, e.g. ``last_web_hits`` from the most recent ``web_search`` so a
  follow-up "刚才搜到的主营业务是什么" can be answered without a new search
  (P0 C1).

Both models use a UNIQUE constraint on their natural key so the service can
upsert without read-then-write races.
"""

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    JSON,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProjectMemory(Base):
    """Project-wide memory keyed by ``memory_type`` (one row per type per project).

    Examples:
      - memory_type="canvas_digest"  → boards / missing_info snapshot
      - memory_type="confirmed_facts" → user-confirmed screen params, budget…
    """

    __tablename__ = "project_memories"
    __table_args__ = (
        UniqueConstraint("project_id", "memory_type", name="uq_project_memory_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    memory_type: Mapped[str] = mapped_column(String(64), nullable=False)
    memory_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<ProjectMemory project={self.project_id} type={self.memory_type}>"


class ConversationState(Base):
    """Per-conversation (optionally per-thread) ephemeral state.

    ``thread_id`` is nullable so a project-scoped conversation can keep state
    without a thread, while node-scoped threads can carry their own. The
    (conversation_id, thread_id, state_key) triple is unique.
    """

    __tablename__ = "conversation_states"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id", "thread_id", "state_key",
            name="uq_conversation_state_key",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    thread_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("conversation_threads.id", ondelete="CASCADE"),
        nullable=True,
    )
    state_key: Mapped[str] = mapped_column(String(64), nullable=False)
    state_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<ConversationState conv={self.conversation_id} key={self.state_key}>"
