"""Conversation orchestration service — manages chat flow and skill routing."""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.prompts import GLOBAL_CAPABILITY_CONSTRAINT
from app.models.conversation import Conversation, Message
from app.services.intent_service import IntentDetector, IntentResult
from app.services.llm_service import get_llm_service

logger = logging.getLogger(__name__)

# System prompt for conversational mode
_CONVERSATION_SYSTEM_PROMPT = """你是花生ONE 展厅+文旅 AI 专家系统的助手。

你的职责：
1. 帮助用户理解项目需求和技术参数
2. 解释企业解析、策划案、视觉方案的细节
3. 根据上下文建议下一步操作（仅限系统已注册的 Skill）
4. 回答关于以下领域的问题：
   - 3D 展示幕墙、裸眼 3D、LED 媒体立面
   - 展厅设计与展陈规划（企业展厅、博物馆、规划馆、科技馆）
   - 文旅项目策划（文旅夜游、沉浸式体验、光影秀）
   - 多媒体展项设计（互动装置、数字沙盘、AR/VR体验）

重要规则：
- 如果缺少关键信息（场地面积、屏幕尺寸、预算、工期等），明确标注「需进一步确认」
- 不要编造案例、报价、屏幕参数或工期
- 推荐用户使用技能卡片执行专业任务（企业解析、策划案生成、视觉生成等）
- 回答要专业、简洁、有建设性""" + GLOBAL_CAPABILITY_CONSTRAINT


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
        """List conversations for the sidebar, newest first.

        By default only active conversations are returned.
        Pass status explicitly to include archived or other statuses.
        """
        stmt = select(Conversation).order_by(Conversation.updated_at.desc())
        if status:
            stmt = stmt.where(Conversation.status == status)
        else:
            stmt = stmt.where(Conversation.status != "archived")
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

        try:
            # 1. Save user message and commit immediately to release DB lock
            await self.save_message(db, conv_uuid, "user", user_message, auto_commit=True)

            # 2. Load history (after commit, so the new message is visible)
            messages = await self.get_history(db, conv_uuid)
            history = self.build_message_history(messages)

            # 2.5 Check for active ProposalAgent context (resume multi-turn)
            proposal_ctx = self._load_proposal_ctx(messages)
            if proposal_ctx.state not in ("COMPLETED",) and proposal_ctx.requirement.raw_input:
                logger.info("Resuming ProposalAgent at state %s", proposal_ctx.state)
                async for chunk in self._handle_proposal_agent(
                    db, conv_uuid, user_message
                ):
                    yield chunk
                return

            # 2.6 Check for paused execution plan that needs resuming
            execution_plan = self._load_execution_plan(messages)
            if execution_plan and execution_plan.status == "paused":
                logger.info("Resuming paused execution plan at step %d", execution_plan.current_step_index)
                async for chunk in self._handle_plan_resume(
                    db, conv_uuid, user_message, execution_plan, history
                ):
                    yield chunk
                return

            # 3. Detect intent
            intent: IntentResult = await self._intent_detector.detect(
                user_message, history, db=db
            )

            logger.info(
                "Intent detected: %s (skill=%s, confidence=%.2f)",
                intent.intent,
                intent.skill_id,
                intent.confidence,
            )

            # 4. Route based on intent
            if intent.intent == "sop_pipeline" and intent.skill_id is None:
                # Route full-flow requests to ProposalAgent
                async for chunk in self._handle_proposal_agent(
                    db, conv_uuid, user_message, intent
                ):
                    yield chunk
            elif intent.intent == "run_skill" and intent.skill_id:
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
                    "请先提供企业的基本信息，我将为您进行专业解析。\n\n"
                    "至少需要：\n"
                    "1. **企业名称**（必填）\n\n"
                    "补充以下信息可获得更精准的分析：\n"
                    "- 所属行业\n"
                    "- 主要产品或服务\n"
                    "- 品牌关键词或调性\n"
                    "- 本次项目目标\n\n"
                    "您可以直接输入，例如：*「华为，科技行业，主要做5G通信设备和手机」*"
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
        """从消息历史中恢复 VisualConceptContext。"""
        from app.agents.visual_concept import VisualConceptContext

        for msg in reversed(messages):
            if msg.metadata_json and "state" in msg.metadata_json:
                return VisualConceptContext.from_dict(msg.metadata_json)
        return VisualConceptContext()

    def _load_proposal_ctx(self, messages: List[Message]) -> "ProposalContext":
        """从消息历史中恢复 ProposalContext。"""
        from app.agents.proposal import ProposalContext

        for msg in reversed(messages):
            if msg.metadata_json and "proposal_state" in msg.metadata_json:
                return ProposalContext.from_dict(msg.metadata_json)
        return ProposalContext()

    def _load_execution_plan(self, messages: List[Message]) -> Optional["ExecutionPlan"]:
        """Recover ExecutionPlan from the most recent assistant message metadata."""
        from app.services.execution_plan import ExecutionPlan
        for msg in reversed(messages):
            if msg.metadata_json and "execution_plan" in msg.metadata_json:
                try:
                    return ExecutionPlan.from_dict(msg.metadata_json)
                except Exception:
                    logger.warning("Failed to parse ExecutionPlan from metadata")
        return None

    # ── Execution Plan (dynamic pipeline) ──────────────────────────

    async def _handle_plan_execution(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
        user_message: str,
        intent: IntentResult,
        history: List[Dict[str, str]],
    ) -> AsyncGenerator[str, None]:
        """Launch a dynamic execution plan based on detected business domain."""
        from app.services.planner import create_plan, default_sop_loader

        # Quick pre-check: does the user message contain any entity info?
        has_entity = len(user_message) > 10
        if not has_entity:
            prompt_text = (
                "请提供以下信息，我将为您启动完整的方案设计流程：\n\n"
                "1. **企业/景区名称**（必填）\n"
                "2. 项目类型（展厅/文旅/幕墙/互动装置）\n"
                "3. 项目需求简述\n\n"
                "例如：*「给华为设计一套企业展厅方案，用于展示5G技术成果」*\n"
                "或：*「为某景区设计文旅夜游方案，包含灯光秀和沉浸式体验」*"
            )
            yield f"data: {json.dumps({'type': 'text_delta', 'text': prompt_text})}\n\n"
            await self.save_message(
                db, conversation_id, "assistant",
                content=prompt_text, content_type="text",
                auto_commit=True,
            )
            return

        # Create plan
        company_name = self._extract_company_name(user_message)
        plan = await create_plan(
            user_message=user_message,
            company_name=company_name,
            db=db,
            sop_loader=default_sop_loader,
        )

        # Execute the plan
        async for chunk in self._execute_plan(db, conversation_id, plan):
            yield chunk

    async def _handle_plan_resume(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
        user_message: str,
        plan: "ExecutionPlan",
        history: List[Dict[str, str]],
    ) -> AsyncGenerator[str, None]:
        """Resume a paused execution plan based on user action."""
        from app.services.intent_service import IntentDetector

        action = IntentDetector.classify_pipeline_action(user_message)

        if action == "restart":
            from app.services.planner import create_plan, default_sop_loader
            plan = await create_plan(
                user_message=plan.context.get("user_message", ""),
                company_name=plan.context.get("company_name", ""),
                db=db,
                sop_loader=default_sop_loader,
            )
            confirm_text = "🔄 已重置方案流程，重新开始...\n\n"
            yield f"data: {json.dumps({'type': 'text_delta', 'text': confirm_text})}\n\n"
            async for chunk in self._execute_plan(db, conversation_id, plan):
                yield chunk
            return

        if action == "confirm":
            step = plan.current_step()
            step_name = step.name if step else "当前阶段"
            confirm_text = f"✅ **{step_name}** 已确认，进入下一阶段...\n\n"
            yield f"data: {json.dumps({'type': 'text_delta', 'text': confirm_text})}\n\n"

            plan.status = "running"
            plan.current_step_index += 1
            async for chunk in self._execute_plan(db, conversation_id, plan):
                yield chunk
            return

        # action == "modify"
        plan.context["modify_feedback"] = user_message
        modify_text = "📝 收到修改意见，正在重新生成...\n\n"
        yield f"data: {json.dumps({'type': 'text_delta', 'text': modify_text})}\n\n"
        plan.status = "running"
        async for chunk in self._execute_plan(db, conversation_id, plan):
            yield chunk

    async def _execute_plan(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
        plan: "ExecutionPlan",
    ) -> AsyncGenerator[str, None]:
        """Execute an ExecutionPlan using the Plan Executor."""
        import time

        from app.skills.base import SkillContext
        from app.skills.registry import SkillRegistry
        from app.services.embedding_service import get_embedding_service
        from app.services.execution_plan import ExecutionPlan
        from app.services.image_service import get_image_service
        from app.services.plan_executor import execute_plan as run_plan_steps

        # Get project_id from conversation
        conv = await self.get_conversation_detail(db, str(conversation_id))
        project_id = str(conv.project_id) if conv and conv.project_id else None

        registry = SkillRegistry.get_instance()
        if not registry.list_skills():
            registry.auto_register()

        from app.db.session import async_session_factory

        all_output: Dict[str, Any] = {}
        blocks: List[Dict[str, Any]] = []
        content_parts: List[str] = []

        async with async_session_factory() as skill_db:
            context = SkillContext(
                project_id=project_id,
                user_id=None,
                db=skill_db,
                llm_service=await get_llm_service(skill_db),
                embedding_service=await get_embedding_service(skill_db),
                image_service=await get_image_service(skill_db),
            )

            # Inject project_id and company_id into plan context
            if project_id:
                plan.context["project_id"] = project_id

            # Run the plan executor
            async for event in run_plan_steps(plan, context, registry):
                event_type = event.get("type", "")
                event_data = event.get("data", {})

                if event_type == "plan_created":
                    # Stream plan overview
                    yield f"data: {json.dumps({'type': 'text_delta', 'text': '📋 方案流程已规划，开始执行...\n\n'})}\n\n"
                    # Send plan info as a content block for frontend rendering
                    yield f"data: {json.dumps({'type': 'content_block_start', 'data': {'block_type': 'plan_progress'}})}\n\n"
                    yield f"data: {json.dumps({'type': 'content_block_data', 'data': event})}\n\n"
                    yield f"data: {json.dumps({'type': 'content_block_end'})}\n\n"

                elif event_type == "plan_step_start":
                    step_name = event_data.get("name", "")
                    progress_text = f"🔄 **{step_name}** 阶段开始执行...\n\n"
                    yield f"data: {json.dumps({'type': 'text_delta', 'text': progress_text})}\n\n"

                elif event_type == "plan_step_complete":
                    step_name = event_data.get("name", "")
                    step_skill_id = event_data.get("skill_id", "")
                    duration = event_data.get("duration", 0)
                    output_summary = event_data.get("output_summary", {})

                    # Build stage summary
                    summary = f"✅ **{step_name}** 完成"
                    if duration >= 60:
                        summary += f"\n⏱ 耗时 {duration // 60} 分 {duration % 60} 秒"
                    else:
                        summary += f"\n⏱ 耗时 {duration} 秒"

                    # Add metrics
                    for key, val in output_summary.items():
                        if key == "missing_count" and val:
                            summary += f"\n⚠️ {val} 项待确认"
                        elif key == "sections_count" and val:
                            summary += f"\n📋 共 {val} 个章节"
                        elif key == "images_count" and val:
                            summary += f"\n🖼 生成 {val} 张效果图"

                    content_parts.append(summary)
                    yield f"data: {json.dumps({'type': 'text_delta', 'text': summary + '\n\n'})}\n\n"

                    # Add skill-specific content blocks
                    step_output = plan.step_outputs.get(step_skill_id, {})
                    if step_skill_id == "company_analysis" and step_output:
                        blocks.append({"type": "company_analysis_card", "data": step_output})
                    elif step_skill_id == "proposal_generation" and step_output:
                        blocks.append({"type": "proposal_section", "data": {
                            "content_type": "text/markdown",
                            "content": step_output.get("content", ""),
                            "missing_info": step_output.get("missing_info", []),
                            # Citations — §3.3 RAG traceability (mirrors the Agent path)
                            "used_cases": step_output.get("used_cases", []),
                            "used_documents": step_output.get("used_documents", []),
                            "used_chunks": step_output.get("used_chunks", []),
                        }})
                    elif step_skill_id in ("visual_prompt", "image_generation") and step_output:
                        blocks.append({"type": "visual_result", "data": step_output})
                    elif step_skill_id == "export" and step_output:
                        blocks.append({"type": "artifact", "data": step_output})

                    # Add stage_summary block
                    blocks.append({
                        "type": "stage_summary",
                        "data": {
                            "stage": step_skill_id,
                            "status": "completed",
                            "duration": duration,
                            "metrics": output_summary,
                        },
                    })

                elif event_type == "plan_step_failed":
                    step_name = event_data.get("name", "")
                    error_msg = event_data.get("error", "执行失败")
                    error_text = f"❌ **{step_name}** 执行失败：{error_msg}\n\n"
                    content_parts.append(error_text)
                    yield f"data: {json.dumps({'type': 'text_delta', 'text': error_text})}\n\n"

                elif event_type == "plan_paused":
                    step_skill_id = event_data.get("skill_id", "")
                    step_name = event_data.get("name", "")

                    # Add action buttons for pause
                    if step_skill_id == "company_analysis":
                        blocks.append({
                            "type": "action_buttons",
                            "data": {"buttons": [
                                {"label": "✓ 确认企业画像，继续", "value": "确认继续", "action": "quick_reply"},
                                {"label": "↻ 重新生成", "value": "重新生成企业解析", "action": "quick_reply"},
                            ]},
                        })
                    elif step_skill_id == "proposal_generation":
                        blocks.append({
                            "type": "action_buttons",
                            "data": {"buttons": [
                                {"label": "✓ 确认策划案，继续", "value": "确认继续", "action": "quick_reply"},
                                {"label": "✎ 我有修改意见", "value": "修改策划案", "action": "quick_reply"},
                            ]},
                        })
                    elif step_skill_id == "visual_prompt":
                        blocks.append({
                            "type": "action_buttons",
                            "data": {"buttons": [
                                {"label": "使用方案 A", "value": "使用第一张效果图", "action": "quick_reply"},
                                {"label": "使用方案 B", "value": "使用第二张效果图", "action": "quick_reply"},
                                {"label": "两个都用", "value": "两张都可以继续", "action": "quick_reply"},
                            ]},
                        })

                elif event_type == "plan_completed":
                    completed = event_data.get("completed_steps", 0)
                    done_text = f"\n🎉 方案流程已全部完成！共完成 {completed} 个阶段。"
                    content_parts.append(done_text)
                    yield f"data: {json.dumps({'type': 'text_delta', 'text': done_text})}\n\n"

            # Commit skill execution records
            try:
                await skill_db.commit()
            except Exception:
                await skill_db.rollback()

        # Stream all content blocks
        for block in blocks:
            yield f"data: {json.dumps({'type': 'content_block_start', 'data': {'block_type': block['type']}})}\n\n"
            yield f"data: {json.dumps({'type': 'content_block_data', 'data': block})}\n\n"
            yield f"data: {json.dumps({'type': 'content_block_end'})}\n\n"

        # Save assistant message with plan state
        content_text = "\n".join(content_parts) if content_parts else "方案流程执行完成。"
        rich_content = {"blocks": blocks} if blocks else None

        await self.save_message(
            db, conversation_id, "assistant",
            content=content_text,
            content_type="rich" if rich_content else "text",
            rich_content=rich_content,
            metadata=plan.to_dict(),
            auto_commit=True,
        )

    @staticmethod
    def _extract_company_name(message: str) -> str:
        """Extract likely company name from user message. Simple heuristic for MVP."""
        import re
        patterns = [
            r"给\s*(\S{2,10}?(?:公司|集团|科技|股份|有限))",
            r"为\s*(\S{2,10}?(?:公司|集团|科技|股份|有限))",
            r"帮\s*(\S{2,10}?(?:公司|集团|科技|股份|有限))",
            r"(\S{2,8})的.*(?:方案|幕墙|展示)",
        ]
        for pat in patterns:
            m = re.search(pat, message)
            if m:
                return m.group(1)
        return ""

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

        # Load project_id from conversation for context auto-fill
        conv = await self.get_conversation_detail(db, str(conversation_id))
        project_id = str(conv.project_id) if conv and conv.project_id else None

        if ctx.state == "COLLECTING" and not ctx.requirement.raw_input:
            ctx.requirement.raw_input = user_message

        agent = VisualConceptAgent()
        async for chunk in agent.handle_message(user_message, ctx, db, project_id=project_id):
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

    async def _handle_proposal_agent(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
        user_message: str,
        intent: Optional[IntentResult] = None,
    ) -> AsyncGenerator[str, None]:
        """处理策划案专家 Agent 请求。"""
        from app.agents.proposal import ProposalAgent, ProposalContext

        history = await self.get_history(db, conversation_id)
        ctx = self._load_proposal_ctx(history)
        initial_state = ctx.state  # capture to detect fresh REVIEWING → COMPLETED

        # Load project_id from conversation for context auto-fill
        conv = await self.get_conversation_detail(db, str(conversation_id))
        project_id = str(conv.project_id) if conv and conv.project_id else None

        if ctx.state == "COLLECTING" and not ctx.requirement.raw_input:
            ctx.requirement.raw_input = user_message

        agent = ProposalAgent()
        async for chunk in agent.handle_message(user_message, ctx, db, project_id=project_id):
            yield chunk

        # Save context to assistant message metadata
        await self.save_message(
            db=db,
            conversation_id=conversation_id,
            role="assistant",
            content="[proposal context saved]",
            content_type="text",
            metadata=ctx.to_dict(),
            auto_commit=True,
        )

        # Auto-chain to VisualConceptAgent on the fresh confirmation transition.
        # Only when the state *just* became COMPLETED (not when re-entering an
        # already-completed proposal), so the visual stage runs exactly once.
        # 业务流程：策划确认 → 自动进入视觉创意专家产出设计图。
        if (
            initial_state != "COMPLETED"
            and ctx.state == "COMPLETED"
            and ctx.output_for_next_agent
        ):
            logger.info(
                "Proposal confirmed (domain=%s) — chaining to VisualConceptAgent",
                ctx.domain,
            )
            async for chunk in self._chain_proposal_to_visual(
                db, conversation_id, ctx, project_id
            ):
                yield chunk

    async def _chain_proposal_to_visual(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
        proposal_ctx: "ProposalContext",
        project_id: Optional[str],
    ) -> AsyncGenerator[str, None]:
        """策划案确认后，自动进入视觉创意专家 Agent（携带策划案产出）。

        把策划案的 output_for_next_agent 映射成 VisualRequirement，
        使视觉 Agent 的关键字段检查（scene + visual_style）直接通过，
        无需重新追问即可进入生成流程。
        """
        from app.agents.visual_concept import (
            VisualConceptAgent,
            VisualConceptContext,
            VisualRequirement,
        )

        handoff = proposal_ctx.output_for_next_agent or {}
        vctx = VisualConceptContext()
        vctx.requirement = VisualRequirement(
            raw_input=handoff.get("visual_direction", "") or "视觉概念图",
            scene=handoff.get("scene"),
            visual_style=handoff.get("visual_style"),
            brand_or_theme=handoff.get("brand_or_theme"),
            target_audience=handoff.get("target_audience"),
            color_tone=handoff.get("color_tone") or None,
        )
        if handoff.get("key_elements"):
            vctx.requirement.key_elements = list(handoff["key_elements"])
        if handoff.get("constraints"):
            vctx.requirement.constraints = handoff.get("constraints")

        agent = VisualConceptAgent()
        async for chunk in agent.handle_message(
            vctx.requirement.raw_input, vctx, db, project_id=project_id
        ):
            yield chunk

        # Persist the visual context so subsequent modify/confirm turns resume it
        await self.save_message(
            db=db,
            conversation_id=conversation_id,
            role="assistant",
            content="[visual concept context saved]",
            content_type="text",
            metadata=vctx.to_dict(),
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
                    lines.append(f"**{label}**: {', '.join(str(v) for v in val)}")
                else:
                    lines.append(f"**{label}**: {val}")

        # Missing info
        missing = analysis.get("missing_info", output.get("missing_info", []))
        if missing and isinstance(missing, list):
            lines.append(f"\n⚠️ **待确认**: {', '.join(missing)}")

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
    ) -> AsyncGenerator[str, None]:
        """Handle conversational intent with streaming LLM response."""
        llm = await get_llm_service(db)
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
