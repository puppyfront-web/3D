"""ProjectMemoryService — project-level memory + per-conversation state.

PRESALE_DELIVERY_SPEC §7.2 memory layer. Two responsibilities:

1. ``build_canvas_digest`` — derive a compact JSON snapshot of the project's
   current canvas (boards / planning / missing_info / last_web_search) so a
   follow-up turn can answer "刚才填充的企业主营业务是什么?" without re-searching.
   Reuses ``canvas_research_service.build_fill_proposal_from_canvas`` for the
   shape and adds an explicit ``missing_info`` roll-up the agent can read.

2. ``upsert_project_memory`` / ``get_project_memory`` — typed JSON blobs keyed
   by (project_id, memory_type), backed by the ``project_memories`` table's
   UNIQUE constraint.

3. ``upsert_conversation_state`` / ``get_conversation_state`` — same pattern
   for ``conversation_states`` (per-conversation ephemeral state like
   ``last_web_hits``).

All writes are idempotent: an existing natural-key row is updated in place,
a missing one is inserted. The caller owns the transaction (the service
flushes but does not commit) so the presale main flow can batch memory writes
with the rest of its turn.
"""

import logging
import uuid
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project_memory import ConversationState, ProjectMemory

logger = logging.getLogger(__name__)


class ProjectMemoryService:
    """CRUD + digest builder for project / conversation memory."""

    # ─── Canvas digest ─────────────────────────────────────────────────────

    async def build_canvas_digest(
        self, db: AsyncSession, project_id
    ) -> Dict[str, Any]:
        """Compact JSON snapshot of the current canvas for follow-up turns.

        Shape (PRESALE_DELIVERY_SPEC §7.2 — project memory):
          {
            "boards": [
              {"board_key": ..., "board_title": ...,
               "nodes": [{"node_key": ..., "node_title": ...,
                          "points": [...], "pending_questions": [...]}]}
            ],
            "missing_info": [...],   # rolled up across nodes
            "last_web_search": None  # placeholder; set by caller via state
          }

        Reuses canvas_research_service.build_fill_proposal_from_canvas for the
        boards shape and rolls pending_questions into a flat missing_info list
        the LLM can read at a glance. Never raises — a digest failure degrades
        to an empty digest so the caller (auto-fill) doesn't abort.
        """
        try:
            from app.services.canvas_research_service import (
                build_fill_proposal_from_canvas,
            )

            proposal = await build_fill_proposal_from_canvas(db, project_id)
        except Exception:
            logger.exception(
                "project_memory: build_fill_proposal_from_canvas failed; "
                "returning empty digest"
            )
            return {"boards": [], "missing_info": [], "last_web_search": None}

        boards = proposal.get("boards") or []
        missing_info: list[str] = []
        for board in boards:
            for node in board.get("nodes") or []:
                for q in node.get("pending_questions") or []:
                    if q and q not in missing_info:
                        missing_info.append(q)

        return {
            "boards": boards,
            "missing_info": missing_info,
            "last_web_search": None,  # filled by caller from conversation state
        }

    # ─── Project memory upsert / get ───────────────────────────────────────

    async def upsert_project_memory(
        self,
        db: AsyncSession,
        project_id,
        memory_type: str,
        memory_json: Dict[str, Any],
    ) -> ProjectMemory:
        """Insert-or-update the (project_id, memory_type) row.

        Natural-key dedup: query first, then UPDATE or INSERT. SQLite's
        NULL-handling makes the UNIQUE constraint unreliable for composite
        keys with nullable parts, but project_memories has no nullable key
        columns — still, going through query-then-write keeps the path
        identical to ConversationState and avoids IntegrityError recovery.
        """
        proj_uuid = uuid.UUID(str(project_id))
        existing = await self._fetch_project_memory(db, proj_uuid, memory_type)
        if existing is not None:
            existing.memory_json = memory_json
            await db.flush()
            return existing
        mem = ProjectMemory(
            project_id=proj_uuid,
            memory_type=memory_type,
            memory_json=memory_json,
        )
        db.add(mem)
        await db.flush()
        return mem

    async def get_project_memory(
        self, db: AsyncSession, project_id, memory_type: str
    ) -> Optional[Dict[str, Any]]:
        """Return the memory_json for (project_id, memory_type) or None."""
        proj_uuid = uuid.UUID(str(project_id))
        mem = await self._fetch_project_memory(db, proj_uuid, memory_type)
        return mem.memory_json if mem is not None else None

    @staticmethod
    async def _fetch_project_memory(
        db: AsyncSession, project_id: uuid.UUID, memory_type: str
    ) -> Optional[ProjectMemory]:
        result = await db.execute(
            select(ProjectMemory).where(
                ProjectMemory.project_id == project_id,
                ProjectMemory.memory_type == memory_type,
            )
        )
        return result.scalar_one_or_none()

    # ─── Conversation state upsert / get ───────────────────────────────────

    async def upsert_conversation_state(
        self,
        db: AsyncSession,
        conversation_id,
        state_key: str,
        state_json: Dict[str, Any],
        thread_id=None,
    ) -> ConversationState:
        """Insert-or-update a (conversation_id, thread_id, state_key) row.

        thread_id is optional; NULL thread_id is the project-scoped default.
        """
        conv_uuid = uuid.UUID(str(conversation_id))
        thread_uuid = uuid.UUID(str(thread_id)) if thread_id else None
        existing = await self._fetch_conversation_state(
            db, conv_uuid, state_key, thread_uuid
        )
        if existing is not None:
            existing.state_json = state_json
            await db.flush()
            return existing
        state = ConversationState(
            conversation_id=conv_uuid,
            thread_id=thread_uuid,
            state_key=state_key,
            state_json=state_json,
        )
        db.add(state)
        await db.flush()
        return state

    async def get_conversation_state(
        self,
        db: AsyncSession,
        conversation_id,
        state_key: str,
        thread_id=None,
    ) -> Optional[Dict[str, Any]]:
        conv_uuid = uuid.UUID(str(conversation_id))
        thread_uuid = uuid.UUID(str(thread_id)) if thread_id else None
        state = await self._fetch_conversation_state(
            db, conv_uuid, state_key, thread_uuid
        )
        return state.state_json if state is not None else None

    @staticmethod
    async def _fetch_conversation_state(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        state_key: str,
        thread_id: Optional[uuid.UUID],
    ) -> Optional[ConversationState]:
        result = await db.execute(
            select(ConversationState).where(
                ConversationState.conversation_id == conversation_id,
                ConversationState.state_key == state_key,
                # Explicit NULL-safe match: thread_id == thread_id OR both NULL.
                # PyRedis-equivalent: `IS NOT DISTINCT FROM`.
                (
                    ConversationState.thread_id == thread_id
                    if thread_id is not None
                    else ConversationState.thread_id.is_(None)
                ),
            )
        )
        return result.scalar_one_or_none()


project_memory_service = ProjectMemoryService()
