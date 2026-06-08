"""Pydantic schemas for conversations and messages."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ─── Content Blocks ──────────────────────────────────────────────


class ContentBlock(BaseModel):
    """A single block of rich content within a message."""

    type: str = Field(..., description="Block type: text, company_analysis_card, proposal_section, etc.")
    content: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class RichContent(BaseModel):
    """Structured content made of typed blocks."""

    blocks: List[ContentBlock] = Field(default_factory=list)


# ─── Messages ────────────────────────────────────────────────────


class MessageCreate(BaseModel):
    """Request body for sending a message."""

    content: str = Field(..., min_length=1, max_length=10000)
    content_type: str = Field(default="text")


class MessageOut(BaseModel):
    """Serialized message returned to the client."""

    id: str
    conversation_id: str
    role: str
    content: str
    content_type: str = "text"
    rich_content: Optional[RichContent] = None
    skill_execution_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Conversations ───────────────────────────────────────────────


class ConversationCreate(BaseModel):
    """Request body for creating a conversation."""

    project_id: Optional[str] = None
    title: Optional[str] = None


class ConversationUpdate(BaseModel):
    """Request body for updating a conversation."""

    title: Optional[str] = Field(None, min_length=1, max_length=500)


class ConversationOut(BaseModel):
    """Serialized conversation for sidebar listing."""

    id: str
    project_id: Optional[str] = None
    title: str
    status: str = "active"
    last_message: Optional[MessageOut] = None
    message_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConversationDetail(ConversationOut):
    """Full conversation with all messages."""

    messages: List[MessageOut] = Field(default_factory=list)


# ─── Chat / Streaming ────────────────────────────────────────────


class ChatRequest(BaseModel):
    """Request body for sending a chat message."""

    message: str = Field(..., min_length=1, max_length=10000)
    conversation_id: Optional[str] = None
    project_id: Optional[str] = None


class StreamChunk(BaseModel):
    """A single chunk in an SSE stream."""

    type: str = Field(
        ...,
        description="Chunk type: text_delta, content_block_start, content_block_data, content_block_end, done, error",
    )
    text: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class ActionRequest(BaseModel):
    """Request body for executing an inline action."""

    action: str = Field(..., description="Action type: run_skill, form_submit, approve, edit")
    skill_id: Optional[str] = None
    form_data: Optional[Dict[str, Any]] = None
    target_message_id: Optional[str] = None
