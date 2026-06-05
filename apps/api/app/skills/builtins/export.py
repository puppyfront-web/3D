"""Export Skill — exports generation results to Word/PDF."""

import logging
import uuid
from typing import Any, Dict

from app.skills.base import BaseSkill, SkillContext, SkillManifest, SkillResult

logger = logging.getLogger(__name__)


class ExportSkill(BaseSkill):
    """Exports generation output to Word or PDF format."""

    manifest = SkillManifest(
        skill_id="export",
        name="方案导出",
        description="将生成结果导出为 Word/PDF 文档",
        category="export",
        input_schema={
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "format": {"type": "string"},
            },
            "required": ["task_id", "format"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
            },
        },
        required_services=["export.docx", "export.pdf"],
        permissions=["read_project_output"],
        visibility="internal",
        version="1.0.0",
    )

    async def execute(self, input_data: Dict[str, Any], context: SkillContext) -> SkillResult:
        task_id = input_data["task_id"]
        format_type = input_data["format"]  # "word" or "pdf"

        if context.db is None:
            return SkillResult(success=False, error="Database session required")

        # Load generation output
        from app.models.generation import GenerationOutput

        output = await context.db.get(GenerationOutput, uuid.UUID(task_id))
        if not output:
            return SkillResult(success=False, error=f"Generation output not found: {task_id}")

        content = output.content
        if not content:
            return SkillResult(success=False, error="No content to export")

        try:
            if format_type == "word":
                from app.services.export_service import ExportService
                file_path = await ExportService.export_to_word(
                    content=content,
                    filename=f"proposal_{task_id[:8]}",
                )
            elif format_type == "pdf":
                from app.services.export_service import ExportService
                file_path = await ExportService.export_to_pdf(
                    content=content,
                    filename=f"proposal_{task_id[:8]}",
                )
            else:
                return SkillResult(success=False, error=f"Unsupported format: {format_type}")

            return SkillResult(
                success=True,
                output={
                    "file_path": file_path,
                    "format": format_type,
                    "task_id": task_id,
                },
            )

        except Exception as e:
            logger.exception("Export failed")
            return SkillResult(success=False, error=str(e))
