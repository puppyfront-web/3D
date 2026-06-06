"""Conversations router — chat endpoints with SSE streaming."""

import json
import logging
import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import Any, Dict

from app.db.session import get_db
from app.models.conversation import Conversation, Message
from app.schemas.common import Response
from app.schemas.conversation import (
    ActionRequest,
    ChatRequest,
    ConversationCreate,
    ConversationDetail,
    ConversationOut,
    MessageOut,
)
from app.services.conversation_service import ConversationService

logger = logging.getLogger(__name__)


class VisualConceptActionRequest(BaseModel):
    """Request body for visual concept version tree actions."""
    action: str  # rollback | branch | switch_branch | abandon_branch
    form_data: Dict[str, Any] = {}

router = APIRouter(prefix="/conversations", tags=["conversations"])

_conv_service = ConversationService()


def _message_to_out(m: Message) -> MessageOut:
    """Convert a Message ORM object to MessageOut schema."""
    return MessageOut(
        id=str(m.id),
        conversation_id=str(m.conversation_id),
        role=m.role,
        content=m.content,
        content_type=m.content_type,
        rich_content=m.rich_content,
        skill_execution_id=str(m.skill_execution_id) if m.skill_execution_id else None,
        metadata=m.metadata_json,
        created_at=m.created_at,
    )


async def _conv_with_stats(db: AsyncSession, conv: Conversation) -> ConversationOut:
    """Build ConversationOut with message count and last message queried explicitly."""
    # Ensure attributes are loaded (refresh if expired)
    try:
        await db.refresh(conv)
    except Exception:
        pass

    # Count messages
    count_result = await db.execute(
        select(func.count(Message.id)).where(Message.conversation_id == conv.id)
    )
    msg_count = count_result.scalar() or 0

    # Get last message
    last_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    last_msg = last_result.scalar_one_or_none()

    return ConversationOut(
        id=str(conv.id),
        project_id=str(conv.project_id) if conv.project_id else None,
        title=conv.title,
        status=conv.status,
        last_message=_message_to_out(last_msg) if last_msg else None,
        message_count=msg_count,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


# ─── CRUD ────────────────────────────────────────────────────────


@router.get("", response_model=Response[list[ConversationOut]])
async def list_conversations(
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List conversations for the sidebar."""
    conversations = await _conv_service.list_conversations(db, status=status, limit=limit)
    items = [await _conv_with_stats(db, c) for c in conversations]
    return Response(data=items, message="Conversations listed")


@router.post("", response_model=Response[ConversationOut])
async def create_conversation(
    body: ConversationCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new conversation, optionally linked to a project."""
    conv = await _conv_service.get_or_create_conversation(
        db,
        project_id=body.project_id,
    )
    if body.title:
        conv.title = body.title
    await db.flush()
    await db.refresh(conv)
    out = await _conv_with_stats(db, conv)
    return Response(data=out, message="Conversation created")


@router.get("/{conversation_id}", response_model=Response[ConversationDetail])
async def get_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get conversation detail with all messages."""
    conv = await _conv_service.get_conversation_detail(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Load messages explicitly
    messages = await _conv_service.get_history(db, conv.id)
    msg_outs = [_message_to_out(m) for m in messages]

    detail = ConversationDetail(
        id=str(conv.id),
        project_id=str(conv.project_id) if conv.project_id else None,
        title=conv.title,
        status=conv.status,
        last_message=msg_outs[-1] if msg_outs else None,
        message_count=len(msg_outs),
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=msg_outs,
    )
    return Response(data=detail, message="Conversation detail")


@router.delete("/{conversation_id}", response_model=Response[None])
async def archive_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Archive a conversation."""
    conv = await _conv_service.get_conversation_detail(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conv.status = "archived"
    await db.flush()
    return Response(message="Conversation archived")


# ─── Messages ────────────────────────────────────────────────────


@router.get("/{conversation_id}/messages", response_model=Response[list[MessageOut]])
async def list_messages(
    conversation_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Get paginated message history for a conversation."""
    messages = await _conv_service.get_history(
        db, uuid.UUID(conversation_id), limit=limit
    )
    items = [_message_to_out(m) for m in messages]
    return Response(data=items, message="Messages listed")


@router.post("/{conversation_id}/messages", response_model=Response[MessageOut])
async def send_message(
    conversation_id: str,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """Send a message (non-streaming fallback)."""
    conv = await _conv_service.get_conversation_detail(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Save user message
    await _conv_service.save_message(db, conv.id, "user", body.message)

    # Save a simple assistant response
    assistant_msg = await _conv_service.save_message(
        db, conv.id, "assistant",
        "收到您的消息，请使用流式接口获取实时回复。",
    )

    return Response(
        data=_message_to_out(assistant_msg),
        message="Message sent",
    )


# ─── SSE Streaming Chat ─────────────────────────────────────────


@router.post("/{conversation_id}/chat/stream")
async def stream_chat(
    conversation_id: str,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """SSE streaming chat endpoint.

    Returns Server-Sent Events with text deltas and content blocks.
    """
    conv = await _conv_service.get_conversation_detail(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    async def event_generator():
        async for sse_chunk in _conv_service.process_message_stream(
            db, conversation_id, body.message
        ):
            yield sse_chunk

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ─── Actions ─────────────────────────────────────────────────────


@router.post("/{conversation_id}/actions", response_model=Response[MessageOut])
async def execute_action(
    conversation_id: str,
    body: ActionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Execute an inline action (skill trigger, form submit, approve)."""
    conv = await _conv_service.get_conversation_detail(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    action_msg = await _conv_service.save_message(
        db,
        conv.id,
        "user",
        f"[Action: {body.action}]" + (f" skill={body.skill_id}" if body.skill_id else ""),
        metadata={"action": body.action, "skill_id": body.skill_id, "form_data": body.form_data},
    )

    return Response(
        data=_message_to_out(action_msg),
        message="Action recorded",
    )


# ─── File Upload ─────────────────────────────────────────────────


from app.core.config import settings

# Allowed file types for chat attachments
_CHAT_ALLOWED_EXTENSIONS = {
    ".pdf", ".ppt", ".pptx", ".doc", ".docx", ".txt", ".md",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg",
    ".mp4", ".mov", ".avi",
    ".zip", ".rar",
}
_CHAT_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}


@router.post("/{conversation_id}/upload", response_model=Response[MessageOut])
async def upload_chat_file(
    conversation_id: str,
    file: UploadFile = File(...),
    caption: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
):
    """Upload a file as a chat message attachment.

    Stores the file locally and creates a user message with attachment metadata.
    """
    conv = await _conv_service.get_conversation_detail(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    original_filename = file.filename or "unnamed"
    _, ext = os.path.splitext(original_filename)
    ext = ext.lower()

    if ext not in _CHAT_ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' not allowed. Allowed: {', '.join(sorted(_CHAT_ALLOWED_EXTENSIONS))}",
        )

    # Store file
    stored_name = f"{uuid.uuid4().hex}{ext}"
    storage_dir = os.path.abspath(os.path.join(settings.storage_path, "chat"))
    os.makedirs(storage_dir, exist_ok=True)
    file_path = os.path.join(storage_dir, stored_name)

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    is_image = ext in _CHAT_IMAGE_EXTENSIONS

    # Build message content
    display_text = caption.strip() if caption.strip() else f"上传了 {original_filename}"

    # Rich content with attachment info
    attachment_block = {
        "type": "attachment",
        "data": {
            "filename": original_filename,
            "stored_name": stored_name,
            "content_type": file.content_type or "application/octet-stream",
            "file_size": len(content),
            "is_image": is_image,
            "url": f"/storage/chat/{stored_name}",
        },
    }

    # If image, also add an image block
    blocks = {"blocks": [attachment_block]}
    if is_image:
        blocks["blocks"].insert(0, {
            "type": "visual_result",
            "data": {
                "images": [{"url": f"/storage/chat/{stored_name}", "status": "completed"}],
            },
        })

    msg = await _conv_service.save_message(
        db,
        conv.id,
        "user",
        content=display_text,
        content_type="rich",
        rich_content=blocks,
        metadata={"attachments": [attachment_block["data"]]},
        auto_commit=True,
    )

    return Response(
        data=_message_to_out(msg),
        message="File uploaded",
    )


# ─── Visual Concept — Version Tree & Artifacts ─────────────────────


async def _load_visual_concept_ctx(
    db: AsyncSession, conversation_id: str
) -> tuple["VisualConceptContext", Message | None]:
    """Load VisualConceptContext from the latest message with state metadata."""
    from app.agents.visual_concept import VisualConceptContext

    stmt = (
        select(Message)
        .where(
            Message.conversation_id == uuid.UUID(conversation_id),
            Message.metadata_json.isnot(None),
        )
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    msg = result.scalar_one_or_none()

    if msg and msg.metadata_json and "state" in msg.metadata_json:
        return VisualConceptContext.from_dict(msg.metadata_json), msg

    return VisualConceptContext(), None


@router.get("/{conversation_id}/version-tree", response_model=Response)
async def get_version_tree(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get the version tree for a conversation's visual concept context."""
    ctx, _ = await _load_visual_concept_ctx(db, conversation_id)

    if ctx.version_tree is None:
        return Response(data=None, message="No visual concept context found")

    return Response(data=ctx.version_tree.to_dict(), message="OK")


@router.get("/{conversation_id}/artifacts/{node_id}", response_model=Response)
async def get_artifact_node(
    conversation_id: str,
    node_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific version node's artifacts."""
    ctx, _ = await _load_visual_concept_ctx(db, conversation_id)

    if ctx.version_tree is None:
        raise HTTPException(status_code=404, detail="No visual concept context found")

    node = ctx.version_tree.nodes.get(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")

    return Response(data=node.to_dict(), message="OK")


@router.get("/{conversation_id}/artifacts/compare", response_model=Response)
async def compare_artifacts(
    conversation_id: str,
    node_a: str = Query(...),
    node_b: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Compare two version nodes."""
    ctx, _ = await _load_visual_concept_ctx(db, conversation_id)

    if ctx.version_tree is None:
        raise HTTPException(status_code=404, detail="No visual concept context found")

    na = ctx.version_tree.nodes.get(node_a)
    nb = ctx.version_tree.nodes.get(node_b)

    if na is None:
        raise HTTPException(status_code=404, detail=f"Node {node_a} not found")
    if nb is None:
        raise HTTPException(status_code=404, detail=f"Node {node_b} not found")

    return Response(
        data={"node_a": na.to_dict(), "node_b": nb.to_dict()},
        message="OK",
    )


@router.post("/{conversation_id}/visual-concept-actions", response_model=Response)
async def execute_visual_concept_action(
    conversation_id: str,
    body: VisualConceptActionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Execute visual concept version tree actions: rollback, branch, switch, abandon."""
    ctx, msg = await _load_visual_concept_ctx(db, conversation_id)

    if ctx.version_tree is None:
        raise HTTPException(status_code=404, detail="No visual concept context found")

    action = body.action

    if action == "rollback":
        target_node_id = body.form_data.get("target_node_id")
        if not target_node_id:
            raise HTTPException(status_code=400, detail="target_node_id is required")
        ctx.version_tree.rollback_to(target_node_id)
        # Restore requirement from the target node snapshot
        target_node = ctx.version_tree.nodes.get(target_node_id)
        if target_node and target_node.requirement_snapshot:
            from app.agents.visual_concept import VisualRequirement
            ctx.requirement = VisualRequirement.from_dict(target_node.requirement_snapshot)
        ctx.current_node_id = target_node_id

    elif action == "branch":
        from app.agents.visual_concept import VisualRequirement
        branch_name = body.form_data.get("branch_name", "新分支")
        new_node = ctx.create_next_version(
            trigger="branch",
            user_instruction=body.form_data.get("user_instruction"),
            branch_id=str(uuid.uuid4())[:8],
            branch_name=branch_name,
        )

    elif action == "switch_branch":
        branch_id = body.form_data.get("branch_id")
        if not branch_id:
            raise HTTPException(status_code=400, detail="branch_id is required")
        ctx.version_tree.switch_branch(branch_id)
        ctx.current_branch_id = branch_id
        # Update current_node_id to the branch's current node
        branch_meta = ctx.version_tree.branches.get(branch_id)
        if branch_meta:
            ctx.current_node_id = branch_meta.current_node_id

    elif action == "abandon_branch":
        branch_id = body.form_data.get("branch_id")
        if not branch_id:
            raise HTTPException(status_code=400, detail="branch_id is required")
        if branch_id == "main":
            raise HTTPException(status_code=400, detail="Cannot abandon the main branch")
        branch_meta = ctx.version_tree.branches.get(branch_id)
        if branch_meta:
            branch_meta.status = "abandoned"
        # If abandoning the active branch, switch back to main
        if ctx.version_tree.active_branch == branch_id:
            ctx.version_tree.switch_branch("main")
            ctx.current_branch_id = "main"
            main_branch = ctx.version_tree.branches.get("main")
            if main_branch:
                ctx.current_node_id = main_branch.current_node_id

    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")

    # Save updated context back to message metadata
    if msg:
        msg.metadata_json = ctx.to_dict()
    await db.commit()

    return Response(data=ctx.version_tree.to_dict(), message="OK")


# ─── Static file serving (dev only) ──────────────────────────────


from fastapi.staticfiles import StaticFiles


def mount_chat_storage(app):
    """Mount chat file storage as static files (development only)."""
    storage_dir = os.path.abspath(os.path.join(settings.storage_path, "chat"))
    os.makedirs(storage_dir, exist_ok=True)
    app.mount("/storage/chat", StaticFiles(directory=storage_dir), name="chat-storage")
