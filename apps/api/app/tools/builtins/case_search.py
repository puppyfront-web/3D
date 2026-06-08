"""Case Search Tool — search the structured case library."""

from typing import Any, Dict, List

from sqlalchemy import select

from app.models.case import Case
from app.tools.base import BaseTool, ToolContext, ToolManifest, ToolResult


class CaseSearchTool(BaseTool):
    """Search published cases by industry, tags, and quality score."""

    manifest = ToolManifest(
        tool_id="case_search",
        name="案例检索",
        description="从案例库中检索已发布的案例，支持按行业、标签和质量评分筛选",
        category="retrieval",
        input_schema={
            "type": "object",
            "properties": {
                "industry": {"type": "string", "description": "行业筛选"},
                "tags": {"type": "array", "description": "标签筛选"},
                "min_score": {"type": "number", "description": "最低质量评分"},
                "limit": {"type": "integer", "description": "返回数量上限", "default": 5},
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "cases": {"type": "array", "description": "匹配的案例列表"},
                "total": {"type": "integer", "description": "匹配总数"},
            },
        },
    )

    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        if context.db is None:
            return ToolResult(success=False, error="No database session")

        industry = params.get("industry")
        tags = params.get("tags", [])
        min_score = params.get("min_score", 0)
        limit = min(params.get("limit", 5), 20)

        stmt = select(Case).where(Case.is_published == True)  # noqa: E712

        if industry:
            stmt = stmt.where(Case.industry == industry)
        if min_score > 0:
            stmt = stmt.where(Case.quality_score >= min_score)

        stmt = stmt.order_by(Case.quality_score.desc()).limit(limit)

        result = await context.db.execute(stmt)
        cases = result.scalars().all()

        case_list = [
            {
                "id": str(c.id),
                "title": c.title,
                "client_name": c.client_name,
                "industry": c.industry,
                "challenge": c.challenge,
                "solution": c.solution,
                "results": c.results,
                "technologies": c.technologies,
                "quality_score": c.quality_score,
                "tags": c.tags,
            }
            for c in cases
        ]

        return ToolResult(
            success=True,
            data={"cases": case_list, "total": len(case_list)},
        )
