"""Conversations router — chat endpoints with SSE streaming."""

import asyncio
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
    MessageCreate,
    ConversationUpdate,
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
        thread_id=str(m.thread_id) if m.thread_id else None,
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
    project_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List conversations for the sidebar.

    Optional `project_id` scopes the list to a single project (canvas workspace).
    """
    conversations = await _conv_service.list_conversations(
        db, status=status, project_id=project_id, limit=limit
    )
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
        thread_id=None,
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


@router.patch("/{conversation_id}", response_model=Response[ConversationOut])
async def update_conversation(
    conversation_id: str,
    body: ConversationUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a conversation (e.g. rename title)."""
    conv = await _conv_service.get_conversation_detail(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if body.title is not None:
        conv.title = body.title
    await db.flush()
    out = await _conv_with_stats(db, conv)
    return Response(data=out, message="Conversation updated")


# ─── SSE Streaming Chat ─────────────────────────────────────────


@router.post("/{conversation_id}/chat/stream")
async def stream_chat(
    conversation_id: str,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """SSE streaming chat endpoint.

    Returns Server-Sent Events with text deltas and content blocks.

    Acquires a per-conversation lock before streaming so two concurrent
    messages can't both drive fill_canvas / ProposalAgent against the same
    conversation (Defect #2). Returns 409 if the conversation is busy.
    """
    conv = await _conv_service.get_conversation_detail(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Acquire the conversation lock using a dedicated short-lived session
    # (NOT the request-scoped streaming db session — that one lives for the
    # whole SSE stream and would pin the lock row's transaction).
    from app.db.session import async_session_factory
    from app.services.conversation_lock_service import conversation_lock_service

    conv_uuid = conv.id
    async with async_session_factory() as lock_db:
        lock_token = await conversation_lock_service.try_acquire(lock_db, conv_uuid)
    if lock_token is None:
        raise HTTPException(
            status_code=409,
            detail="该会话正在处理中，请稍候再试",
        )

    async def event_generator():
        try:
            async for sse_chunk in _conv_service.process_message_stream(
                db,
                conversation_id,
                body.message,
                node_id=body.node_id,
                thread_id=body.thread_id,
                force_intent=body.force_intent,
                force_skill_id=body.force_skill_id,
            ):
                yield sse_chunk
        except asyncio.CancelledError:
            # The client disconnected — StreamingResponse cancels the generator,
            # surfacing as CancelledError inside the async for. Log it and stop
            # driving the (now-useless) LLM / agent work into the void, instead
            # of letting the stream run to completion against nobody.
            logger.info(
                "SSE client disconnected for conversation %s", conversation_id
            )
            raise  # Re-raise so the framework can finish cleaning up.
        finally:
            # Always release the lock — even on exception / client disconnect —
            # so a crashed handler doesn't hold the lock until TTL expires.
            async with async_session_factory() as release_db:
                await conversation_lock_service.release(release_db, conv_uuid, lock_token)

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


@router.post("/{conversation_id}/messages", response_model=Response[MessageOut])
async def create_message(
    conversation_id: str,
    body: MessageCreate,
    db: AsyncSession = Depends(get_db),
):
    """Non-streaming fallback used by tests and simple message posting."""
    conv = await _conv_service.get_conversation_detail(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    user_msg = await _conv_service.save_message(
        db,
        conv.id,
        "user",
        body.content,
        content_type=body.content_type,
    )
    await _conv_service.save_message(
        db,
        conv.id,
        "assistant",
        f"已记录你的消息：{body.content}",
    )
    await db.commit()

    return Response(
        data=_message_to_out(user_msg),
        message="Message created",
    )


# ─── File Upload ─────────────────────────────────────────────────


from app.core.config import settings

# Allowed file types for chat attachments
# NOTE: legacy binary .doc/.ppt removed — no parser handles them. Users must
# convert to .docx/.pptx. Knowledge-base upload (document_service.py) is the
# stricter allowlist; this one is for chat attachments which may also include
# images/video/archives that are stored but not content-parsed.
_CHAT_ALLOWED_EXTENSIONS = {
    ".pdf", ".pptx", ".docx", ".txt", ".md",
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
    For text-parseable types (pdf/pptx/docx/txt/md) a Document row is also
    created so the attachment shows up in the project's document list with a
    parse_status, and can be re-parsed / categorised / deleted from the
    workspace attachment tray (PRD §11).
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
            detail=f"不支持的文件类型 '{ext}'，允许：{', '.join(sorted(_CHAT_ALLOWED_EXTENSIONS))}",
        )

    # Read content and enforce size limit before touching disk.
    content = await file.read()
    if len(content) > settings.max_upload_size:
        raise HTTPException(
            status_code=400,
            detail=f"文件过大：{len(content)} 字节，上限 {settings.max_upload_size} 字节",
        )

    # Store file
    stored_name = f"{uuid.uuid4().hex}{ext}"
    storage_dir = os.path.abspath(os.path.join(settings.storage_path, "chat"))
    os.makedirs(storage_dir, exist_ok=True)
    file_path = os.path.join(storage_dir, stored_name)

    with open(file_path, "wb") as f:
        f.write(content)

    is_image = ext in _CHAT_IMAGE_EXTENSIONS

    # Build message content
    display_text = caption.strip() if caption.strip() else f"上传了 {original_filename}"

    # Parseable text documents also get a Document row so the attachment tray
    # can track parse_status / category / re-parse / delete (PRD §11.3-11.5).
    parseable_exts = {".pdf", ".pptx", ".docx", ".txt", ".md", ".xlsx", ".xls", ".csv"}
    document_id_str: str | None = None
    initial_parse_status = "uploaded"
    if ext in parseable_exts:
        try:
            from app.models.document import Document

            doc = Document(
                project_id=conv.project_id,
                filename=stored_name,
                original_filename=original_filename,
                content_type=file.content_type or "application/octet-stream",
                file_size=len(content),
                file_path=file_path,
                title=original_filename,
                status="uploaded",
                parse_status="uploaded",
                chunk_count=0,
            )
            db.add(doc)
            await db.flush()
            document_id_str = str(doc.id)
        except Exception:  # noqa: BLE001 — Document creation is best-effort
            logger.warning("Failed to create Document row for chat attachment", exc_info=True)

    # Rich content with attachment info
    attachment_data = {
        "filename": original_filename,
        "stored_name": stored_name,
        "content_type": file.content_type or "application/octet-stream",
        "file_size": len(content),
        "is_image": is_image,
        "url": f"/api/v1/conversations/files/{stored_name}",
        "document_id": document_id_str,
        "parse_status": initial_parse_status,
    }
    attachment_block = {"type": "attachment", "data": attachment_data}

    # If image, also add an image block
    blocks = {"blocks": [attachment_block]}
    if is_image:
        blocks["blocks"].insert(0, {
            "type": "visual_result",
            "data": {
                "images": [{"url": f"/api/v1/conversations/files/{stored_name}", "status": "completed"}],
            },
        })

    msg = await _conv_service.save_message(
        db,
        conv.id,
        "user",
        content=display_text,
        content_type="rich",
        rich_content=blocks,
        metadata={"attachments": [attachment_data]},
        auto_commit=True,
    )

    # Kick off indexing asynchronously so the tray flips to "parsed" once done.
    # Failures are non-fatal — the document keeps parse_status="uploaded" and
    # the user can re-parse from the tray (PRD §11.5).
    if document_id_str:
        try:
            from app.services.document_service import document_service

            await document_service.index_document(uuid.UUID(document_id_str), db)
            await db.commit()
        except Exception:  # noqa: BLE001 — async parse is best-effort
            logger.warning("Async parse failed for attachment %s", document_id_str, exc_info=True)

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


# ─── Auth-gated file serving (replaces the open StaticFiles mount) ──


import re

from fastapi.responses import FileResponse

from app.core.security import get_current_user


@router.get("/files/{stored_name}")
async def serve_chat_file(
    stored_name: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Serve a chat attachment file.

    Auth-gated and path-traversal-safe, replacing the previous open
    ``StaticFiles`` mount at ``/storage/chat`` which exposed every uploaded
    attachment to unauthenticated callers.
    """
    # Prevent path traversal: only allow alphanumeric + dash + dot.
    if not re.match(r"^[a-zA-Z0-9\-\.]+$", stored_name):
        raise HTTPException(status_code=400, detail="Invalid filename")
    storage_dir = os.path.abspath(os.path.join(settings.storage_path, "chat"))
    file_path = os.path.join(storage_dir, stored_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)
