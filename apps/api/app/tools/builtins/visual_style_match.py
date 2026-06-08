"""Visual Style Match Tool — search visual style library."""

from typing import Any, Dict

from sqlalchemy import select

from app.models.visual import VisualStyle
from app.tools.base import BaseTool, ToolContext, ToolManifest, ToolResult


class VisualStyleMatchTool(BaseTool):
    """Match visual styles from the style library, optionally filtered by layout."""

    manifest = ToolManifest(
        tool_id="visual_style_match",
        name="视觉风格匹配",
        description="从视觉风格库中检索匹配的风格方案",
        category="retrieval",
        input_schema={
            "type": "object",
            "properties": {
                "layout": {"type": "string", "description": "布局类型筛选"},
                "limit": {"type": "integer", "description": "返回数量上限", "default": 5},
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "styles": {"type": "array"},
                "total": {"type": "integer"},
            },
        },
    )

    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        if context.db is None:
            return ToolResult(success=False, error="No database session")

        layout = params.get("layout")
        limit = min(params.get("limit", 5), 20)

        stmt = select(VisualStyle)
        if layout:
            stmt = stmt.where(VisualStyle.layout == layout)
        stmt = stmt.limit(limit)

        result = await context.db.execute(stmt)
        styles = result.scalars().all()

        style_list = [
            {
                "id": str(s.id),
                "name": s.name,
                "description": s.description,
                "primary_color": s.primary_color,
                "secondary_color": s.secondary_color,
                "accent_color": s.accent_color,
                "background_color": s.background_color,
                "font_primary": s.font_primary,
                "font_secondary": s.font_secondary,
                "layout": s.layout,
                "brand_guidelines": s.brand_guidelines,
                "material_spec": s.material_spec,
                "lighting_spec": s.lighting_spec,
            }
            for s in styles
        ]

        return ToolResult(
            success=True,
            data={"styles": style_list, "total": len(style_list)},
        )
