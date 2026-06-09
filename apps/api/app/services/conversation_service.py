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
from app.services.pipeline_state import PipelineState

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

        # 2.5 Check for paused pipeline that needs resuming
        pipeline_state = self._load_pipeline_state(messages)
        if pipeline_state and pipeline_state.status == "paused":
            logger.info("Resuming paused pipeline at stage: %s", pipeline_state.current_stage)
            async for chunk in self._handle_sop_pipeline_resume(
                db, conv_uuid, user_message, pipeline_state, history
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
            async for chunk in self._handle_sop_pipeline(
                db, conv_uuid, user_message, intent, history
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

        # Final done event
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
            if not input_data.get("user_message") and history:
                # Get the last user message from history
                for msg in reversed(history):
                    if msg.get("role") == "user":
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

            context = SkillContext(
                project_id=project_id,
                user_id=None,
                db=db,
                llm_service=await get_llm_service(db),
                embedding_service=await get_embedding_service(db),
                image_service=await get_image_service(db),
            )

            # Notify frontend that a skill is starting — send as content block
            skill = registry.get(skill_id)
            skill_name = skill.manifest.name if skill else skill_id
            yield f"data: {json.dumps({'type': 'content_block_start', 'data': {'block_type': 'skill_executing'}})}\n\n"
            yield f"data: {json.dumps({'type': 'content_block_data', 'data': {'type': 'skill_executing', 'data': {'skill_id': skill_id, 'name': skill_name}}})}\n\n"
            yield f"data: {json.dumps({'type': 'content_block_end'})}\n\n"

            runner = SkillRunner(registry)
            result = await runner.run(skill_id, input_data, context)

            if result.get("success"):
                output = result.get("output", {})

                # ── Auto-chain: visual_prompt → image_generation (2 variations) ──
                if skill_id == "visual_prompt" and isinstance(output, dict) and output.get("positive_prompt"):
                    image_input = {
                        "prompt": output["positive_prompt"],
                        "negative_prompt": output.get("negative_prompt", ""),
                        "width": input_data.get("width", 1024),
                        "height": input_data.get("height", 768),
                        "style": output.get("visual_strategy", {}).get("concept") if isinstance(output.get("visual_strategy"), dict) else None,
                    }
                    if project_id:
                        image_input["project_id"] = project_id

                    # Generate 2 variations for comparison
                    collected_images: list[dict] = []
                    for _idx in range(2):
                        image_result = await runner.run("image_generation", image_input, context)
                        if image_result.get("success"):
                            img_url = image_result.get("output", {}).get("image_url")
                            if img_url:
                                collected_images.append({"url": img_url})

                    if collected_images:
                        output["images"] = collected_images
                        # Keep single image_url for backward compat
                        output["image_url"] = collected_images[0]["url"]

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
            combined = f"{company_info} {requirement}".strip()

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

    def _load_pipeline_state(self, messages: List[Message]) -> Optional[PipelineState]:
        """Recover pipeline state from the most recent assistant message metadata."""
        for msg in reversed(messages):
            if msg.metadata_json and "pipeline" in msg.metadata_json:
                return PipelineState.from_dict(msg.metadata_json)
        return None

    async def _handle_sop_pipeline_resume(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
        user_message: str,
        state: PipelineState,
        history: List[Dict[str, str]],
    ) -> AsyncGenerator[str, None]:
        """Resume a paused pipeline based on user action (confirm/modify/restart)."""
        from app.services.intent_service import IntentDetector

        action = IntentDetector.classify_pipeline_action(user_message)

        if action == "restart":
            state.reset()
            confirm_text = "🔄 已重置方案流程，重新从企业解析开始...\n\n"
            yield f"data: {json.dumps({'type': 'text_delta', 'text': confirm_text})}\n\n"
            async for chunk in self._execute_pipeline_stage(
                db, conversation_id, state, history
            ):
                yield chunk
            return

        if action == "confirm":
            stage_names = {
                "company_analysis": "企业画像",
                "proposal_generation": "策划案",
                "visual_generation": "视觉方案",
            }
            current_name = stage_names.get(state.current_stage, state.current_stage)
            confirm_text = f"✅ **{current_name}** 已确认，进入下一阶段...\n\n"
            yield f"data: {json.dumps({'type': 'text_delta', 'text': confirm_text})}\n\n"

            next_stage = state.advance()
            if next_stage is None:
                done_text = "🎉 方案流程已全部完成！所有产物已保存。"
                yield f"data: {json.dumps({'type': 'text_delta', 'text': done_text})}\n\n"
                await self.save_message(
                    db, conversation_id, "assistant",
                    content=confirm_text + done_text, content_type="text",
                    metadata=state.to_dict(), auto_commit=True,
                )
                return

            async for chunk in self._execute_pipeline_stage(
                db, conversation_id, state, history
            ):
                yield chunk
            return

        # action == "modify"
        state.project_context["modify_feedback"] = user_message
        modify_text = f"📝 收到修改意见，正在重新生成...\n\n"
        yield f"data: {json.dumps({'type': 'text_delta', 'text': modify_text})}\n\n"
        state.status = "running"
        async for chunk in self._execute_pipeline_stage(
            db, conversation_id, state, history
        ):
            yield chunk

    async def _handle_sop_pipeline(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
        user_message: str,
        intent: IntentResult,
        history: List[Dict[str, str]],
    ) -> AsyncGenerator[str, None]:
        """Launch a full SOP pipeline: company_analysis -> proposal -> visual -> export."""
        # Quick pre-check: does the user message contain any entity info?
        has_entity = len(user_message) > 10
        if not has_entity:
            prompt_text = (
                "请提供以下信息，我将为您启动完整的方案设计流程：\n\n"
                "1. **企业名称**（必填）\n"
                "2. 所属行业\n"
                "3. 项目需求简述\n\n"
                "例如：*「给华为科技公司设计一套3D展示幕墙方案，用于新品发布会」*"
            )
            yield f"data: {json.dumps({'type': 'text_delta', 'text': prompt_text})}\n\n"
            await self.save_message(
                db, conversation_id, "assistant",
                content=prompt_text, content_type="text",
                auto_commit=True,
            )
            return

        # Initialize pipeline state
        state = PipelineState()
        state.project_context = {
            "user_message": user_message,
            "company_name": self._extract_company_name(user_message),
        }

        # Execute Stage 1: company_analysis
        async for chunk in self._execute_pipeline_stage(
            db, conversation_id, state, history
        ):
            yield chunk

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

    async def _execute_pipeline_stage(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
        state: PipelineState,
        history: List[Dict[str, str]],
    ) -> AsyncGenerator[str, None]:
        """Execute the current pipeline stage, stream results, and pause/advance."""
        from app.skills.base import SkillContext
        from app.skills.registry import SkillRegistry
        from app.skills.runner import SkillRunner
        from app.services.embedding_service import get_embedding_service
        from app.services.image_service import get_image_service
        from app.services.pipeline_state import PAUSE_STAGES

        stage = state.current_stage

        # Build skill input from pipeline context
        input_data = self._build_stage_input(stage, state, history)

        # Get project_id from conversation
        conv = await self.get_conversation_detail(db, str(conversation_id))
        project_id = str(conv.project_id) if conv and conv.project_id else None
        if project_id:
            input_data["project_id"] = project_id

        # Prepare context
        registry = SkillRegistry.get_instance()
        if not registry.list_skills():
            registry.auto_register()

        context = SkillContext(
            project_id=project_id,
            user_id=None,
            db=db,
            llm_service=await get_llm_service(db),
            embedding_service=await get_embedding_service(db),
            image_service=await get_image_service(db),
        )

        # Stream stage-start indicator
        stage_names = {
            "company_analysis": "企业解析",
            "proposal_generation": "策划案生成",
            "visual_generation": "视觉方案生成",
            "export": "方案导出",
        }
        stage_display = stage_names.get(stage, stage)
        progress_text = f"🔄 **{stage_display}** 阶段开始执行...\n\n"
        yield f"data: {json.dumps({'type': 'text_delta', 'text': progress_text})}\n\n"

        # Execute skill(s)
        runner = SkillRunner(registry)
        all_output: Dict[str, Any] = {}

        if stage == "visual_generation":
            vp_result = await runner.run("visual_prompt", input_data, context)
            if vp_result.get("success"):
                all_output = vp_result.get("output", {})
                collected_images: list = []
                for _ in range(2):
                    img_input = {
                        "prompt": all_output.get("positive_prompt", ""),
                        "negative_prompt": all_output.get("negative_prompt", ""),
                        "width": input_data.get("width", 1024),
                        "height": input_data.get("height", 768),
                    }
                    if project_id:
                        img_input["project_id"] = project_id
                    img_result = await runner.run("image_generation", img_input, context)
                    if img_result.get("success"):
                        url = img_result.get("output", {}).get("image_url")
                        if url:
                            collected_images.append({"url": url})
                if collected_images:
                    all_output["images"] = collected_images
                    all_output["image_url"] = collected_images[0]["url"]
        elif stage == "export":
            export_input = self._build_export_input(state, project_id)
            if export_input.get("task_id"):
                result = await runner.run("export", export_input, context)
                if result.get("success"):
                    all_output = result.get("output", {})
                else:
                    all_output = await self._fallback_export(state, context, project_id)
            else:
                all_output = await self._fallback_export(state, context, project_id)
        else:
            skill_id = stage
            result = await runner.run(skill_id, input_data, context)
            if result.get("success"):
                all_output = result.get("output", {})
            else:
                error_msg = result.get("error", "执行失败")
                error_text = f"❌ **{stage_display}** 执行失败：{error_msg}\n\n请尝试重新描述需求。"
                yield f"data: {json.dumps({'type': 'text_delta', 'text': error_text})}\n\n"
                state.status = "failed"
                await self.save_message(
                    db, conversation_id, "assistant",
                    content=error_text, content_type="text",
                    metadata=state.to_dict(), auto_commit=True,
                )
                return

        # Save stage output
        state.stage_outputs[stage] = all_output

        # Render output text
        skill_id_for_render = "visual_prompt" if stage == "visual_generation" else stage
        content_text = self._render_skill_output(skill_id_for_render, all_output)

        # Build content blocks
        blocks = self._build_stage_blocks(stage, all_output, state)

        # Stream output
        yield f"data: {json.dumps({'type': 'text_delta', 'text': content_text})}\n\n"

        for block in blocks:
            yield f"data: {json.dumps({'type': 'content_block_start', 'data': {'block_type': block['type']}})}\n\n"
            yield f"data: {json.dumps({'type': 'content_block_data', 'data': block})}\n\n"
            yield f"data: {json.dumps({'type': 'content_block_end'})}\n\n"

        # Pause or complete
        if stage in PAUSE_STAGES:
            state.pause()
        else:
            state.advance()

        # Save assistant message with pipeline state
        await self.save_message(
            db, conversation_id, "assistant",
            content=content_text, content_type="rich",
            rich_content={"blocks": blocks},
            metadata=state.to_dict(), auto_commit=True,
        )

    @staticmethod
    def _build_stage_input(
        stage: str, state: PipelineState, history: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """Build skill input data from pipeline state and history."""
        user_msg = state.project_context.get("user_message", "")

        if stage == "company_analysis":
            return {
                "company_info": user_msg,
                "company_name": state.project_context.get("company_name", ""),
            }

        elif stage == "proposal_generation":
            company_output = state.stage_outputs.get("company_analysis", {})
            return {
                "requirement_text": user_msg,
                "company_profile": company_output,
                "company_info": user_msg,
            }

        elif stage == "visual_generation":
            proposal_output = state.stage_outputs.get("proposal_generation", {})
            company_output = state.stage_outputs.get("company_analysis", {})
            return {
                "user_message": user_msg,
                "proposal_context": proposal_output,
                "visual_direction": company_output.get("recommended_visual_direction", ""),
                "style": state.project_context.get("visual_style"),
            }

        elif stage == "export":
            return {}

        return {"user_message": user_msg}

    @staticmethod
    def _build_stage_blocks(
        stage: str, output: Dict[str, Any], state: PipelineState
    ) -> List[Dict[str, Any]]:
        """Build rich content blocks for a pipeline stage."""
        blocks: List[Dict[str, Any]] = []

        blocks.append({
            "type": "skill_progress",
            "data": {"skill_id": stage, "status": "completed"},
        })

        if stage == "company_analysis" and output:
            blocks.append({"type": "company_analysis_card", "data": output})

        elif stage == "proposal_generation" and output:
            missing = output.get("missing_info", [])
            sections = output.get("sections_meta", [])
            blocks.append({
                "type": "proposal_section",
                "data": {
                    "content_type": "text/markdown",
                    "missing_info": missing if isinstance(missing, list) else [],
                    "sections": sections if isinstance(sections, list) else [],
                },
            })

        elif stage == "visual_generation" and output:
            blocks.append({"type": "visual_result", "data": output})

        elif stage == "export" and output:
            blocks.append({"type": "artifact", "data": output})

        # Action buttons for pause stages
        if stage == "company_analysis":
            blocks.append({
                "type": "action_buttons",
                "data": {"buttons": [
                    {"label": "✓ 确认企业画像，继续", "value": "确认继续", "action": "quick_reply"},
                    {"label": "↻ 重新生成", "value": "重新生成企业解析", "action": "quick_reply"},
                ]},
            })
        elif stage == "proposal_generation":
            blocks.append({
                "type": "action_buttons",
                "data": {"buttons": [
                    {"label": "✓ 确认策划案，继续", "value": "确认继续", "action": "quick_reply"},
                    {"label": "✎ 我有修改意见", "value": "修改策划案", "action": "quick_reply"},
                ]},
            })
        elif stage == "visual_generation":
            blocks.append({
                "type": "action_buttons",
                "data": {"buttons": [
                    {"label": "使用方案 A", "value": "使用第一张效果图", "action": "quick_reply"},
                    {"label": "使用方案 B", "value": "使用第二张效果图", "action": "quick_reply"},
                    {"label": "两个都用", "value": "两张都可以继续", "action": "quick_reply"},
                ]},
            })

        return blocks

    @staticmethod
    def _build_export_input(
        state: PipelineState, project_id: Optional[str]
    ) -> Dict[str, Any]:
        """Build export skill input from accumulated pipeline outputs."""
        proposal_output = state.stage_outputs.get("proposal_generation", {})
        task_id = proposal_output.get("output_id") or proposal_output.get("task_id")

        if task_id:
            return {"task_id": str(task_id), "format": "word"}

        return {"task_id": "", "format": "word"}

    async def _fallback_export(
        self,
        state: PipelineState,
        context: "SkillContext",
        project_id: Optional[str],
    ) -> Dict[str, Any]:
        """Direct export when no GenerationOutput record exists (pipeline chat mode)."""
        try:
            from app.services.export_service import get_export_service

            proposal_output = state.stage_outputs.get("proposal_generation", {})
            content = proposal_output.get("content", proposal_output.get("proposal_text", ""))

            if not content:
                company_output = state.stage_outputs.get("company_analysis", {})
                parts = []
                if company_output:
                    parts.append("# 企业解析\n")
                    parts.append(str(company_output.get("summary", "")))
                if proposal_output:
                    parts.append("\n# 策划方案\n")
                    parts.append(str(proposal_output))
                content = "\n".join(parts)

            if not content:
                return {"error": "No content to export"}

            service = get_export_service()
            file_path = await service.export_to_word(
                content=content,
                filename=f"pipeline_{state.started_at[:10]}.docx",
            )
            return {"file_path": file_path, "format": "word"}
        except Exception as e:
            return {"error": str(e)}

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
        # Generic fallback
        return json.dumps(output, ensure_ascii=False, indent=2) if output else "执行完成"

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
        """Render visual output as readable text."""
        lines = []
        strategy = output.get("visual_strategy", {})
        if strategy and isinstance(strategy, dict):
            lines.append("## 视觉策略\n")
            for key, label in [
                ("concept", "概念"), ("elements", "核心元素"),
                ("color_palette", "色彩方案"), ("composition", "构图"),
                ("mood", "氛围"),
            ]:
                val = strategy.get(key)
                if val:
                    if isinstance(val, list):
                        lines.append(f"**{label}**: {', '.join(str(v) for v in val)}")
                    else:
                        lines.append(f"**{label}**: {val}")

        pos_prompt = output.get("positive_prompt", "")
        if pos_prompt:
            lines.append(f"\n**正向 Prompt**:\n```\n{pos_prompt}\n```")
        neg_prompt = output.get("negative_prompt", "")
        if neg_prompt:
            lines.append(f"\n**负向 Prompt**:\n```\n{neg_prompt}\n```")

        advice = output.get("composition_advice", "")
        if advice:
            lines.append(f"\n**构图建议**: {advice}")

        # Image generation result
        image_url = output.get("image_url")
        if image_url:
            lines.append(f"\n✅ **图片已生成**，见下方卡片。")

        return "\n".join(lines) if lines else "视觉方案生成完成。"

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
