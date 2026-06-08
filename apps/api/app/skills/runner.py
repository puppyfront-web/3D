"""Skill Runner — executes skills with logging, timing, and error handling."""

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

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
            result: SkillResult = await skill.execute(input_data, context)
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
