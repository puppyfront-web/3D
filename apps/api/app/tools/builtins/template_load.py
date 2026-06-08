"""Proposal Template Load Tool — load proposal templates by category."""

from typing import Any, Dict

from sqlalchemy import select

from app.models.template import ProposalTemplate
from app.tools.base import BaseTool, ToolContext, ToolManifest, ToolResult


class TemplateLoadTool(BaseTool):
    """Load a proposal template by category, preferring the default one."""

    manifest = ToolManifest(
        tool_id="template_load",
        name="方案模板加载",
        description="按类别加载方案模板，返回章节结构和变量",
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
                "sections": {"type": "array"},
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
            template = await context.db.get(ProposalTemplate, _uuid.UUID(template_id))
        elif category:
            stmt = (
                select(ProposalTemplate)
                .where(ProposalTemplate.category == category, ProposalTemplate.is_default == True)  # noqa: E712
                .limit(1)
            )
            result = await context.db.execute(stmt)
            template = result.scalar_one_or_none()

            if not template:
                stmt = select(ProposalTemplate).where(ProposalTemplate.category == category).limit(1)
                result = await context.db.execute(stmt)
                template = result.scalar_one_or_none()

        if not template:
            return ToolResult(success=True, data={"sections": []})

        return ToolResult(
            success=True,
            data={
                "sections": template.sections or [],
                "variables": template.variables or {},
                "template_id": str(template.id),
                "name": template.name,
            },
        )
