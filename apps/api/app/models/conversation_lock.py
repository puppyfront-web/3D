"""ConversationLock model — application-level per-conversation chat lock.

Prevents two concurrent ``POST /conversations/{id}/chat/stream`` requests
from both triggering fill_canvas / ProposalAgent against the same conversation
(last-writer-wins data corruption). Uses a DB row + unique index as the
mutual-exclusion primitive so it works on both SQLite (tests) and Postgres
(production) with no Redis dependency.

Lifecycle:
  - ``try_acquire`` inserts a row with ``expires_at = now + ttl``; the unique
    index on ``conversation_id`` makes a concurrent insert fail atomically.
  - ``release`` deletes the row (only if the holder token matches, so a later
    request can't release an earlier one's lock).
  - Stale locks (expired ``expires_at``) are reaped on each acquire.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ConversationLock(Base):
    """A per-conversation processing lock (Defect #2)."""

    __tablename__ = "conversation_locks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    holder: Mapped[str] = mapped_column(String(64), nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __repr__(self) -> str:
        return f"<ConversationLock conv={self.conversation_id} holder={self.holder[:8]}>"
