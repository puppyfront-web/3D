"""Conversation orchestration service — manages chat flow and skill routing."""

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.prompts import GLOBAL_CAPABILITY_CONSTRAINT
from app.models.conversation import Conversation, ConversationThread, Message
from app.services import canvas_research_service
from app.services.intent_service import IntentDetector, IntentResult
from app.services.llm_service import get_llm_service
from app.services.search_helper import acquire_web_context

logger = logging.getLogger(__name__)
_REF_DOC_RE = re.compile(r"\[ref_doc:([0-9a-fA-F-]{32,36})\]")

# System prompt for conversational mode — KB-first answers with conclusion + plan.
_CONVERSATION_SYSTEM_PROMPT = """你是企业知识库与方案问答助手，服务内部业务、销售、策划与项目经理。

你的任务是：基于【企业内部知识库命中】与（如有）【网络搜索命中】，给出**可直接使用的结论与方案建议**，而不是空泛建议。

回答结构（按问题选用，必须清晰）：
1. **结论** — 1–3 句话直接回答核心问题
2. **方案建议** — 分点列出可执行建议、步骤或选项（若适用）
3. **依据** — 说明关键判断来自哪些内部资料，正文用 [1][2] 标注引用序号
4. **待确认** — 资料不足或存在歧义时，列出「⚠️ 需要进一步确认：…」

原则：
- **内部资料优先**；外网信息仅作补充，须标注「来自网络」。
- 禁止编造案例、报价、合同条款、交付工期或未在资料中出现的承诺。
- 资料未覆盖时明确写「资料中未找到相关信息」，不要臆测。
- 用户要方案/对比/选型时，给出结构化方案要点，而非「建议你考虑…」式空话。
""" + GLOBAL_CAPABILITY_CONSTRAINT


def _parse_sse(chunk: str) -> Optional[Dict[str, Any]]:
    """Parse one SSE-formatted line (`data: {json}\\n\\n`) into a dict.

    Returns None for non-SSE or malformed lines (mirrors the frontend, which
    silently ignores unparseable chunks).
    """
    if not chunk or not chunk.startswith("data: "):
        return None
    try:
        return json.loads(chunk[len("data: "):].strip())
    except (ValueError, TypeError):
        return None


# Short summaries for the common result-bearing block types, used as a fallback
# when an agent flow streamed structured blocks but no plain text deltas.
_BLOCK_SUMMARY_HINTS: Dict[str, str] = {
    "proposal_section": "已生成策划案",
    "proposal_result": "已生成策划案",
    "visual_result": "已生成视觉方案",
    "company_analysis": "已生成企业解析",
    "artifact_summary": "已生成内容产物",
    "image_result": "已生成图片",
}


def _serialize_proposal_to_profile(proposal: dict) -> str:
    """把 canvas_fill_proposal 的 Proposal 序列化成企业画像文本,作为 proposal_generation 的 context_pack。"""
    lines = ["【企业画像（来自画布采集填充）】"]
    for board in proposal.get("boards", []):
        lines.append(f"\n## {board.get('board_title','')}")
        for n in board.get("nodes", []):
            pts = n.get("points") or []
            if pts:
                lines.append(f"- {n.get('node_title','')}：{'；'.join(pts)}")
    summary = proposal.get("summary") or {}
    if summary.get("missing_info"):
        lines.append("\n【待确认/缺失信息】：" + "；".join(summary["missing_info"]))
    return "\n".join(lines)


class _StreamAccumulator:
    """Collects user-facing text + content blocks from an SSE chunk stream.

    Mirrors the frontend's collection logic in apps/web/lib/chat-api.ts
    (streamChat `done` handler) so that what gets persisted to the DB matches
    exactly what the user saw during live streaming. This is what makes a
    conversation survive reload (switching chats and coming back): the agent
    flows previously persisted only a placeholder string and lost all real
    content.
    """

    _STRUCTURAL = {
        "content_block_start",
        "content_block_end",
        "done",
        "error",
    }

    def __init__(self) -> None:
        self._text: List[str] = []
        self.blocks: List[Dict[str, Any]] = []

    def feed(self, sse_chunk: str) -> None:
        payload = _parse_sse(sse_chunk)
        if payload is None:
            return
        ctype = payload.get("type")
        if ctype == "text_delta":
            text = payload.get("text") or ""
            if text:
                self._text.append(text)
        elif ctype == "content_block_data":
            data = payload.get("data") or {}
            if isinstance(data, dict) and data.get("type"):
                self.blocks.append(data)
        elif ctype in self._STRUCTURAL:
            return
        else:
            # Raw block type (skill_progress / action_buttons / visual_result /
            # context_card / artifact_summary / quality_check / ...). The
            # frontend collects these as {type, data}. Unknown-type payloads
            # carry only structural/internal text (debug or marker strings), so
            # a non-dict payload is discarded rather than persisted as user-
            # facing message content.
            data = payload.get("data")
            if isinstance(data, dict):
                self.blocks.append({"type": ctype, "data": data})

    @property
    def text(self) -> str:
        joined = "".join(self._text)
        if joined.strip():
            return joined
        # Fallback: some agent flows (proposal / visual generation) stream only
        # structured blocks and no text deltas, leaving _text empty. An empty
        # assistant message would (a) render blank after reload and (b) make
        # some LLM providers 400 when the history is replayed next turn. When we
        # do have blocks, synthesize a short honest summary from the block types.
        for block in self.blocks:
            hint = _BLOCK_SUMMARY_HINTS.get(block.get("type") or "")
            if hint:
                return hint
        return "已生成结果" if self.blocks else ""

    @property
    def rich_content(self) -> Optional[Dict[str, Any]]:
        return {"blocks": self.blocks} if self.blocks else None


class ConversationService:
    """Orchestrates the full conversation flow."""

    def __init__(self) -> None:
        self._intent_detector = IntentDetector()

    async def get_or_create_conversation(
        self,
        db: AsyncSession,
        project_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> Conversation:
        """Get an existing conversation or create a new one."""
        if conversation_id:
            result = await db.execute(
                select(Conversation).where(Conversation.id == uuid.UUID(conversation_id))
            )
            conv = result.scalar_one_or_none()
            if conv:
                return conv

        # Try to find existing conversation for project
        if project_id:
            result = await db.execute(
                select(Conversation)
                .where(
                    Conversation.project_id == uuid.UUID(project_id),
                    Conversation.status == "active",
                )
                .order_by(Conversation.updated_at.desc())
                .limit(1)
            )
            conv = result.scalar_one_or_none()
            if conv:
                return conv

        # Create new conversation
        conv = Conversation(
            id=uuid.uuid4(),
            project_id=uuid.UUID(project_id) if project_id else None,
            title="新对话",
            status="active",
        )
        db.add(conv)
        await db.commit()
        await db.refresh(conv)
        return conv

    async def get_or_create_thread(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
        scope_type: str,
        scope_ref_id: Optional[str] = None,
    ) -> ConversationThread:
        """Get or create a scoped thread within a conversation."""
        result = await db.execute(
            select(ConversationThread).where(
                ConversationThread.conversation_id == conversation_id,
                ConversationThread.scope_type == scope_type,
                ConversationThread.scope_ref_id == scope_ref_id,
                ConversationThread.status == "active",
            )
        )
        thread = result.scalar_one_or_none()
        if thread:
            return thread

        thread = ConversationThread(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            scope_type=scope_type,
            scope_ref_id=scope_ref_id,
            status="active",
        )
        db.add(thread)
        await db.flush()
        return thread

    async def get_thread(
        self,
        db: AsyncSession,
        thread_id: str | uuid.UUID,
    ) -> Optional[ConversationThread]:
        """Load a single thread by id."""
        thread_uuid = thread_id if isinstance(thread_id, uuid.UUID) else uuid.UUID(thread_id)
        result = await db.execute(
            select(ConversationThread).where(ConversationThread.id == thread_uuid)
        )
        return result.scalar_one_or_none()

    async def get_default_thread(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
    ) -> ConversationThread:
        """Resolve the default thread for a conversation."""
        conv_result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conv = conv_result.scalar_one_or_none()
        if conv is None:
            raise ValueError(f"Conversation not found: {conversation_id}")
        scope_type = "project" if conv.project_id else "root"
        return await self.get_or_create_thread(
            db,
            conversation_id=conversation_id,
            scope_type=scope_type,
        )

    async def list_conversations(
        self,
        db: AsyncSession,
        status: Optional[str] = None,
        project_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Conversation]:
        """List conversations for the sidebar, newest first.

        By default only active conversations are returned.
        Pass status explicitly to include archived or other statuses.
        Pass project_id to scope to a single project (used by the canvas workspace).
        """
        stmt = select(Conversation).order_by(Conversation.updated_at.desc())
        if status:
            stmt = stmt.where(Conversation.status == status)
        else:
            stmt = stmt.where(Conversation.status != "archived")
        if project_id:
            stmt = stmt.where(Conversation.project_id == uuid.UUID(project_id))
        stmt = stmt.limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_conversation_detail(
        self, db: AsyncSession, conversation_id: str
    ) -> Optional[Conversation]:
        """Get conversation by ID."""
        result = await db.execute(
            select(Conversation).where(Conversation.id == uuid.UUID(conversation_id))
        )
        return result.scalar_one_or_none()

    async def save_message(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
        role: str,
        content: str,
        thread_id: Optional[uuid.UUID] = None,
        content_type: str = "text",
        rich_content: Optional[Dict[str, Any]] = None,
        skill_execution_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        auto_commit: bool = False,
    ) -> Message:
        """Save a message to the database.

        If auto_commit=True, commits immediately to release DB locks (needed for SSE).
        """
        if thread_id is None:
            metadata_node_id = None
            if isinstance(metadata, dict):
                raw_node_id = metadata.get("node_id")
                if isinstance(raw_node_id, str) and raw_node_id:
                    metadata_node_id = raw_node_id
            if metadata_node_id:
                thread = await self.get_or_create_thread(
                    db,
                    conversation_id=conversation_id,
                    scope_type="node",
                    scope_ref_id=metadata_node_id,
                )
                if role == "assistant":
                    recent_messages = list(
                        (
                            await db.execute(
                                select(Message)
                                .where(Message.conversation_id == conversation_id)
                                .order_by(Message.created_at.desc())
                                .limit(12)
                            )
                        ).scalars().all()
                    )
                    matching_user = None
                    fallback_user = None
                    for candidate in recent_messages:
                        if candidate.role != "user":
                            continue
                        candidate_metadata = candidate.metadata_json or {}
                        if candidate_metadata.get("node_id") == metadata_node_id:
                            matching_user = candidate
                            break
                        if fallback_user is None and not candidate_metadata.get("node_id"):
                            fallback_user = candidate
                    previous_message = matching_user or fallback_user
                    if previous_message is not None and previous_message.thread_id != thread.id:
                        previous_message.thread_id = thread.id
            else:
                thread = await self.get_default_thread(db, conversation_id)
            thread_id = thread.id
        msg = Message(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            thread_id=thread_id,
            role=role,
            content=content,
            content_type=content_type,
            rich_content=rich_content,
            skill_execution_id=uuid.UUID(skill_execution_id) if skill_execution_id else None,
            metadata_json=metadata,
        )
        db.add(msg)

        # Update conversation timestamp and title
        conv_result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conv = conv_result.scalar_one_or_none()
        if conv:
            conv.updated_at = datetime.now(timezone.utc)
            if role == "user" and conv.title == "新对话":
                conv.title = content[:50] + ("..." if len(content) > 50 else "")

        if auto_commit:
            await db.commit()
        else:
            await db.flush()

        return msg

    async def get_history(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
        limit: int = 50,
    ) -> List[Message]:
        """Load message history for a conversation."""
        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_thread_history(
        self,
        db: AsyncSession,
        thread_id: uuid.UUID,
        limit: int = 50,
    ) -> List[Message]:
        """Load message history for a thread."""
        result = await db.execute(
            select(Message)
            .where(Message.thread_id == thread_id)
            .order_by(Message.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def clear_thread_messages(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
        thread_id: uuid.UUID,
    ) -> int:
        """Delete all messages in a thread. Returns removed count."""
        from sqlalchemy import delete

        thread = await self.get_thread(db, thread_id)
        if thread is None or thread.conversation_id != conversation_id:
            raise ValueError("Conversation thread not found")

        result = await db.execute(
            delete(Message).where(
                Message.conversation_id == conversation_id,
                Message.thread_id == thread_id,
            )
        )
        await db.commit()
        return int(result.rowcount or 0)

    def filter_messages_for_scope(
        self,
        messages: List[Message],
        node_id: Optional[str] = None,
    ) -> List[Message]:
        """Filter project conversation history to global or node scope.

        Global scope excludes any node-scoped turn. Node scope returns only the
        turn(s) attributed to that node. Legacy node turns are supported by
        inferring the user message's scope from assistant replies before the
        next user message.
        """
        scoped: List[Message] = []
        total = len(messages)

        def _message_node_scope(index: int) -> Optional[str]:
            msg = messages[index]
            metadata = msg.metadata_json or {}
            direct = metadata.get("node_id")
            if isinstance(direct, str) and direct:
                return direct

            if msg.role != "user":
                return None

            for next_index in range(index + 1, total):
                next_msg = messages[next_index]
                if next_msg.role == "user":
                    break
                next_meta = next_msg.metadata_json or {}
                inferred = next_meta.get("node_id")
                if (
                    next_msg.role == "assistant"
                    and next_meta.get("intent") == "node_edit"
                    and isinstance(inferred, str)
                    and inferred
                ):
                    return inferred
            return None

        for index, message in enumerate(messages):
            message_scope = _message_node_scope(index)
            if node_id:
                if message_scope == node_id:
                    scoped.append(message)
            else:
                if message_scope is None:
                    scoped.append(message)
        return scoped

    def build_message_history(
        self, messages: List[Message]
    ) -> List[Dict[str, str]]:
        """Convert DB messages to the format LLM expects.

        Skips messages whose ``content`` is empty/blank: some providers reject
        an assistant turn with empty content with a 400, and a blank message
        carries no signal for the model anyway.
        """
        history: List[Dict[str, str]] = []
        for msg in messages:
            if msg.role in ("user", "assistant") and (msg.content or "").strip():
                history.append({"role": msg.role, "content": msg.content})
        return history

    async def _load_ref_docs_context(
        self,
        db: AsyncSession,
        user_message: str,
    ) -> tuple[str, List[Dict[str, Any]]]:
        """Resolve [ref_doc:...] handles into chunk summaries + provenance."""
        from app.models.document import Document, DocumentChunk

        doc_ids: List[uuid.UUID] = []
        for raw_id in _REF_DOC_RE.findall(user_message or ""):
            try:
                doc_ids.append(uuid.UUID(raw_id))
            except ValueError:
                continue
        if not doc_ids:
            return "", []

        summaries: List[str] = []
        sources: List[Dict[str, Any]] = []
        for doc_id in doc_ids[:5]:
            document = await db.get(Document, doc_id)
            if document is None:
                continue
            result = await db.execute(
                select(DocumentChunk)
                .where(DocumentChunk.document_id == doc_id)
                .order_by(DocumentChunk.chunk_index.asc())
                .limit(3)
            )
            chunks = result.scalars().all()
            excerpt = "\n".join(
                chunk.content.strip() for chunk in chunks if (chunk.content or "").strip()
            )[:1500]
            if excerpt:
                summaries.append(f"《{document.title or document.original_filename}》\n{excerpt}")
            sources.append(
                {
                    "document_id": str(document.id),
                    "project_id": str(document.project_id) if document.project_id else None,
                    "title": document.title,
                    "filename": document.original_filename,
                    "excerpt": excerpt[:300] if excerpt else "",
                    "chunk_ids": [str(chunk.id) for chunk in chunks],
                }
            )
        return "\n\n".join(summaries), sources

    async def process_message_stream(
        self,
        db: AsyncSession,
        conversation_id: str,
        user_message: str,
        node_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        force_intent: Optional[str] = None,
        force_skill_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Process a user message and yield SSE chunks.

        Flow:
        1. Save user message (with immediate commit to release DB lock)
        2. Load history
        2.5. If node_id is set, route to node-scoped edit handler (skips intent)
        3. Detect intent
        4. Route to skill or conversational LLM
        5. Stream response
        6. Save assistant message
        """
        conv_uuid = uuid.UUID(conversation_id)

        try:
            if thread_id:
                active_thread = await self.get_thread(db, thread_id)
                if active_thread is None or active_thread.conversation_id != conv_uuid:
                    raise ValueError("Conversation thread not found")
            elif node_id:
                active_thread = await self.get_or_create_thread(
                    db,
                    conv_uuid,
                    scope_type="node",
                    scope_ref_id=node_id,
                )
            else:
                active_thread = await self.get_default_thread(db, conv_uuid)

            # 1. Save user message and commit immediately to release DB lock
            user_metadata = {"node_id": node_id} if node_id else None
            await self.save_message(
                db,
                conv_uuid,
                "user",
                user_message,
                thread_id=active_thread.id,
                metadata=user_metadata,
                auto_commit=True,
            )

            # 2. Load history (after commit, so the new message is visible)
            messages = await self.get_thread_history(db, active_thread.id)
            history = self.build_message_history(messages)

            # 2.5 Node-scoped conversation short-circuit. When the caller binds
            # the chat to a single canvas node, skip the IntentDetector and the
            # ProposalAgent/auto-fill paths entirely — node edits are an
            # isolated concern and must never be captured by a multi-turn
            # agent state machine.
            if node_id:
                async for chunk in self._handle_node_edit(
                    db, conv_uuid, user_message, node_id, history, active_thread.id
                ):
                    yield chunk
                return

            # 2.6 First-message auto-fill (PRD §3.3 MVP loop). When this is the
            # very first user message in the project conversation AND the user
            # is describing an enterprise need (not a social greeting), trigger
            # the web_search + fill_canvas pipeline so the canvas populates
            # automatically. This is the core of the "input → auto-fill" loop.
            conv = await self.get_conversation_detail(db, conversation_id)
            project_id = str(conv.project_id) if conv and conv.project_id else None
            prior_user_msgs = [m for m in messages if m.role == "user"]
            is_first_message = len(prior_user_msgs) == 1  # only the just-saved one
            if (
                settings.canvas_auto_fill_enabled
                and is_first_message
                and project_id
                and not self._is_social_greeting(user_message)
            ):
                async for chunk in self._handle_auto_fill(
                    db, conv_uuid, user_message, project_id
                ):
                    yield chunk
                return

            # 2.7 Social greetings (你好/谢谢/在吗 …). Reply with a fixed
            # courteous acknowledgement without invoking the LLM or any
            # workflow — keeps the experience snappy for non-task input.
            if self._is_social_greeting(user_message):
                async for chunk in self._handle_smalltalk(
                    db, conv_uuid, user_message
                ):
                    yield chunk
                return

            # 3. Detect intent — or use a forced override (Defect #15: the
            # client had no way to bypass intent detection; now force_intent /
            # force_skill_id let the caller pin a specific path).
            #
            # NOTE: the legacy ProposalAgent multi-turn state machine was
            # removed — the canvas orchestrator is now the single planning
            # path (sop_pipeline → _handle_auto_fill). Old conversations that
            # still carry ProposalContext metadata in their message history
            # are no longer resumed; they fall through to normal intent
            # detection and re-generate on the canvas like any new request.
            if force_intent:
                from app.services.intent_service import IntentResult
                intent = IntentResult(
                    intent=force_intent,
                    skill_id=force_skill_id,
                    confidence=1.0,
                    reply_hint="",
                )
                logger.info("Intent FORCED by client: %s (skill=%s)", intent.intent, intent.skill_id)
            else:
                intent: IntentResult = await self._intent_detector.detect(
                    user_message, history, db=db
                )
                logger.info(
                    "Intent detected: %s (skill=%s, confidence=%.2f)",
                    intent.intent,
                    intent.skill_id,
                    intent.confidence,
                )

            # 4. Route based on intent. Note: sop_pipeline (the legacy plan-
            # execution path) was removed; a "full proposal" request now also
            # routes to auto-fill so the canvas is the single source of truth.
            # run_skill / visual_concept remain as explicit single-skill paths.
            if intent.intent == "sop_pipeline" and intent.skill_id is None:
                if project_id:
                    async for chunk in self._handle_auto_fill(
                        db, conv_uuid, user_message, project_id, force=True
                    ):
                        yield chunk
                else:
                    async for chunk in self._handle_conversational(
                        db, conv_uuid, user_message, history, project_id
                    ):
                        yield chunk
            elif intent.intent == "run_skill" and intent.skill_id:
                async for chunk in self._handle_skill_execution(
                    db, conv_uuid, intent, history
                ):
                    yield chunk
            elif intent.intent == "visual_concept":
                async for chunk in self._handle_visual_concept(
                    db, conv_uuid, user_message, intent, thread_id=active_thread.id
                ):
                    yield chunk
            else:
                # Non-first, non-social, non-skill message: lightweight reply
                # that guides the user back to node-scoped editing on canvas.
                async for chunk in self._handle_conversational(
                    db, conv_uuid, user_message, history, project_id
                ):
                    yield chunk

        except Exception as e:
            logger.exception("Unhandled error in process_message_stream")
            err_str = str(e).lower()
            if "timeout" in err_str or "timed out" in err_str:
                error_text = "抱歉，AI 服务响应超时，请稍后重试。"
            elif "database is locked" in err_str:
                error_text = "抱歉，系统繁忙，请稍后重试。"
            else:
                error_text = f"抱歉，处理您的请求时发生错误：{e}"
            yield f"data: {json.dumps({'type': 'text_delta', 'text': error_text})}\n\n"
        finally:
            # Always send the done event so the frontend doesn't hang
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    async def _handle_skill_execution(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
        intent: IntentResult,
        history: List[Dict[str, str]],
    ) -> AsyncGenerator[str, None]:
        """Handle a skill execution intent.

        If the skill can run (has required inputs), execute it.
        If not (e.g. no project_id), fall back to conversational LLM response
        so the user still gets a useful answer instead of an error.
        """
        skill_id = intent.skill_id

        try:
            from app.skills.base import SkillContext
            from app.skills.registry import SkillRegistry
            from app.skills.runner import SkillRunner
            from app.services.embedding_service import get_embedding_service
            from app.services.image_service import get_image_service

            registry = SkillRegistry.get_instance()
            if not registry.list_skills():
                registry.auto_register()
            # Tools (web_search, knowledge_search, ...) are registered at app
            # startup in main.py lifespan. This guard is a defensive fallback
            # for test paths that bypass lifespan — it must never be the primary
            # registration site (Defect #1: lazy registration left ProposalAgent's
            # direct ToolRegistry.get calls with an empty registry on fresh processes).
            from app.tools.registry import ToolRegistry
            tool_registry = ToolRegistry.get_instance()
            if not tool_registry.list_tools():
                tool_registry.auto_register()
            if not registry.has(skill_id):
                # Skill not registered — fall back to conversational
                async for chunk in self._handle_conversational(
                    db, conversation_id, intent.input_data.get("user_message", ""), history
                ):
                    yield chunk
                return

            # Get conversation to find project_id
            conv = await self.get_conversation_detail(db, str(conversation_id))
            project_id = str(conv.project_id) if conv and conv.project_id else None

            # Build input data from intent + history context
            # Include user_message so skills can work in conversation mode
            input_data = {**intent.input_data}
            # Always propagate user_message to company_info/requirement_text
            # so skills that read those keys can work in conversation mode.
            if input_data.get("user_message"):
                input_data.setdefault("company_info", input_data["user_message"])
                input_data.setdefault("requirement_text", input_data["user_message"])
                input_data.setdefault("context_text", input_data["user_message"])
            elif history:
                # Get the last user message from history
                for msg in reversed(history):
                    if msg.get("role") == "user":
                        input_data.setdefault("user_message", msg["content"])
                        input_data.setdefault("company_info", msg["content"])
                        input_data.setdefault("requirement_text", msg["content"])
                        input_data.setdefault("context_text", msg["content"])
                        break
            if skill_id == "image_generation" and not input_data.get("prompt"):
                prompt_source = input_data.get("user_message")
                if not prompt_source:
                    for msg in reversed(history):
                        if msg.get("role") == "user":
                            prompt_source = msg["content"]
                            break
                if prompt_source:
                    input_data["prompt"] = self._extract_image_prompt(str(prompt_source))
            if project_id:
                input_data["project_id"] = project_id

            # ── Pre-validation: quick checks before invoking LLM ──
            quick_response = self._quick_prevalidate(skill_id, input_data)
            if quick_response:
                yield f"data: {json.dumps({'type': 'text_delta', 'text': quick_response})}\n\n"
                await self.save_message(
                    db, conversation_id, "assistant",
                    content=quick_response,
                    content_type="text",
                    metadata={"intent": "run_skill", "skill_id": skill_id, "prevalidated": True},
                    auto_commit=True,
                )
                return

            # Use a separate DB session for skill execution to avoid
            # SQLite deadlocks when the SSE stream session holds a
            # write lock and SkillRunner tries to flush().
            from app.db.session import async_session_factory

            logger.info("_handle_skill_execution: creating separate DB session for skill %s", skill_id)
            async with async_session_factory() as skill_db:
                logger.info("_handle_skill_execution: session created, building context")
                llm_svc = await get_llm_service(skill_db)
                logger.info("_handle_skill_execution: LLM service = %s", type(llm_svc).__name__)
                emb_svc = await get_embedding_service(skill_db)
                img_svc = await get_image_service(skill_db)
                context = SkillContext(
                    project_id=project_id,
                    user_id=None,
                    db=skill_db,
                    llm_service=llm_svc,
                    embedding_service=emb_svc,
                    image_service=img_svc,
                )

                # Notify frontend that a skill is starting — send as content block
                skill = registry.get(skill_id)
                skill_name = skill.manifest.name if skill else skill_id
                # Surface a reasoning step so the UI's thinking panel shows what
                # the assistant is about to do before the skill_executing block
                # (and its spinner) takes over. Mirrors _handle_conversational.
                yield f"data: {json.dumps({'type': 'thinking_delta', 'text': '正在调用「%s」技能，准备上下文并执行 SOP 步骤…' % skill_name})}\n\n"
                yield f"data: {json.dumps({'type': 'content_block_start', 'data': {'block_type': 'skill_executing'}})}\n\n"
                yield f"data: {json.dumps({'type': 'content_block_data', 'data': {'type': 'skill_executing', 'data': {'skill_id': skill_id, 'name': skill_name}}})}\n\n"
                yield f"data: {json.dumps({'type': 'content_block_end'})}\n\n"

                runner = SkillRunner(registry)
                result = await runner.run_with_react(skill_id, input_data, context)

                # Handle ReAct ask_user — stream the question to user
                if result.get("_react_ask_user"):
                    ask_text = result["_react_ask_user"]
                    yield f"data: {json.dumps({'type': 'text_delta', 'text': ask_text})}\n\n"
                    await self.save_message(
                        db, conversation_id, "assistant",
                        content=ask_text,
                        content_type="text",
                        metadata={"intent": "run_skill", "skill_id": skill_id, "react_ask": True},
                        auto_commit=True,
                    )
                    return

                # Auto-chain visual_prompt → image_generation within same session
                if result.get("success") and skill_id == "visual_prompt":
                    output = result.get("output", {})
                    if isinstance(output, dict) and output.get("positive_prompt"):
                        image_input = {
                            "prompt": output["positive_prompt"],
                            "negative_prompt": output.get("negative_prompt", ""),
                            "width": input_data.get("width", 1024),
                            "height": input_data.get("height", 768),
                            "style": output.get("visual_strategy", {}).get("concept") if isinstance(output.get("visual_strategy"), dict) else None,
                        }
                        if project_id:
                            image_input["project_id"] = project_id
                        collected_images: list[dict] = []
                        for _idx in range(2):
                            image_result = await runner.run("image_generation", image_input, context)
                            if image_result.get("success"):
                                img_url = image_result.get("output", {}).get("image_url")
                                if img_url:
                                    collected_images.append({"url": img_url})
                        if collected_images:
                            output["images"] = collected_images
                            output["image_url"] = collected_images[0]["url"]

                # Commit skill execution records
                await skill_db.commit()

            # Skill finished — surface a reasoning step before the structured
            # result renders, so the thinking panel narrates the transition.
            yield f"data: {json.dumps({'type': 'thinking_delta', 'text': '技能执行完成，正在整理结构化结果与引用来源…'})}\n\n"

            if result.get("success"):
                output = result.get("output", {})

                # Render skill output as readable text for the user
                content_text = self._render_skill_output(skill_id, output)

                # Create rich content blocks
                blocks: Dict[str, Any] = {
                    "blocks": [
                        {"type": "skill_progress", "data": {
                            "skill_id": skill_id,
                            "status": "completed",
                            "duration_ms": result.get("duration_ms", 0),
                        }},
                    ]
                }

                # Add skill-specific content block
                if skill_id == "company_analysis" and isinstance(output, dict):
                    blocks["blocks"].append({"type": "company_analysis_card", "data": output})
                elif skill_id == "proposal_generation" and isinstance(output, dict):
                    blocks["blocks"].append({"type": "proposal_section", "data": output})
                elif skill_id in ("visual_prompt", "image_generation") and isinstance(output, dict):
                    blocks["blocks"].append({"type": "visual_result", "data": output})
                elif skill_id == "export" and isinstance(output, dict):
                    blocks["blocks"].append({"type": "artifact", "data": output})

                # Stream the content text
                yield f"data: {json.dumps({'type': 'text_delta', 'text': content_text})}\n\n"

                # Stream ALL content blocks (skill_progress completed + result block)
                # so the frontend receives the completion signal, not just the last block.
                for block in blocks["blocks"]:
                    yield f"data: {json.dumps({'type': 'content_block_start', 'data': {'block_type': block['type']}})}\n\n"
                    yield f"data: {json.dumps({'type': 'content_block_data', 'data': block})}\n\n"
                    yield f"data: {json.dumps({'type': 'content_block_end'})}\n\n"

                # Save assistant message
                await self.save_message(
                    db, conversation_id, "assistant",
                    content=content_text,
                    content_type="rich",
                    rich_content=blocks,
                    skill_execution_id=result.get("execution_id"),
                    metadata={"intent": "run_skill", "skill_id": skill_id},
                    auto_commit=True,
                )
            else:
                if skill_id == "image_generation":
                    error_text = (
                        "图片生成失败，未收到可展示的图片结果。"
                        f"\n\n失败原因：{result.get('error') or '缺少必要参数或图片服务不可用'}"
                    )
                    yield f"data: {json.dumps({'type': 'text_delta', 'text': error_text})}\n\n"
                    await self.save_message(
                        db, conversation_id, "assistant",
                        content=error_text,
                        content_type="text",
                        metadata={
                            "intent": "run_skill",
                            "skill_id": skill_id,
                            "status": "failed",
                            "error": result.get("error"),
                        },
                        auto_commit=True,
                    )
                    return
                # Skill failed (missing inputs etc.) — fall back to conversational LLM
                logger.info(
                    "Skill %s failed (%s), falling back to conversational",
                    skill_id, result.get("error"),
                )
                async for chunk in self._handle_conversational(
                    db, conversation_id, intent.input_data.get("user_message", ""), history
                ):
                    yield chunk

        except Exception as e:
            logger.exception("Skill execution error in conversation")
            if skill_id == "image_generation":
                error_text = f"图片生成失败，未收到可展示的图片结果。\n\n失败原因：{e}"
                yield f"data: {json.dumps({'type': 'text_delta', 'text': error_text})}\n\n"
                await self.save_message(
                    db, conversation_id, "assistant",
                    content=error_text,
                    content_type="text",
                    metadata={
                        "intent": "run_skill",
                        "skill_id": skill_id,
                        "status": "failed",
                        "error": str(e),
                    },
                    auto_commit=True,
                )
                return
            # Fall back to conversational on any exception
            async for chunk in self._handle_conversational(
                db, conversation_id, intent.input_data.get("user_message", ""), history
            ):
                yield chunk

    @staticmethod
    def _quick_prevalidate(skill_id: str, input_data: dict) -> str | None:
        """Rule-based pre-validation for skills — returns a quick response
        message if required inputs are missing, or None to proceed normally.

        This check does NOT call the LLM; it uses simple string heuristics
        so the user gets an immediate response.
        """
        if skill_id == "company_analysis":
            company_info = input_data.get("company_info", "") or ""
            requirement = input_data.get("requirement_text", "") or ""
            user_msg = input_data.get("user_message", "") or ""
            combined = f"{company_info} {requirement} {user_msg}".strip()

            # Strip common trigger phrases to see if any real info remains
            trigger_phrases = [
                "帮我进行企业解析", "帮我做企业解析", "进行企业解析",
                "帮我分析一下企业", "帮我分析企业", "企业解析",
                "企业分析", "分析一下企业", "分析企业",
            ]
            cleaned = combined
            for phrase in trigger_phrases:
                cleaned = cleaned.replace(phrase, " ")
            cleaned = " ".join(cleaned.split()).strip()

            # If nothing meaningful is left, ask for info
            if len(cleaned) < 2:
                return (
                    "请描述你要解析的对象或问题，我将基于你提供的信息进行结构化分析。\n\n"
                    "可以输入：\n"
                    "- 一段背景描述或资料摘要\n"
                    "- 某个行业/产品/场景的说明\n"
                    "- 上传资料后在对话中引用\n\n"
                    "示例：*「分析裸眼3D幕墙在品牌发布场景的应用要点」*"
                )

        return None

    @staticmethod
    def _extract_image_prompt(message: str) -> str:
        """Derive an image prompt from direct chat wording."""
        prompt = message.strip()
        for marker in ("生成图片", "图片生成", "生成一张", "生成一个", "生成", "生图", "出图", "效果图", "图片", "图像"):
            prompt = prompt.replace(marker, " ")
        prompt = " ".join(prompt.split())
        return prompt or message.strip()

    def _load_visual_concept_ctx(self, messages: List[Message]) -> "VisualConceptContext":
        """从消息历史中恢复 VisualConceptContext。

        匹配优先级（防止 key 碰撞，Defect #4）：
        1. 新格式信封 ``{"_agent": "visual_concept", "ctx": {...}}``
        2. 旧格式：metadata 里有 ``state`` key（向后兼容）
        """
        from app.agents.visual_concept import VisualConceptContext

        for msg in reversed(messages):
            if not msg.metadata_json:
                continue
            meta = msg.metadata_json
            # New envelope format
            if isinstance(meta, dict) and meta.get("_agent") == "visual_concept":
                return VisualConceptContext.from_dict(meta.get("ctx", {}))
            # Legacy: bare dict with "state" key (backward compat)
            if isinstance(meta, dict) and "state" in meta and "_agent" not in meta:
                return VisualConceptContext.from_dict(meta)
        return VisualConceptContext()

    async def _handle_visual_concept(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
        user_message: str,
        intent: IntentResult,
        thread_id: Optional[uuid.UUID] = None,
    ) -> AsyncGenerator[str, None]:
        """处理视觉概念图生成请求。"""
        from app.agents.visual_concept import VisualConceptAgent, VisualConceptContext

        # Thread-scoped history (Defect #4: prevents cross-thread state leakage).
        history = (
            await self.get_thread_history(db, thread_id)
            if thread_id
            else await self.get_history(db, conversation_id)
        )
        ctx = self._load_visual_concept_ctx(history)

        # Load project_id from conversation for context auto-fill
        conv = await self.get_conversation_detail(db, str(conversation_id))
        project_id = str(conv.project_id) if conv and conv.project_id else None

        if ctx.state == "COLLECTING" and not ctx.requirement.raw_input:
            ctx.requirement.raw_input = user_message

        # Surface the visual-concept pipeline as a reasoning step so the
        # thinking panel narrates the plan before image generation runs.
        if ctx.state == "COLLECTING":
            yield f"data: {json.dumps({'type': 'thinking_delta', 'text': '正在解析视觉需求 → 匹配视觉风格库 → 确认创意方向…'})}\n\n"
        else:
            yield f"data: {json.dumps({'type': 'thinking_delta', 'text': '基于策划案与风格偏好，生成视觉策略 + 正负向 Prompt → 调用图片生成…'})}\n\n"

        agent = VisualConceptAgent()
        acc = _StreamAccumulator()
        async for chunk in agent.handle_message(user_message, ctx, db, project_id=project_id):
            yield chunk
            acc.feed(chunk)

        # Persist the real streamed content (text + blocks) so the conversation
        # survives reload. Internal markers like "[visual concept context
        # saved]" must never be user-facing message content; the live SSE
        # stream is exactly what should be persisted.
        # The metadata uses an agent-tagged envelope (Defect #4) so the
        # state-restore scanner can match on "_agent" without key collisions.
        await self.save_message(
            db=db,
            conversation_id=conversation_id,
            role="assistant",
            content=acc.text,
            content_type="rich" if acc.blocks else "text",
            rich_content=acc.rich_content,
            metadata={"_agent": "visual_concept", "ctx": ctx.to_dict()},
            auto_commit=True,
        )

    def _render_skill_output(self, skill_id: str, output: Dict[str, Any]) -> str:
        """Render skill output into readable text for the user."""
        if skill_id == "company_analysis":
            return self._render_company_analysis_output(output)
        elif skill_id == "proposal_generation":
            return self._render_proposal_output(output)
        elif skill_id in ("visual_prompt", "image_generation"):
            return self._render_visual_output(output)
        elif skill_id == "export":
            return self._render_export_output(output)
        elif skill_id == "case_retrieval":
            return self._render_case_retrieval_output(output)
        # Generic fallback — natural language, never raw JSON
        if output:
            # Try to produce a brief human-readable summary
            name = output.get("name") or output.get("title") or ""
            if name:
                return f"「{name}」已完成，详情见下方卡片。"
            return "任务已完成，详情见下方卡片。"
        return "执行完成。"

    def _render_company_analysis_output(self, output: Dict[str, Any]) -> str:
        """Render company analysis as readable text."""
        lines = []

        analysis = output.get("analysis", output)
        if isinstance(analysis, str):
            return analysis

        # Six Views
        six_views = output.get("six_views") or analysis.get("six_views")
        if six_views and isinstance(six_views, dict):
            lines.append("## 企业六看\n")
            dim_labels = {
                "backward_history": ("向后看·发展历史", ["founding", "origin", "core_philosophy"]),
                "forward_planning": ("向前看·发展规划", ["strategy", "product_roadmap", "market_expansion"]),
                "left_competitors": ("向左看·竞争对手", None),
                "right_industry": ("向右看·行业情况", ["trends", "market_landscape"]),
                "upward_policy": ("向上看·政策背景", ["national_policy", "local_policy"]),
                "downward_niche": ("向下看·生态位", ["core_advantage", "irreplaceability"]),
            }
            for key, (label, fields) in dim_labels.items():
                data = six_views.get(key)
                if not data:
                    continue
                if isinstance(data, dict):
                    if fields:
                        parts = [f"  - {f}: {data.get(f, '')}" for f in fields if data.get(f)]
                    else:
                        parts = [f"  - {k}: {v}" for k, v in data.items() if v]
                    if parts:
                        lines.append(f"**{label}**:")
                        lines.extend(parts)
                elif isinstance(data, (list, str)):
                    lines.append(f"**{label}**: {data}")
            lines.append("")

        # Technology Architecture
        tech_arch = output.get("technology_arch") or analysis.get("technology_arch")
        if tech_arch and isinstance(tech_arch, dict):
            lines.append("## 技术一张图\n")
            for layer in tech_arch.get("layers", []):
                metaphor = layer.get("metaphor", "")
                metaphor_tag = f"（{metaphor}）" if metaphor else ""
                lines.append(f"- **{layer.get('name', '')}**{metaphor_tag}: {layer.get('description', '')}")
            summary = tech_arch.get("core_technology_summary", "")
            if summary:
                lines.append(f"\n核心技术总结: {summary}")
            lines.append("")

        # Project Background
        proj_bg = output.get("project_background") or analysis.get("project_background")
        if proj_bg and isinstance(proj_bg, dict):
            lines.append("## 项目背景\n")
            bg_labels = {
                "national_policy": "宏观·国家政策",
                "city_or_industry": "中观·城市/行业",
                "project_positioning": "微观·项目定位",
            }
            for key, label in bg_labels.items():
                data = proj_bg.get(key)
                if not data:
                    continue
                if isinstance(data, dict):
                    title = data.get("title", "")
                    content = data.get("content", "")
                    lines.append(f"**{label}**: {title}")
                    if content:
                        lines.append(f"  {content}")
                elif isinstance(data, str):
                    lines.append(f"**{label}**: {data}")
            lines.append("")

        # Regular analysis fields
        for field, label in [
            ("strengths", "企业优势"), ("weaknesses", "企业劣势"),
            ("product_service_features", "产品/服务特点"),
            ("target_audience", "目标客户"), ("communication_goals", "传播目标"),
            ("visual_preferences", "推荐视觉方向"),
        ]:
            val = analysis.get(field)
            if val:
                if isinstance(val, list):
                    # Skip empty lists — prompt now leaves them empty when no evidence
                    items = [str(v) for v in val if v]
                    if items:
                        lines.append(f"**{label}**: {', '.join(items)}")
                else:
                    lines.append(f"**{label}**: {val}")

        # External search results — the actual fetched content (key points,
        # sources, conflicts). Per AGENTS.md §3, this is the primary thing the
        # user wants to see, not guidance/suggestions.
        es = output.get("external_search")
        used_sources = output.get("used_external_sources", []) or []
        if es or used_sources:
            lines.append("\n## 联网检索结果\n")
            status = (es or {}).get("status") if es else None
            if status == "ok" and used_sources:
                lines.append("**已联网核实客观信息**，以下为检索到的公开信息：\n")
            elif status in ("degraded", "failed"):
                # Only place guidance-style text is allowed: when web_search
                # genuinely failed to fetch anything.
                reason = (es or {}).get("degraded_reason") or status
                lines.append(f"⚠️ 本次未能联网核实客观信息（{reason}），下方未展示的字段均为未获取到。\n")

            # Key points
            key_points = (es or {}).get("key_points", []) if es else []
            if key_points:
                lines.append("**关键发现**：")
                for kp in key_points:
                    lines.append(f"- {kp}")
                lines.append("")

            # Conflicts
            conflicts = (es or {}).get("conflicts", []) if es else []
            if conflicts:
                lines.append("**信息冲突**（不同来源说法不一致）：")
                for c in conflicts:
                    lines.append(f"- {c}")
                lines.append("")

            # Source list — actual fetched snippets with traceable URLs
            if used_sources:
                lines.append("**信息来源**：")
                for i, src in enumerate(used_sources, 1):
                    title = src.get("title", "") or "（无标题）"
                    url = src.get("url", "")
                    domain = src.get("domain", "")
                    pub = src.get("published_at")
                    snippet = (src.get("snippet", "") or "").strip().replace("\n", " ")
                    title_part = f"[{title}]({url})" if url else title
                    meta_parts = [p for p in [domain, pub] if p]
                    meta = f" — {' · '.join(meta_parts)}" if meta_parts else ""
                    lines.append(f"{i}. {title_part}{meta}")
                    if snippet:
                        lines.append(f"   > {snippet}")
                lines.append("")

        return "\n".join(lines) if lines else "企业分析完成，详情见下方卡片。"

    def _render_proposal_output(self, output: Dict[str, Any]) -> str:
        """Render proposal as readable text."""
        content = output.get("content", "")
        if content:
            return content
        return "策划案生成完成，详情见下方卡片。"

    def _render_visual_output(self, output: Dict[str, Any]) -> str:
        """Render visual output — show image result, not internal strategy/prompt."""
        images = output.get("images", [])
        image_url = output.get("image_url")
        if images:
            return f"✅ 已生成 {len(images)} 张效果图，见下方卡片。"
        elif image_url:
            return "✅ 效果图已生成，见下方卡片。"
        return "视觉方案生成完成。"

    def _render_export_output(self, output: Dict[str, Any]) -> str:
        return f"方案导出完成: {output.get('filename', '文件已生成')}"

    def _render_case_retrieval_output(self, output: Dict[str, Any]) -> str:
        cases = output.get("cases", [])
        if not cases:
            return "未找到匹配案例。"
        lines = [f"找到 {len(cases)} 个相关案例:\n"]
        for i, c in enumerate(cases, 1):
            if isinstance(c, dict):
                lines.append(f"{i}. **{c.get('title', '未命名')}** — {c.get('client_name', '')}")
            else:
                lines.append(f"{i}. {c}")
        return "\n".join(lines)

    async def _handle_conversational(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
        user_message: str,
        history: List[Dict[str, str]],
        project_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """KB-first conversational Q&A with optional web supplement."""
        from app.services.knowledge_context_service import (
            acquire_kb_context,
            is_web_search_enabled,
        )

        llm = await get_llm_service(db)
        full_text = ""
        msg = (user_message or "").strip()
        is_real_question = bool(msg) and not self._is_social_greeting(msg) and len(msg) >= 4

        kb_citations: List[Dict[str, Any]] = []
        kb_meta: Dict[str, Any] = {}

        if is_real_question:
            yield f"data: {json.dumps({'type': 'thinking_delta', 'text': '正在检索企业知识库…'}, ensure_ascii=False)}\n\n"
            try:
                kb_citations, kb_block, kb_meta = await acquire_kb_context(
                    db, msg, project_id=project_id, top_k=8,
                    conversation_id=conversation_id,
                )
            except Exception:
                logger.exception("conversational: kb retrieval failed; continuing.")
                kb_block = ""
            else:
                if kb_citations:
                    yield f"data: {json.dumps({'type': 'thinking_delta', 'text': f'命中 {len(kb_citations)} 条内部资料'}, ensure_ascii=False)}\n\n"
        else:
            kb_block = ""

        web_hits: List[Dict[str, Any]] = []
        web_enabled = await is_web_search_enabled(db)
        if is_real_question and web_enabled:
            try:
                web_hits, _ = await acquire_web_context(
                    db, msg, max_results=5, context_hint=msg
                )
            except Exception:
                logger.exception("conversational: web search failed; continuing.")

        system_prompt = _CONVERSATION_SYSTEM_PROMPT
        if kb_block:
            system_prompt += kb_block
        if web_hits:
            web_block = "\n".join(
                f"- {h.get('title') or h.get('domain')}：{(h.get('snippet') or '').strip()[:120]}"
                for h in web_hits[:5]
            )
            system_prompt = (
                system_prompt
                + f"\n\n【网络搜索命中】（补充信息，标注来自网络）\n{web_block}\n"
            )
        elif is_real_question and not web_enabled:
            system_prompt += "\n\n【联网搜索】已关闭，仅使用内部知识库与对话上下文。\n"

        # ── PRESALE_DELIVERY_SPEC §7.2 — inject project memory so follow-up
        # turns don't "失忆". The canvas_digest carries the boards / missing_info
        # from the most recent auto-fill, and last_web_hits carries the prior
        # search so a question like "刚才搜到的主营业务是什么?" can cite it
        # without a new search. Both are best-effort: missing/empty memory
        # degrades silently to no injection.
        if project_id:
            try:
                from app.services.project_memory_service import (
                    project_memory_service,
                )

                proj_uuid_mem = (
                    uuid.UUID(project_id) if isinstance(project_id, str) else project_id
                )
                digest = await project_memory_service.get_project_memory(
                    db, proj_uuid_mem, "canvas_digest"
                )
                if digest and digest.get("boards"):
                    digest_blob = json.dumps(digest, ensure_ascii=False)[:4000]
                    system_prompt = (
                        system_prompt
                        + f"\n\n【项目上下文摘要】\n{digest_blob}\n"
                    )
                last_kb = await project_memory_service.get_conversation_state(
                    db, conversation_id, "last_kb_citations"
                )
                if last_kb and last_kb.get("citations"):
                    prior_kb = "\n".join(
                        f"- [{c.get('index')}] {c.get('title') or '资料'}"
                        for c in (last_kb.get("citations") or [])[:5]
                    )
                    system_prompt = (
                        system_prompt
                        + f"\n\n【上一轮知识库引用】\n{prior_kb}\n"
                    )
                last_web = await project_memory_service.get_conversation_state(
                    db, conversation_id, "last_web_hits"
                )
                if last_web and last_web.get("hits"):
                    prior_block = "\n".join(
                        f"- {h.get('title') or h.get('domain')}：{(h.get('snippet') or '').strip()[:120]}"
                        for h in (last_web.get("hits") or [])[:3]
                    )
                    system_prompt = (
                        system_prompt
                        + f"\n\n【上一轮联网检索】（用户追问上轮结果时引用，不要重复搜索）\n{prior_block}\n"
                    )
            except Exception:
                logger.exception(
                    "conversational: inject project memory failed; continuing"
                )

        rich_stream = getattr(llm, "generate_with_history_stream_rich", None)

        if web_hits and not kb_citations:
            thinking = "内部资料较少，已补充网络检索，正在组织回复…"
        elif kb_citations:
            thinking = "已检索知识库，正在整理结论与方案…"
        else:
            thinking = "正在理解你的问题并组织回复…"
        yield f"data: {json.dumps({'type': 'thinking_delta', 'text': thinking}, ensure_ascii=False)}\n\n"

        if rich_stream is not None:
            got_real_thinking = False
            first_content_sent = False
            async for kind, text in rich_stream(
                messages=history,
                system_prompt=system_prompt,
                temperature=0.7,
            ):
                if kind == "thinking":
                    if not got_real_thinking:
                        got_real_thinking = True
                    yield f"data: {json.dumps({'type': 'thinking_delta', 'text': text}, ensure_ascii=False)}\n\n"
                else:
                    if not first_content_sent:
                        first_content_sent = True
                        if not got_real_thinking:
                            yield f"data: {json.dumps({'type': 'thinking_delta', 'text': '已理解需求，正在组织回复…'}, ensure_ascii=False)}\n\n"
                    full_text += text
                    yield f"data: {json.dumps({'type': 'text_delta', 'text': text}, ensure_ascii=False)}\n\n"
        else:
            async for chunk in llm.generate_with_history_stream(
                messages=history,
                system_prompt=system_prompt,
                temperature=0.7,
            ):
                full_text += chunk
                yield f"data: {json.dumps({'type': 'text_delta', 'text': chunk}, ensure_ascii=False)}\n\n"

        citation_block: Optional[Dict[str, Any]] = None
        if kb_citations or web_hits:
            citation_block = {
                "type": "knowledge_citations",
                "data": {
                    "citations": kb_citations,
                    "web_sources": [
                        {
                            "title": h.get("title") or h.get("domain"),
                            "url": h.get("url"),
                            "snippet": (h.get("snippet") or "")[:160],
                        }
                        for h in web_hits[:5]
                    ],
                    "kb_meta": kb_meta,
                },
            }
            yield f"data: {json.dumps({'type': 'content_block_start', 'data': {'block_type': 'knowledge_citations'}}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'content_block_data', 'data': citation_block}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'content_block_end'}, ensure_ascii=False)}\n\n"

        if kb_citations:
            try:
                from app.services.project_memory_service import project_memory_service

                await project_memory_service.upsert_conversation_state(
                    db,
                    conversation_id,
                    "last_kb_citations",
                    {"citations": kb_citations, "query": msg},
                )
            except Exception:
                logger.exception("conversational: persist last_kb_citations failed")

        rich_content = (
            {"blocks": [citation_block]} if citation_block else None
        )
        log_id_raw = kb_meta.get("retrieval_log_id")
        assistant_msg = await self.save_message(
            db, conversation_id, "assistant",
            content=full_text,
            content_type="text",
            rich_content=rich_content,
            metadata={
                "intent": "conversational",
                "kb_hit_count": kb_meta.get("total", 0),
                "web_hit_count": len(web_hits),
                "retrieval_log_ids": [log_id_raw] if log_id_raw else [],
                "citations": kb_citations,
            },
            auto_commit=True,
        )
        if log_id_raw:
            try:
                from app.services.retrieval_trace_service import link_message_to_retrieval_log

                proj_uuid = None
                if project_id:
                    try:
                        proj_uuid = uuid.UUID(project_id)
                    except (ValueError, TypeError):
                        proj_uuid = None
                await link_message_to_retrieval_log(
                    db,
                    uuid.UUID(log_id_raw),
                    assistant_msg.id,
                    conversation_id,
                    project_id=proj_uuid,
                )
                await db.commit()
            except Exception:
                logger.exception("conversational: link retrieval log to message failed")

    async def _handle_node_edit(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
        user_message: str,
        node_id: str,
        history: List[Dict[str, str]],
        thread_id: uuid.UUID,
    ) -> AsyncGenerator[str, None]:
        """Handle a node-scoped conversation (PRD §15) — DIRECT-OUTPUT mode.

        Loads the node's current content + sources + a web-search pass, then
        asks the LLM — streaming — to WRITE the finished copy for THIS single
        node (not advise on how to write it). The streamed body is shown to
        the user as-is; after streaming we split out an optional
        「【还需你提供】」tail into pending questions and emit a structured
        ``node_draft`` block so the UI can offer a one-click 「采纳到节点」.

        Per product decision (单节点隔离 + AI 直出成品 → 用户一键采纳):
          - Reply IS the finished node copy; the user adopts it via the
            adopt endpoint (Task 3) when satisfied — we do NOT write here.
          - Only the current node is in scope.
        """
        from app.services.canvas_service import canvas_service

        try:
            node = await canvas_service.get_node(db, uuid.UUID(node_id))
        except Exception:
            logger.exception("node_edit: failed to load node %s", node_id)
            yield f"data: {json.dumps({'type': 'text_delta', 'text': '无法加载该节点，请返回全局对话后重试。'}, ensure_ascii=False)}\n\n"
            return

        if not node:
            yield f"data: {json.dumps({'type': 'text_delta', 'text': '未找到该节点，可能已被删除。'}, ensure_ascii=False)}\n\n"
            return

        node_title = node.title or node.node_key or "该节点"
        content = node.content or {}
        planning = content.get("planning", []) or []
        extracted = content.get("extracted", []) or []
        pending = content.get("pending_questions", []) or []
        sources = node.sources or []
        sources_brief = (
            ", ".join(
                f"{s.source_name or s.source_type}({s.confidence or '—'})"
                for s in sources[:5]
            )
            or "（暂无来源）"
        )

        # ── Task 1: web-search pass with a context-aware rewritten query ──
        context_hint = f"画布节点：{node_title}；用户要求：{user_message}；已有资料：{self._fmt_slot(extracted)}"
        web_hits: List[Dict[str, Any]] = []
        web_summary: Dict[str, Any] = {}
        try:
            web_hits, web_summary = await acquire_web_context(
                db, user_message, max_results=5, context_hint=context_hint
            )
        except Exception:
            logger.exception("node_edit: web search failed for node %s; continuing without.", node_id)

        web_block = (
            "（无网络命中）"
            if not web_hits
            else "\n".join(
                f"- {h.get('title') or h.get('domain')}：{(h.get('snippet') or '').strip()[:120]}"
                for h in web_hits[:5]
            )
        )

        # ── Build the node-edit system prompt (direct-output, not advisory) ──
        context_block = (
            f"当前节点：{node_title}\n\n"
            f"【已有资料提取】\n{self._fmt_slot(extracted)}\n\n"
            f"【已有策划内容】\n{self._fmt_slot(planning)}\n\n"
            f"【待确认项】\n{self._fmt_slot(pending)}\n\n"
            f"【信息来源】{sources_brief}\n\n"
            f"【网络搜索命中】\n{web_block}\n"
        )
        system_prompt = (
            "你是售前方案工作台的文案撰写助手。用户正在「节点级对话」中，要你为画布上的单个节点撰写内容。\n"
            "硬性约束：\n"
            "1. 只为「当前节点」撰写内容，绝不要涉及其它节点。\n"
            "2. 直接输出该节点可用的成品售前文案——也就是用户采纳后能直接写进节点的内容。"
            "不要输出「建议这样写」「应该包含 X」「需要考虑 Y」之类的元指导或方法论。\n"
            "3. 不得使用「建议、应该、可以提炼、需要考虑」等空泛建议措辞；写就是了。\n"
            "4. 内容要基于【已有资料提取】和【网络搜索命中】。引用必须可追溯、不得编造；"
            "基于网络命中的内容即视为来自网络搜索，基于已有资料的视为来自用户资料。\n"
            "5. 只有当关键信息确实缺失、必须用户客观提供时，才在成品正文最末尾另起一段，"
            "以「【还需你提供】」为标题，每行一项列出具体缺失项及其用途，例如：\n"
            "   【还需你提供】\n"
            "   - 营业执照上的成立时间：用于企业简介基础信息\n"
            "   - 主营业务的具体描述：用于准确表述业务范围\n"
            "   若无缺失，不要输出该段。\n"
            "6. 若用户要的内容明显超出该节点范围（涉及多个板块），在正文开头用一句话提示"
            "「这超出本节点范围，建议在全局对话处理」，然后仍尽量给出本节点能写的部分。\n"
            f"\n{context_block}"
        )

        thinking_text = f"正在结合资料与联网搜索为节点「{node_title}」撰写内容…"
        yield f"data: {json.dumps({'type': 'thinking_delta', 'text': thinking_text}, ensure_ascii=False)}\n\n"

        llm = await get_llm_service(db)
        full_text = ""
        async for chunk in llm.generate_with_history_stream(
            messages=history,
            system_prompt=system_prompt,
            temperature=0.5,
        ):
            full_text += chunk
            yield f"data: {json.dumps({'type': 'text_delta', 'text': chunk}, ensure_ascii=False)}\n\n"

        # ── Split finished copy vs pending-questions tail, emit node_draft ──
        planning_items, pending_items = self._split_node_draft(full_text)
        draft_sources = [
            {
                "type": "web_search",
                "name": h.get("title") or h.get("domain") or "网络来源",
                "quote": (h.get("snippet") or "").strip()[:200],
            }
            for h in web_hits[:3]
        ]
        node_draft = {
            "type": "node_draft",
            "data": {
                "planning": planning_items,
                "pending_questions": pending_items,
                "sources": draft_sources,
            },
        }
        yield f"data: {json.dumps(node_draft, ensure_ascii=False)}\n\n"

        await self.save_message(
            db, conversation_id, "assistant",
            content=full_text,
            thread_id=thread_id,
            content_type="text",
            metadata={
                "intent": "node_edit",
                "node_id": node_id,
                "node_title": node_title,
                "node_draft": node_draft["data"],
            },
            auto_commit=True,
        )

    @staticmethod
    def _split_node_draft(raw: str) -> tuple:
        """Split streamed copy into (planning_items, pending_questions).

        Anything after the「【还需你提供】」marker is parsed as a bullet list
        of pending questions; the rest is the finished copy, split into
        paragraphs. Always returns two lists (never None).
        """
        marker = "【还需你提供】"
        body, pending_block = raw, ""
        if marker in raw:
            body, _, pending_block = raw.partition(marker)
        planning = [p.strip() for p in body.strip().split("\n\n") if p.strip()]
        pending = []
        for line in pending_block.strip().splitlines():
            item = re.sub(r"^[\s\-•*]+", "", line).strip()
            # drop the trailing "：用途" rationale but keep the asked item readable
            item = item.split("：", 1)[0].strip() if "：" in item else item
            if item:
                pending.append(item)
        return planning, pending

    @staticmethod
    def _fmt_slot(items: Any) -> str:
        """Render a node content slot (list or scalar) as a readable block."""
        if not items:
            return "（暂无）"
        if isinstance(items, list):
            lines = []
            for i, it in enumerate(items, 1):
                if isinstance(it, dict):
                    # Common shapes: {"text": ...} or {"title": ..., "detail": ...}
                    txt = it.get("text") or it.get("detail") or it.get("title") or ""
                    if txt:
                        lines.append(f"{i}. {txt}")
                    else:
                        lines.append(f"{i}. {it}")
                else:
                    lines.append(f"{i}. {it}")
            return "\n".join(lines)
        return str(items)

    # ─── Social greeting detection ────────────────────────────────────────

    # Short, unambiguous courtesy phrases. Hitting one means the user is just
    # being polite (not describing a task), so we reply with a fixed
    # acknowledgement and skip the LLM + workflow entirely.
    _SOCIAL_GREETINGS = {
        "你好", "您好", "嗨", "哈喽", "hi", "hello", "hey",
        "谢谢", "感谢", "thanks", "thank you",
        "再见", "拜拜", "bye",
        "在吗", "在不在",
        "好的", "ok", "okay",
    }

    def _is_social_greeting(self, message: str) -> bool:
        """Detect short courtesy phrases that shouldn't trigger any workflow."""
        normalized = message.strip().lower()
        # Only treat very short messages (≤8 chars) as greetings, so a real
        # requirement that happens to start with "你好，我是…" still flows
        # through to intent detection / auto-fill.
        if len(normalized) > 8:
            return False
        # Strip trailing punctuation for matching.
        cleaned = normalized.rstrip("。.！!？?，,~")
        return cleaned in self._SOCIAL_GREETINGS

    async def _handle_smalltalk(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
        user_message: str,
    ) -> AsyncGenerator[str, None]:
        """Courteous fixed reply for social greetings (no LLM, no workflow)."""
        msg = user_message.strip()
        if any(k in msg for k in ("你好", "您好", "嗨", "哈喽", "hi", "hello")):
            reply = "你好！我是企业知识问答助手。你可以直接提问，或上传资料后基于内部知识库获得可追溯的回答。"
        elif any(k in msg for k in ("谢谢", "感谢", "thanks")):
            reply = "不客气！如有其他问题，继续提问即可。"
        elif any(k in msg for k in ("再见", "拜拜", "bye")):
            reply = "再见！随时回来继续提问。"
        else:
            reply = "收到。请描述你的问题，或上传相关资料。"

        yield f"data: {json.dumps({'type': 'thinking_delta', 'text': '收到你的消息'}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'text_delta', 'text': reply}, ensure_ascii=False)}\n\n"

        await self.save_message(
            db, conversation_id, "assistant",
            content=reply,
            content_type="text",
            metadata={"intent": "smalltalk"},
            auto_commit=True,
        )

    # ─── First-message auto-fill (PRD §3.3 core loop) ────────────────────

    async def _handle_auto_fill(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
        user_message: str,
        project_id: str,
        force: bool = False,
    ) -> AsyncGenerator[str, None]:
        """Auto-fill the canvas: web_search → fill_canvas (PRD §3.3 / §13).

        Triggered on the first user message of a project conversation (or when
        the user explicitly asks for a full proposal). Streams thinking deltas
        throughout so the user sees live progress, then a summary reply.
        """
        from app.services.canvas_service import canvas_service
        from app.services.canvas_agent_orchestrator import canvas_agent_orchestrator

        proj_uuid = uuid.UUID(project_id)

        # Resolve the current version. The canvas workspace guarantees a V1
        # exists by the time the user chats, but guard anyway.
        try:
            version = await canvas_service.get_current_version(db, proj_uuid)
        except Exception:
            logger.exception("auto_fill: no current version for project %s", project_id)
            yield f"data: {json.dumps({'type': 'text_delta', 'text': '当前项目还没有画布版本，请先在画布页点击「生成新版本」。'}, ensure_ascii=False)}\n\n"
            return

        doc_context, doc_sources = await self._load_ref_docs_context(db, user_message)
        if doc_context:
            yield f"data: {json.dumps({'type': 'thinking_delta', 'text': f'已读取 {len(doc_sources)} 份上传资料摘要，准备融合到三大板块…'}, ensure_ascii=False)}\n\n"

        # PRESALE_DELIVERY_SPEC §11.2 — collect a per-step trace through the
        # turn, then persist ONE OperationRun at the end via a dedicated
        # session. Updating it inline would race the skill_db / mem_db commits
        # under SQLite's single-writer model; batching avoids that.
        _op_steps: List[Dict[str, Any]] = []

        # ── Stage 1: web search ──
        # Run web_search + fill_canvas in a DEDICATED session so the SSE
        # request session (held for the whole stream) isn't pinned during the
        # multi-second LLM/检索 work (Defect #3: long SSE sessions block other
        # writes under SQLite's single-writer model).
        yield f"data: {json.dumps({'type': 'thinking_delta', 'text': '正在联网搜索企业公开信息…'}, ensure_ascii=False)}\n\n"
        web_hits: List[Dict[str, Any]] = []
        try:
            from app.services.search_helper import acquire_web_context

            # web_search only reads settings (no writes), but we still use an
            # isolated session for consistency with fill_canvas below.
            from app.db.session import async_session_factory as _asf
            async with _asf() as search_db:
                web_hits, search_summary = await acquire_web_context(
                    search_db, user_message, max_results=5
                )
            status = search_summary.get("status", "ok")
            if web_hits:
                yield f"data: {json.dumps({'type': 'thinking_delta', 'text': f'已收集到 {len(web_hits)} 条公开信息，正在推理填充三大板块…'}, ensure_ascii=False)}\n\n"
            elif status in ("degraded", "failed"):
                yield f"data: {json.dumps({'type': 'thinking_delta', 'text': '联网搜索暂不可用（标记「未核实」），将基于内部知识与通用经验生成初版…'}, ensure_ascii=False)}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'thinking_delta', 'text': '未检索到相关公开信息，将基于内部知识与通用经验生成初版…'}, ensure_ascii=False)}\n\n"
        except Exception:
            # Search failure is non-fatal — degrade and continue to fill.
            logger.exception("auto_fill: web_search failed, degrading")
            yield f"data: {json.dumps({'type': 'thinking_delta', 'text': '联网搜索异常（标记「未核实」），继续基于内部知识生成…'}, ensure_ascii=False)}\n\n"
        _op_steps.append({
            "step": "web_search",
            "status": "completed" if web_hits else "skipped",
            "hit_count": len(web_hits),
        })

        # ── Stage 2: fill canvas (passes the user's free-text + web hits) ──
        # Uses a dedicated session so the canvas writes don't block the SSE
        # stream's request session (Defect #3).
        yield f"data: {json.dumps({'type': 'thinking_delta', 'text': '正在为「企业介绍 / 产品技术 / 未来责任」三大板块生成节点内容…'}, ensure_ascii=False)}\n\n"
        fill_result: Dict[str, Any] = {"success": False, "filled_count": 0, "node_ids": [], "errors": []}
        try:
            from app.db.session import async_session_factory as _asf
            async with _asf() as fill_db:
                fill_result = await canvas_agent_orchestrator.fill_canvas(
                    fill_db,
                    proj_uuid,
                    version.id,
                    web_search_results=(web_hits or None),
                    extra_context=user_message,
                    document_context=(doc_context or None),
                    document_sources=(doc_sources or None),
                )
                await fill_db.commit()
        except Exception as e:
            logger.exception("auto_fill: fill_canvas failed")
            err_text = f"画布填充失败：{e}。可在画布页点击「生成新版本」重试。"
            yield f"data: {json.dumps({'type': 'text_delta', 'text': err_text}, ensure_ascii=False)}\n\n"
            await self.save_message(
                db, conversation_id, "assistant",
                content=err_text,
                content_type="text",
                metadata={"intent": "auto_fill", "project_id": project_id, "error": str(e)},
                auto_commit=True,
            )
            # Persist a failed OperationRun so排障 has the same trace as the
            # success path (PRESALE_DELIVERY_SPEC §11.2 — previous early return
            # wrote nothing, leaving the failure invisible to the run table).
            _op_steps.append({
                "step": "canvas_fill",
                "status": "failed",
                "error": str(e),
            })
            _op_steps.append({"step": "persist_message", "status": "completed"})
            await self._persist_op_run(
                proj_uuid, conversation_id, _op_steps, status="failed", error=str(e)
            )
            return
        _op_steps.append({
            "step": "canvas_fill",
            "status": "completed" if fill_result.get("success") else "failed",
            "filled_count": fill_result.get("filled_count", 0),
        })

        # 可见化:从 fill_canvas 写回结果派生 Proposal,让用户看到填了什么(所见即所写)
        try:
            proposal = await canvas_research_service.build_fill_proposal_from_canvas(
                db, proj_uuid
            )
            if proposal.get("boards"):
                yield f"data: {json.dumps({'type': 'canvas_fill_proposal', 'data': proposal}, ensure_ascii=False)}\n\n"
        except Exception:
            # 派生失败不阻断主流程(fill 已成功);记录日志便于排查,与下方 Brief 块一致。
            logger.exception("auto_fill: derive canvas_fill_proposal failed; continuing")

        # 设计 Brief:基于已填画布(企业画像)+ 项目上下文,调 proposal_generation 生成策划案。
        # 复用既有 proposal_section block(与 _handle_skill_execution:865 一致,data = skill output 整体),
        # 不新增 design_brief block,前端既有 proposal_section 渲染不变。
        # 镜像 _handle_skill_execution(765-798):独立 session + SkillRegistry.get_instance() +
        # SkillContext(user_id=None) + run_with_react,避免 SQLite 单写者死锁。
        # Brief 失败不阻断主流程(画布已填、可见化已 emit)。
        _auto_fill_gen_output_id: Optional[str] = None
        try:
            from app.skills.base import SkillContext
            from app.skills.registry import SkillRegistry
            from app.skills.runner import SkillRunner
            from app.db.session import async_session_factory as _asf
            from app.services.embedding_service import get_embedding_service
            from app.services.image_service import get_image_service

            # 把已填画布序列化成企业画像文本(重新派生,解耦上面 proposal 变量作用域)
            brief_proposal = await canvas_research_service.build_fill_proposal_from_canvas(
                db, proj_uuid
            )
            profile_text = _serialize_proposal_to_profile(brief_proposal)
            async with _asf() as skill_db:
                skill_ctx = SkillContext(
                    project_id=str(proj_uuid),   # SkillContext.project_id: Optional[str]
                    user_id=None,                # _handle_auto_fill 无 user_id 入参
                    db=skill_db,
                    llm_service=await get_llm_service(skill_db),
                    embedding_service=await get_embedding_service(skill_db),
                    image_service=await get_image_service(skill_db),
                )
                registry = SkillRegistry.get_instance()
                runner = SkillRunner(registry)
                skill_result = await runner.run_with_react(
                    "proposal_generation",
                    {
                        "project_id": str(proj_uuid),
                        "requirement_text": user_message or "",
                        "context_pack": profile_text,
                    },
                    skill_ctx,
                )
                # run_with_react 返回 dict(runner.py:97-118),output 在 "output" 键下
                # —— 不能用 getattr(dict, "output")(恒为 None)。镜像 _handle_skill_execution:860。
                skill_output = skill_result.get("output", {}) or {}

                # PRESALE_DELIVERY_SPEC §6.1 / §9 — the proposal (设计 Brief)
                # must be persisted as a GenerationOutput so the章节审核 / 导出
                # 门控 / Proposal 编辑器都能定位到它。proposal_generation 在 DB
                # 模式下已经写了自己的 GenerationOutput(含 sections_meta)并返回
                # output_id;优先复用那一行,避免重复落库 + sections_meta 丢失。
                # 仅当 skill 没有持久化(chat 模式 / 旧路径)才在此补建。
                #
                # 重要:这段 commit 必须在 `async with skill_db` 之内执行 —— 否则
                # async with 退出会关闭 session 并回滚 skill 的 flush,导致 Brief
                # 落不进库(Proposal 编辑器 / 导出门控都找不到)。
                try:
                    skill_output_id = skill_output.get("output_id")
                    if skill_output_id:
                        _auto_fill_gen_output_id = str(skill_output_id)
                    else:
                        from app.models.generation import (
                            GenerationOutput,
                            GenerationTask,
                        )

                        gen_task = GenerationTask(
                            project_id=proj_uuid,
                            type="proposal_generation",
                            status="completed",
                            model_used=skill_ctx.llm_service.__class__.__name__,
                            completed_at=datetime.now(timezone.utc),
                        )
                        skill_db.add(gen_task)
                        await skill_db.flush()

                        gen_output = GenerationOutput(
                            task_id=gen_task.id,
                            content_type="application/json",
                            content=json.dumps(skill_output, ensure_ascii=False),
                            used_cases=list(skill_output.get("used_cases") or []),
                            used_documents=list(
                                skill_output.get("used_documents") or []
                            ),
                            used_chunks=list(skill_output.get("used_chunks") or []),
                            used_external_sources=list(
                                skill_output.get("used_external_sources") or []
                            ),
                            sections_meta=list(
                                skill_output.get("sections_meta") or []
                            ),
                        )
                        skill_db.add(gen_output)
                        _auto_fill_gen_output_id = str(gen_output.id)
                    # Commit in BOTH branches: the DB-mode skill already flushed
                    # its GenerationTask/Output into skill_db but never commits
                    # — without this commit those rows roll back when the
                    # session closes and the editor / export gate can't find
                    # the Brief.
                    #
                    # PRESALE_DELIVERY_SPEC §4.2 / F5: a successful auto-fill that
                    # produced a Brief advances the project lifecycle to
                    # `proposal_generated`. The skill already stamps
                    # `proposal_draft` (legacy); normalise to the canonical value
                    # so the workspace status chip reads correctly.
                    if _auto_fill_gen_output_id:
                        from app.models.project import Project as _Project

                        proj_row = await skill_db.get(_Project, proj_uuid)
                        if proj_row is not None:
                            proj_row.status = "proposal_generated"
                    await skill_db.commit()
                except Exception:
                    logger.exception(
                        "auto_fill: persist proposal GenerationOutput failed; continuing"
                    )
                    _auto_fill_gen_output_id = None
            # Emit the proposal_section block AFTER the skill_db transaction is
            # committed — the SSE event is the user-facing signal that the Brief
            # is ready; emitting earlier would race the editor's GET.
            if skill_output:
                yield f"data: {json.dumps({'type': 'proposal_section', 'data': skill_output}, ensure_ascii=False)}\n\n"
            if not skill_output:
                _auto_fill_gen_output_id = None
        except Exception as e:
            logger.exception("auto_fill: brief generation failed; continuing")
            _auto_fill_gen_output_id = None
            _op_steps.append({
                "step": "skill_execute",
                "status": "failed",
                "error": str(e),
            })
        else:
            _op_steps.append({
                "step": "skill_execute",
                "status": "completed" if _auto_fill_gen_output_id else "skipped",
                "output_id": _auto_fill_gen_output_id,
            })

        # ── Stage 2.5: persist project + conversation memory ──
        # PRESALE_DELIVERY_SPEC §7.2 — write the canvas_digest (so follow-up
        # turns answer "刚才填充的企业主营业务是什么?" without re-searching) and the
        # last_web_hits conversation state (so a fact question can cite the
        # prior search). Uses a dedicated session so the SSE request session
        # isn't pinned; memory failures never abort the main flow (the Brief
        # is already emitted).
        try:
            from app.db.session import async_session_factory as _asf
            from app.services.project_memory_service import (
                project_memory_service,
            )

            async with _asf() as mem_db:
                digest = await project_memory_service.build_canvas_digest(
                    mem_db, proj_uuid
                )
                # Attach the just-collected web hits to the digest so the LLM
                # has the one-turn-ago search context inline.
                digest["last_web_search"] = {
                    "hits": web_hits or [],
                    "summary": search_summary,
                } if web_hits else None
                await project_memory_service.upsert_project_memory(
                    mem_db, proj_uuid, "canvas_digest", digest
                )
                if web_hits:
                    await project_memory_service.upsert_conversation_state(
                        mem_db,
                        conversation_id,
                        "last_web_hits",
                        {"hits": web_hits, "summary": search_summary},
                    )
                await mem_db.commit()
        except Exception:
            logger.exception("auto_fill: write project memory failed; continuing")
        _op_steps.append({"step": "memory_write", "status": "completed"})

        # ── Stage 3: summary reply ──
        filled = fill_result.get("filled_count", 0)
        errors = fill_result.get("errors") or []
        node_ids = fill_result.get("node_ids") or []
        web_note = "（含网络搜索参考）" if web_hits else "（基于内部知识）"

        if fill_result.get("success") and filled > 0:
            summary = (
                f"已为该企业填充画布三大板块，共 {filled} 个节点{web_note}。\n"
                "- 企业介绍：企业简介、规模、发展历程、荣誉资质、团队能力、核心价值\n"
                "- 产品 / 技术 / 应用场景：产品体系、技术能力、应用场景、典型案例、解决方案\n"
                "- 未来 / 社会责任：未来布局、发展战略、社会责任、可持续发展、品牌愿景\n\n"
                "右侧画布已同步更新。点击任一节点可进入「节点对话」修改，或在下方继续追问。"
            )
        elif errors:
            summary = f"画布填充部分失败：{'; '.join(errors[:3])}。可在画布页点击「生成新版本」重试。"
        else:
            summary = "画布节点已是最新状态，无需重新填充。点击节点可进入「节点对话」修改。"

        yield f"data: {json.dumps({'type': 'text_delta', 'text': summary}, ensure_ascii=False)}\n\n"

        await self.save_message(
            db, conversation_id, "assistant",
            content=summary,
            content_type="text",
            metadata={
                "intent": "auto_fill",
                "project_id": project_id,
                "version_id": str(version.id),
                "filled_count": filled,
                "web_search_used": bool(web_hits),
                "node_ids": node_ids,
                # Link the assistant turn to the persisted Brief so the frontend
                # can open the Proposal editor / trigger export directly from
                # this message (PRESALE_DELIVERY_SPEC §6.1).
                "generation_output_id": _auto_fill_gen_output_id,
            },
            auto_commit=True,
        )
        _op_steps.append({"step": "persist_message", "status": "completed"})

        # Close the OperationRun — completed unless fill_canvas itself failed.
        # Delegated to a helper so both the success path and the early-return
        # failure path (canvas_fill exception above) write a run.
        run_status = "completed" if fill_result.get("success") else "failed"
        await self._persist_op_run(
            proj_uuid, conversation_id, _op_steps, status=run_status
        )

    async def _persist_op_run(
        self,
        project_id: uuid.UUID,
        conversation_id: uuid.UUID,
        steps: List[Dict[str, Any]],
        status: str = "completed",
        error: Optional[str] = None,
    ) -> None:
        """Persist ONE OperationRun (start + steps + finish) in a dedicated session.

        PRESALE_DELIVERY_SPEC §11.2 — write the whole run in one go so it
        doesn't race the skill_db / mem_db commits under SQLite's
        single-writer model. Soft-fail: a persistence failure only logs (the
        user-facing turn already completed). Shared by the auto-fill success
        path and the fill_canvas-failed early return.
        """
        try:
            from app.db.session import async_session_factory as _asf
            from app.services.operation_run_service import operation_run_service

            async with _asf() as op_db:
                op_run = await operation_run_service.start(
                    op_db, project_id, "auto_fill", conversation_id=conversation_id
                )
                for step in steps:
                    # ``error`` is a first-class field on add_step (top-level on
                    # the step entry); everything else lands in ``extra``.
                    step_error = step.get("error")
                    extra = {
                        k: v
                        for k, v in step.items()
                        if k not in ("step", "status", "error")
                    }
                    await operation_run_service.add_step(
                        op_db, op_run, step["step"], step["status"],
                        error=step_error,
                        extra=extra or None,
                    )
                await operation_run_service.finish(
                    op_db, op_run, status=status, error=error
                )
                await op_db.commit()
        except Exception:
            logger.exception("auto_fill: persist OperationRun failed; continuing")
