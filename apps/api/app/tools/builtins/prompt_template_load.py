"""Prompt Template Load Tool — load prompt templates by category."""

from typing import Any, Dict

from sqlalchemy import select

from app.models.template import PromptTemplate
from app.tools.base import BaseTool, ToolContext, ToolManifest, ToolResult


class PromptTemplateLoadTool(BaseTool):
    """Load a prompt template by category, preferring the default one."""

    manifest = ToolManifest(
        tool_id="prompt_template_load",
        name="Prompt 模板加载",
        description="按类别加载 Prompt 模板，优先返回默认模板",
        category="loader",
        input_schema={
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "模板类别"},
                "template_id": {"type": "string", "description": "指定模板 UUID"},
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "template_text": {"type": "string"},
                "variables": {"type": "object"},
                "template_id": {"type": "string"},
            },
        },
    )

    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        if context.db is None:
            return ToolResult(success=False, error="No database session")

        import uuid as _uuid

        template_id = params.get("template_id")
        category = params.get("category")

        template = None

        if template_id:
            template = await context.db.get(PromptTemplate, _uuid.UUID(template_id))
        elif category:
            # Prefer default template for the category
            stmt = (
                select(PromptTemplate)
                .where(PromptTemplate.category == category, PromptTemplate.is_default == True)  # noqa: E712
                .limit(1)
            )
            result = await context.db.execute(stmt)
            template = result.scalar_one_or_none()

            # Fall back to any template in the category
            if not template:
                stmt = select(PromptTemplate).where(PromptTemplate.category == category).limit(1)
                result = await context.db.execute(stmt)
                template = result.scalar_one_or_none()

        if not template:
            return ToolResult(success=True, data={"template_text": None})

        return ToolResult(
            success=True,
            data={
                "template_text": template.template_text,
                "variables": template.variables or {},
                "template_id": str(template.id),
            },
        )
