"""Conversation orchestration service — manages chat flow and skill routing."""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, Message
from app.services.intent_service import IntentDetector, IntentResult
from app.services.llm_service import get_llm_service

logger = logging.getLogger(__name__)

# System prompt for conversational mode
_CONVERSATION_SYSTEM_PROMPT = """你是 3D 展示幕墙 AI 专家系统的助手。

你的职责：
1. 帮助用户理解项目需求和技术参数
2. 解释企业解析、策划案、视觉方案的细节
3. 根据上下文建议下一步操作
4. 回答关于 3D 展示幕墙、裸眼 3D、LED 媒体立面的问题

重要规则：
- 如果缺少关键信息（屏幕尺寸、预算、工期等），明确标注「需进一步确认」
- 不要编造案例、报价、屏幕参数或工期
- 推荐用户使用技能卡片执行专业任务（企业解析、策划案生成、视觉生成等）
- 回答要专业、简洁、有建设性"""


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

    async def list_conversations(
        self,
        db: AsyncSession,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Conversation]:
        """List conversations for the sidebar, newest first."""
        stmt = select(Conversation).order_by(Conversation.updated_at.desc())
        if status:
            stmt = stmt.where(Conversation.status == status)
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
        content_type: str = "text",
        rich_content: Optional[Dict[str, Any]] = None,
        skill_execution_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        auto_commit: bool = False,
    ) -> Message:
        """Save a message to the database.

        If auto_commit=True, commits immediately to release DB locks (needed for SSE).
        """
        msg = Message(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
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

    def build_message_history(
        self, messages: List[Message]
    ) -> List[Dict[str, str]]:
        """Convert DB messages to the format LLM expects."""
        history: List[Dict[str, str]] = []
        for msg in messages:
            if msg.role in ("user", "assistant"):
                history.append({"role": msg.role, "content": msg.content})
        return history

    async def process_message_stream(
        self,
        db: AsyncSession,
        conversation_id: str,
        user_message: str,
    ) -> AsyncGenerator[str, None]:
        """Process a user message and yield SSE chunks.

        Flow:
        1. Save user message (with immediate commit to release DB lock)
        2. Load history
        3. Detect intent
        4. Route to skill or conversational LLM
        5. Stream response
        6. Save assistant message
        """
        conv_uuid = uuid.UUID(conversation_id)

        # 1. Save user message and commit immediately to release DB lock
        await self.save_message(db, conv_uuid, "user", user_message, auto_commit=True)

        # 2. Load history (after commit, so the new message is visible)
        messages = await self.get_history(db, conv_uuid)
        history = self.build_message_history(messages)

        # 3. Detect intent
        intent: IntentResult = await self._intent_detector.detect(
            user_message, history
        )

        logger.info(
            "Intent detected: %s (skill=%s, confidence=%.2f)",
            intent.intent,
            intent.skill_id,
            intent.confidence,
        )

        # 4. Route based on intent
        if intent.intent == "run_skill" and intent.skill_id:
            async for chunk in self._handle_skill_execution(
                db, conv_uuid, intent, history
            ):
                yield chunk
        elif intent.intent == "visual_concept":
            async for chunk in self._handle_visual_concept(
                db, conv_uuid, user_message, intent
            ):
                yield chunk
        else:
            async for chunk in self._handle_conversational(
                db, conv_uuid, user_message, history
            ):
                yield chunk

        # Final done event
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    async def _handle_skill_execution(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
        intent: IntentResult,
        history: List[Dict[str, str]],
    ) -> AsyncGenerator[str, None]:
        """Handle a skill execution intent."""
        skill_id = intent.skill_id

        # Notify frontend that a skill is starting
        yield f"data: {json.dumps({'type': 'text_delta', 'text': f'正在执行「{skill_id}」技能...\\n\\n'})}\n\n"

        try:
            from app.skills.base import SkillContext
            from app.skills.registry import SkillRegistry
            from app.skills.runner import SkillRunner
            from app.services.embedding_service import get_embedding_service
            from app.services.image_service import get_image_service

            registry = SkillRegistry.get_instance()
            if not registry.has(skill_id):
                yield f"data: {json.dumps({'type': 'text_delta', 'text': f'抱歉，技能「{skill_id}」暂不可用。'})}\n\n"
                await self.save_message(
                    db, conversation_id, "assistant",
                    f"抱歉，技能「{skill_id}」暂不可用。",
                    auto_commit=True,
                )
                return

            # Get conversation to find project_id
            conv = await self.get_conversation_detail(db, str(conversation_id))
            project_id = str(conv.project_id) if conv and conv.project_id else None

            # Build input data from intent + history context
            input_data = {**intent.input_data}
            if project_id:
                input_data["project_id"] = project_id

            context = SkillContext(
                project_id=project_id,
                user_id=None,
                db=db,
                llm_service=get_llm_service(),
                embedding_service=get_embedding_service(),
                image_service=get_image_service(),
            )

            runner = SkillRunner(registry)
            result = await runner.run(skill_id, input_data, context)

            if result.get("success"):
                output = result.get("output", {})

                # Create rich content blocks
                blocks: Dict[str, Any] = {
                    "blocks": [
                        {"type": "text", "content": f"✅ 技能「{skill_id}」执行完成"},
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

                summary = f"✅ 技能「{skill_id}」执行完成，耗时 {result.get('duration_ms', 0)}ms"
                yield f"data: {json.dumps({'type': 'text_delta', 'text': summary})}\n\n"

                # Stream content block events
                last_block = blocks["blocks"][-1]
                yield f"data: {json.dumps({'type': 'content_block_start', 'data': {'block_type': last_block['type']}})}\n\n"
                yield f"data: {json.dumps({'type': 'content_block_data', 'data': last_block})}\n\n"
                yield f"data: {json.dumps({'type': 'content_block_end'})}\n\n"

                # Save assistant message
                await self.save_message(
                    db, conversation_id, "assistant",
                    content=summary,
                    content_type="rich",
                    rich_content=blocks,
                    skill_execution_id=result.get("execution_id"),
                    metadata={"intent": "run_skill", "skill_id": skill_id},
                    auto_commit=True,
                )
            else:
                error_msg = result.get("error", "未知错误")
                yield f"data: {json.dumps({'type': 'text_delta', 'text': f'❌ 技能执行失败：{error_msg}'})}\n\n"
                await self.save_message(
                    db, conversation_id, "assistant",
                    content=f"技能「{skill_id}」执行失败：{error_msg}",
                    metadata={"intent": "run_skill", "skill_id": skill_id, "error": error_msg},
                    auto_commit=True,
                )

        except Exception as e:
            logger.exception("Skill execution error in conversation")
            yield f"data: {json.dumps({'type': 'text_delta', 'text': f'执行出错：{str(e)}'})}\n\n"
            try:
                await self.save_message(
                    db, conversation_id, "assistant",
                    content=f"执行出错：{str(e)}",
                    metadata={"intent": "run_skill", "skill_id": skill_id, "error": str(e)},
                    auto_commit=True,
                )
            except Exception:
                logger.exception("Failed to save error message")

    def _load_visual_concept_ctx(self, messages: List[Message]) -> "VisualConceptContext":
        """从消息历史中恢复 VisualConceptContext。"""
        from app.agents.visual_concept import VisualConceptContext

        for msg in reversed(messages):
            if msg.metadata_json and "state" in msg.metadata_json:
                return VisualConceptContext.from_dict(msg.metadata_json)
        return VisualConceptContext()

    async def _handle_visual_concept(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
        user_message: str,
        intent: IntentResult,
    ) -> AsyncGenerator[str, None]:
        """处理视觉概念图生成请求。"""
        from app.agents.visual_concept import VisualConceptAgent, VisualConceptContext

        history = await self.get_history(db, conversation_id)
        ctx = self._load_visual_concept_ctx(history)

        if ctx.state == "COLLECTING" and not ctx.requirement.raw_input:
            ctx.requirement.raw_input = user_message

        agent = VisualConceptAgent()
        async for chunk in agent.handle_message(user_message, ctx, db):
            yield chunk

        # Save context to assistant message metadata
        await self.save_message(
            db=db,
            conversation_id=conversation_id,
            role="assistant",
            content="[visual concept context saved]",
            content_type="text",
            metadata=ctx.to_dict(),
            auto_commit=True,
        )

    async def _handle_conversational(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
        user_message: str,
        history: List[Dict[str, str]],
    ) -> AsyncGenerator[str, None]:
        """Handle conversational intent with streaming LLM response."""
        llm = get_llm_service()
        full_text = ""

        async for chunk in llm.generate_with_history_stream(
            messages=history,
            system_prompt=_CONVERSATION_SYSTEM_PROMPT,
            temperature=0.7,
        ):
            full_text += chunk
            yield f"data: {json.dumps({'type': 'text_delta', 'text': chunk})}\n\n"

        # Save complete assistant message
        await self.save_message(
            db, conversation_id, "assistant",
            content=full_text,
            content_type="text",
            metadata={"intent": "conversational"},
            auto_commit=True,
        )
