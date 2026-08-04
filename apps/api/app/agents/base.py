"""Base classes for stateful multi-turn chat agents (Defect #5).

Extracts the 8 copy-pasted patterns shared between ProposalAgent and
VisualConceptAgent:
  - ``_sse_chunk`` (SSE frame builder)
  - ``_ensure_services`` (lazy LLM/embedding/image init)
  - parameter-card emission (missing-field prompt)
  - action-buttons emission (satisfied/modify/restart)
  - quality-check skeleton (LLM judge returning structured items)
  - review-intent classification (satisfied/modify/restart)
  - ``handle_message`` template method (ensure_services → route → try/except)

Subclasses implement:
  - ``agent_type`` (used as the metadata envelope tag, Defect #4)
  - ``_route_state`` (state-machine dispatch: COLLECTING / REVIEWING / etc.)
  - agent-specific blocks (e.g. visual_strategy, visual_result)

The metadata envelope format (``{"_agent": <agent_type>, "ctx": {...}}``) is
owned by ``BaseContext`` so the conversation_service scanner can match without
key collisions.
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

logger = logging.getLogger(__name__)


# ─── SSE helper (module-level, shared by all agents) ──────────────────────


def sse_chunk(
    chunk_type: str,
    text: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
) -> str:
    """Build an SSE-formatted string for streaming to the frontend.

    This is the single source of truth — previously copy-pasted identically
    in proposal.py:28-39 and visual_concept.py:23-34.
    """
    payload: Dict[str, Any] = {"type": chunk_type}
    if text is not None:
        payload["text"] = text
    if data is not None:
        payload["data"] = data
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


# ─── BaseContext ───────────────────────────────────────────────────────────


class BaseContext:
    """Base for agent conversation state (serialized into Message.metadata_json).

    Subclasses set ``agent_type`` and implement ``to_dict`` / ``from_dict``.
    The envelope wrappers (``to_envelope`` / ``from_envelope``) add the
    ``_agent`` tag so the conversation_service scanner can match without
    relying on fragile key-presence checks (Defect #4).
    """

    agent_type: str = "base"
    state: str = "COLLECTING"

    def to_dict(self) -> Dict[str, Any]:
        raise NotImplementedError

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaseContext":
        raise NotImplementedError

    def to_envelope(self) -> Dict[str, Any]:
        """Wrap the context dict with an agent-type tag for safe storage."""
        return {"_agent": self.agent_type, "ctx": self.to_dict()}

    @classmethod
    def from_envelope(cls, meta: Any) -> Optional["BaseContext"]:
        """Unwrap an agent context from a metadata dict.

        Returns None if the metadata doesn't match this agent's type.
        Handles both the new envelope format and legacy bare dicts (via the
        ``_legacy_keys`` hook).
        """
        if not isinstance(meta, dict):
            return None
        # New envelope format
        if meta.get("_agent") == cls.agent_type:
            return cls.from_dict(meta.get("ctx", {}))
        # Legacy bare-dict format (backward compat)
        if "_agent" not in meta:
            for key in cls._legacy_keys():
                if key in meta:
                    return cls.from_dict(meta)
        return None

    @classmethod
    def _legacy_keys(cls) -> List[str]:
        """Keys that identify a legacy (pre-envelope) metadata dict for this agent."""
        return []


# ─── BaseAgent ─────────────────────────────────────────────────────────────


class BaseAgent:
    """Template-method base for stateful chat agents.

    Subclasses set ``name`` and ``agent_type``, and implement ``_route_state``
    to dispatch on the context's state machine. The ``handle_message`` template
    handles service init, error wrapping, and the ``done`` terminal chunk.
    """

    name: str = "base"
    agent_type: str = "base"

    def __init__(self) -> None:
        self._llm: Any = None
        self._embedding: Any = None
        self._image: Any = None

    @property
    def needs_image_service(self) -> bool:
        """Override to True if the agent uses image generation."""
        return False

    async def _ensure_services(self, db: Any = None) -> None:
        """Lazily initialize LLM / embedding / image services.

        Previously copy-pasted between proposal.py:285-292 and
        visual_concept.py:575-585.
        """
        if self._llm is None:
            from app.services.llm_service import get_llm_service
            self._llm = await get_llm_service(db)
        if self._embedding is None:
            from app.services.embedding_service import get_embedding_service
            self._embedding = await get_embedding_service(db)
        if self.needs_image_service and self._image is None:
            from app.services.image_service import get_image_service
            self._image = await get_image_service(db)

    # ── SSE helpers (delegate to module-level sse_chunk) ──

    @staticmethod
    def _sse_chunk(
        chunk_type: str,
        text: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> str:
        return sse_chunk(chunk_type, text, data)

    # ── Shared emission patterns ──

    async def _emit_parameter_card(
        self, missing_fields: List[Dict[str, Any]]
    ) -> AsyncGenerator[str, None]:
        """Emit a parameter-card prompting the user to fill missing fields.

        Previously duplicated in proposal.py:392-406 and visual_concept.py:699-713.
        """
        yield sse_chunk("text_delta", text="请补充以下关键信息：")
        yield sse_chunk("parameter_card", data={"missing_fields": missing_fields})
        yield sse_chunk("done")

    async def _emit_action_buttons(self) -> AsyncGenerator[str, None]:
        """Emit the satisfied/modify/restart action buttons.

        Previously duplicated in proposal.py:569-578 and visual_concept.py:858-867.
        """
        yield sse_chunk("action_buttons", data={
            "buttons": [
                {"id": "satisfied", "label": "确认满意"},
                {"id": "modify", "label": "需要修改"},
                {"id": "restart", "label": "重新开始"},
            ]
        })

    async def _classify_review_intent(
        self, user_input: str, ctx: Any
    ) -> str:
        """Classify the user's review-phase reply: satisfied / modify / restart.

        Previously duplicated in proposal.py:425-473 and visual_concept.py:732-784.
        Uses a short LLM call with a standardized prompt.
        """
        prompt = (
            "判断用户对生成结果的反馈意图，返回 JSON：\n"
            '{"intent": "satisfied" | "modify" | "restart", "modifications": ["具体修改要求"]}\n\n'
            f"用户输入：{user_input}\n\n"
            "规则：\n"
            "1. satisfied：用户确认满意、通过、没问题、可以、好的。\n"
            "2. modify：用户提出了具体的修改意见或补充要求。\n"
            "3. restart：用户要求重新开始、从头来。\n"
            "只返回 JSON，不要其他文字。"
        )
        from app.core.prompts import GLOBAL_CAPABILITY_CONSTRAINT
        result = await self._llm.generate_json(
            prompt + "\n\n" + GLOBAL_CAPABILITY_CONSTRAINT,
            temperature=0.1,
            max_tokens=300,
        )
        intent = (result or {}).get("intent", "modify")
        if intent not in ("satisfied", "modify", "restart"):
            intent = "modify"
        return intent

    # ── Template method ──

    async def handle_message(
        self,
        user_input: str,
        ctx: BaseContext,
        db: Any = None,
        project_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Template method: ensure services → route on state → try/except.

        Subclasses implement ``_route_state`` which dispatches on ``ctx.state``.
        The try/except wrapper ensures an ``error`` + ``done`` chunk is always
        emitted, even on exception (previously duplicated identically).
        """
        try:
            await self._ensure_services(db)
            async for chunk in self._route_state(user_input, ctx, db, project_id):
                yield chunk
        except Exception as e:
            logger.exception("%s.handle_message failed", self.name)
            yield sse_chunk("error", text=f"处理失败：{e}")
            yield sse_chunk("done")

    async def _route_state(
        self,
        user_input: str,
        ctx: BaseContext,
        db: Any,
        project_id: Optional[str],
    ) -> AsyncGenerator[str, None]:
        """Dispatch on ctx.state. Override in subclasses."""
        raise NotImplementedError
