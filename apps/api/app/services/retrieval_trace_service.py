"""Link retrieval logs to conversations/messages (KB_PRIVATE_DELIVERY_SPEC M1-7)."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.retrieval import RetrievalLog


async def patch_retrieval_log_context(
    db: AsyncSession,
    log_id: uuid.UUID,
    *,
    selected_context: Optional[Dict[str, Any]] = None,
    project_id: Optional[uuid.UUID] = None,
    conversation_id: Optional[uuid.UUID] = None,
    message_id: Optional[uuid.UUID] = None,
) -> None:
    log = await db.get(RetrievalLog, log_id)
    if log is None:
        return
    if selected_context is not None:
        log.selected_context_json = selected_context
    if project_id is not None:
        log.project_id = project_id
    if conversation_id is not None:
        log.conversation_id = conversation_id
    if message_id is not None:
        log.message_id = message_id
        log.final_output_id = str(message_id)
    await db.flush()


async def link_message_to_retrieval_log(
    db: AsyncSession,
    log_id: uuid.UUID,
    message_id: uuid.UUID,
    conversation_id: uuid.UUID,
    project_id: Optional[uuid.UUID] = None,
) -> None:
    await patch_retrieval_log_context(
        db,
        log_id,
        conversation_id=conversation_id,
        message_id=message_id,
        project_id=project_id,
    )
