"""Conversation and Message models for chat-style interaction."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Conversation(Base):
    """A conversation thread, optionally linked to a project."""

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="新对话")
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="active", index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships — use selectinload explicitly in queries
    messages: Mapped[List["Message"]] = relationship(
        back_populates="conversation",
        lazy="raise",
        order_by="Message.created_at",
        cascade="all, delete-orphan",
    )
    project: Mapped[Optional["Project"]] = relationship(lazy="raise")

    def __repr__(self) -> str:
        return f"<Conversation {self.title}>"


class Message(Base):
    """A single message within a conversation."""

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user | assistant | system
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="text"
    )  # text | rich

    # Structured content blocks for rich AI responses
    rich_content: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True, default=None
    )

    # Optional link to a skill execution that produced this message
    skill_execution_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("skill_executions.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Arbitrary metadata (intent, detected_skill, tokens_used, etc.)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True, default=None
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    skill_execution: Mapped[Optional["SkillExecution"]] = relationship(lazy="raise")

    def __repr__(self) -> str:
        return f"<Message {self.role} in {self.conversation_id}>"
