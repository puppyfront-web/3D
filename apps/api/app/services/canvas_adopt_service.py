"""Task 3: adopt a node-edit draft into the canvas node.

Mirrors the write-back discipline of ``canvas_agent_orchestrator.fill_canvas``:
preserve unchanged slots, overwrite ``planning``/``pending_questions``, set
status=filled, and append a ``NodeSource`` for provenance.
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.canvas import CanvasNode, NodeSource
from app.services.canvas_service import canvas_service

logger = logging.getLogger(__name__)


async def adopt_node_draft(
    db: AsyncSession,
    *,
    project_id: uuid.UUID,
    node_id: uuid.UUID,
    planning: List[str],
    pending_questions: Optional[List[str]] = None,
    extracted: Optional[List[str]] = None,
    sources: Optional[List[Dict[str, Any]]] = None,
) -> CanvasNode:
    """Merge the adopted draft into the node and mark it filled.

    - Keeps the old ``ui_suggestion`` and (unless overridden) ``extracted``.
    - Overwrites ``planning`` and ``pending_questions`` from the draft.
    - Sets status=filled.
    - Appends a ``NodeSource(ai_completed, "对话采纳")`` plus one row per
      ``web_search`` source in ``sources`` for provenance.
    Raises ForbiddenException (via update_node) if the node's version is not
    current or doesn't belong to ``project_id``.
    """
    node = await canvas_service.get_node(db, node_id)
    old = node.content or {}
    merged = {
        "extracted": list(extracted) if extracted is not None else list(old.get("extracted", [])),
        "planning": list(planning),
        "ui_suggestion": list(old.get("ui_suggestion", [])),
        "pending_questions": list(pending_questions) if pending_questions is not None
        else list(old.get("pending_questions", [])),
    }

    updated = await canvas_service.update_node(
        db,
        project_id=project_id,
        node_id=node_id,
        content=merged,
        status="filled",
    )

    # Provenance — primary adopt row.
    db.add(
        NodeSource(
            id=uuid.uuid4(),
            node_id=node.id,
            source_type="ai_completed",
            source_name="对话采纳",
            confidence="medium",
            quote=planning[0] if planning else None,
        )
    )
    for s in sources or []:
        if s.get("type") != "web_search":
            continue
        db.add(
            NodeSource(
                id=uuid.uuid4(),
                node_id=node.id,
                source_type="web_search",
                source_name=s.get("name") or "网络来源",
                confidence="low",
                quote=s.get("quote"),
            )
        )
    await db.flush()
    return updated
