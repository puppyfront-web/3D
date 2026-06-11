"""Skill Runner — executes skills with logging, timing, and error handling."""

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.prompts import GLOBAL_CAPABILITY_CONSTRAINT
from app.skills.base import BaseSkill, SkillContext, SkillResult
from app.skills.registry import SkillRegistry

logger = logging.getLogger(__name__)


class SkillRunner:
    """Executes skills and records results in the database."""

    def __init__(self, registry: Optional[SkillRegistry] = None):
        self._registry = registry or SkillRegistry.get_instance()

    async def run(
        self,
        skill_id: str,
        input_data: Dict[str, Any],
        context: SkillContext,
    ) -> Dict[str, Any]:
        """Execute a skill by ID and return the execution record.

        Steps:
        1. Look up skill from registry
        2. Validate input
        3. Create SkillExecution record (status=running)
        4. Execute skill with timing
        5. Update SkillExecution record (completed/failed)
        6. Return execution data
        """
        skill = self._registry.get(skill_id)
        if not skill:
            return {"success": False, "error": f"Skill not found: {skill_id}"}

        # Validate input
        if not skill.validate_input(input_data):
            required = skill.manifest.input_schema.get("required", [])
            missing = [k for k in required if k not in input_data]
            return {
                "success": False,
                "error": f"Input validation failed for skill: {skill_id}",
                "missing_fields": missing,
                "hint": f"该技能需要关联项目才能执行，缺少: {', '.join(missing)}。请在项目工作台中操作，或先创建/关联一个项目。",
            }

        execution_id = uuid.uuid4()
        started_at = time.monotonic()

        # Create execution record in DB if session available
        execution_record = None
        if context.db is not None:
            from app.models.skill import SkillExecution
            skill_db_id = await self._resolve_skill_db_id(skill_id, context)
            if skill_db_id is not None:
                execution_record = SkillExecution(
                    id=execution_id,
                    skill_id=skill_db_id,
                    project_id=uuid.UUID(context.project_id) if context.project_id else None,
                    user_id=uuid.UUID(context.user_id) if context.user_id else None,
                    input_json=input_data,
                    status="running",
                )
                context.db.add(execution_record)
                await context.db.flush()
            else:
                logger.warning("Skill %s is not seeded in DB; skipping execution log", skill_id)

        # Execute
        try:
            logger.info("SkillRunner: calling skill.execute() for %s", skill_id)
            result: SkillResult = await skill.execute(input_data, context)
            logger.info("SkillRunner: skill.execute() returned for %s (success=%s)", skill_id, result.success)
            elapsed_ms = int((time.monotonic() - started_at) * 1000)
            result.duration_ms = elapsed_ms

            # Update execution record
            if execution_record is not None:
                execution_record.status = "completed" if result.success else "failed"
                execution_record.output_json = result.output
                execution_record.duration_ms = elapsed_ms
                execution_record.used_cases = result.used_cases
                execution_record.used_documents = result.used_documents
                execution_record.used_chunks = result.used_chunks
                execution_record.error_message = result.error
                execution_record.completed_at = datetime.now(timezone.utc)
                await context.db.flush()

            return {
                "execution_id": str(execution_id) if execution_record is not None else None,
                **result.to_dict(),
            }

        except Exception as e:
            elapsed_ms = int((time.monotonic() - started_at) * 1000)
            logger.exception("Skill execution failed: %s", skill_id)

            if execution_record is not None:
                execution_record.status = "failed"
                execution_record.error_message = str(e)
                execution_record.duration_ms = elapsed_ms
                execution_record.completed_at = datetime.now(timezone.utc)
                await context.db.flush()

            return {
                "execution_id": str(execution_id) if execution_record is not None else None,
                "success": False,
                "error": str(e),
                "duration_ms": elapsed_ms,
            }

    async def _resolve_skill_db_id(self, skill_id: str, context: SkillContext) -> Optional[uuid.UUID]:
        """Resolve the string skill_id to the database UUID."""
        from sqlalchemy import select
        from app.models.skill import Skill

        result = await context.db.execute(
            select(Skill.id).where(Skill.skill_id == skill_id)
        )
        row = result.scalar_one_or_none()
        if row:
            return row
        return None

    async def run_with_react(
        self,
        skill_id: str,
        input_data: Dict[str, Any],
        context: SkillContext,
        max_turns: int = 2,
    ) -> Dict[str, Any]:
        """Execute a skill with ReAct reflection loop.

        If the skill fails or returns missing_info, reflect on the result
        and potentially retry with supplemented inputs.
        """
        current_input = dict(input_data)
        current_skill_id = skill_id

        for turn in range(max_turns):
            result = await self.run(current_skill_id, current_input, context)

            # Success with no missing info — return immediately
            if result.get("success") and not result.get("missing_info"):
                return result

            # Skill not found or other structural error — don't retry
            if not result.get("success") and "not found" in (result.get("error") or "").lower():
                return result

            # Skill failed or has missing_info — attempt reflection
            if turn < max_turns - 1 and context.llm_service:
                reflection = await self._reflect(
                    current_skill_id, current_input, result, context
                )
                action = reflection.get("action", "give_up")

                if action == "retry_with_supplement":
                    supplement = reflection.get("supplement", {})
                    current_input.update(supplement)
                    logger.info(
                        "ReAct retry turn %d: supplementing %d fields for %s",
                        turn + 1, len(supplement), current_skill_id,
                    )
                    continue
                elif action == "ask_user":
                    result["_react_ask_user"] = reflection.get("question", "")
                    return result
                elif action == "fallback_skill":
                    fallback = reflection.get("fallback_skill_id")
                    if fallback and fallback != current_skill_id:
                        current_skill_id = fallback
                        logger.info(
                            "ReAct fallback turn %d: switching %s -> %s",
                            turn + 1, skill_id, fallback,
                        )
                        continue
                # give_up or unknown — break
            break

        return result

    async def _reflect(
        self,
        skill_id: str,
        input_data: Dict[str, Any],
        result: Dict[str, Any],
        context: SkillContext,
    ) -> Dict[str, Any]:
        """Use LLM to reflect on a skill execution result and decide next action."""
        reflection_prompt = f"""一个 Skill 刚执行完毕，请分析结果并决定下一步动作。

Skill: {skill_id}
输入概要: { {k: str(v)[:100] for k, v in input_data.items()} }
执行成功: {result.get('success')}
缺失信息: {result.get('missing_info', [])}
错误: {result.get('error', '无')}

可选动作：
- "retry_with_supplement": 缺少的信息可以从已有上下文中推断，给出补充参数
- "ask_user": 必须由用户补充，生成追问文本
- "give_up": 不可恢复错误，返回错误信息

返回 JSON:
{{
  "thought": "分析过程",
  "action": "retry_with_supplement | ask_user | give_up",
  "supplement": {{}},
  "question": ""
}}"""

        try:
            reflection = await context.llm_service.generate_json(
                prompt=reflection_prompt,
                system_prompt="你是 Skill 执行反思引擎。分析执行结果，决定下一步最优动作。" + GLOBAL_CAPABILITY_CONSTRAINT,
                temperature=0.1,
            )
            return reflection
        except Exception:
            logger.exception("ReAct reflection failed for %s", skill_id)
            return {"action": "give_up"}
