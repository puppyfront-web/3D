"""Pydantic schemas for conversations and messages."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from app.schemas.common import APIBaseModel
from pydantic import AliasChoices, Field


# ─── Content Blocks ──────────────────────────────────────────────


class ContentBlock(APIBaseModel):
    """A single block of rich content within a message."""

    type: str = Field(..., description="Block type: text, company_analysis_card, proposal_section, etc.")
    content: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class RichContent(APIBaseModel):
    """Structured content made of typed blocks."""

    blocks: List[ContentBlock] = Field(default_factory=list)


# ─── Messages ────────────────────────────────────────────────────


class MessageCreate(APIBaseModel):
    """Request body for sending a message."""

    content: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        validation_alias=AliasChoices("content", "message"),
    )
    content_type: str = Field(default="text")


class MessageOut(APIBaseModel):
    """Serialized message returned to the client."""

    id: str
    conversation_id: str
    thread_id: Optional[str] = None
    role: str
    content: str
    content_type: str = "text"
    rich_content: Optional[RichContent] = None
    skill_execution_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime


# ─── Conversations ───────────────────────────────────────────────


class ConversationCreate(APIBaseModel):
    """Request body for creating a conversation."""

    project_id: Optional[str] = None
    title: Optional[str] = None


class ConversationUpdate(APIBaseModel):
    """Request body for updating a conversation."""

    title: Optional[str] = Field(None, min_length=1, max_length=500)


class ConversationOut(APIBaseModel):
    """Serialized conversation for sidebar listing."""

    id: str
    project_id: Optional[str] = None
    title: str
    status: str = "active"
    last_message: Optional[MessageOut] = None
    message_count: int = 0
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationOut):
    """Full conversation with all messages."""

    thread_id: Optional[str] = None
    messages: List[MessageOut] = Field(default_factory=list)


# ─── Chat / Streaming ────────────────────────────────────────────


class ChatRequest(APIBaseModel):
    """Request body for sending a chat message."""

    message: str = Field(..., min_length=1, max_length=10000)
    conversation_id: Optional[str] = None
    thread_id: Optional[str] = None
    project_id: Optional[str] = None
    # When set, the message is scoped to a single canvas node: the assistant
    # routes through the node-edit handler and constrains its reply to that
    # node (used by the canvas left-rail node-scoped conversation).
    node_id: Optional[str] = None
    # Force a specific intent, bypassing the ReAct intent classifier (Defect
    # #15: previously the client had no way to override intent detection).
    # Valid values: run_skill | sop_pipeline | visual_concept | conversational.
    force_intent: Optional[str] = None
    # When force_intent="run_skill", specifies which skill to run.
    force_skill_id: Optional[str] = None


class StreamChunk(APIBaseModel):
    """A single chunk in an SSE stream."""

    type: str = Field(
        ...,
        description="Chunk type: text_delta, content_block_start, content_block_data, content_block_end, done, error",
    )
    text: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class ActionRequest(APIBaseModel):
    """Request body for executing an inline action."""

    action: str = Field(..., description="Action type: run_skill, form_submit, approve, edit")
    skill_id: Optional[str] = None
    form_data: Optional[Dict[str, Any]] = None
    target_message_id: Optional[str] = None


class ClearConversationRequest(APIBaseModel):
    """Clear all messages in a scoped thread."""

    thread_id: str = Field(..., description="Thread whose messages should be removed")
