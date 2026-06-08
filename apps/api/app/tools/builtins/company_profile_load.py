"""Company Profile Load Tool — load company profile by company_id."""

from typing import Any, Dict

from sqlalchemy import select

from app.models.company_profile import CompanyProfile
from app.tools.base import BaseTool, ToolContext, ToolManifest, ToolResult


class CompanyProfileLoadTool(BaseTool):
    """Load a company profile with all analysis data (six_views, tech_arch, etc.)."""

    manifest = ToolManifest(
        tool_id="company_profile_load",
        name="企业画像加载",
        description="按 company_id 加载企业画像，包含六看分析、技术架构、项目背景等",
        category="loader",
        input_schema={
            "type": "object",
            "properties": {
                "company_id": {"type": "string", "description": "企业 UUID"},
            },
            "required": ["company_id"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "profile": {"type": "object"},
            },
        },
    )

    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        if context.db is None:
            return ToolResult(success=False, error="No database session")

        import uuid as _uuid

        company_id = params.get("company_id")
        if not company_id:
            return ToolResult(success=False, error="company_id is required")

        stmt = select(CompanyProfile).where(
            CompanyProfile.company_id == _uuid.UUID(company_id)
        )
        result = await context.db.execute(stmt)
        profile = result.scalar_one_or_none()

        if not profile:
            return ToolResult(success=True, data={"profile": None})

        return ToolResult(
            success=True,
            data={
                "profile": {
                    "id": str(profile.id),
                    "company_id": str(profile.company_id),
                    "strengths": profile.strengths,
                    "weaknesses": profile.weaknesses,
                    "market_position": profile.market_position,
                    "key_products": profile.key_products,
                    "competitors": profile.competitors,
                    "recent_news": profile.recent_news,
                    "culture": profile.culture,
                    "financials": profile.financials,
                    "raw_analysis": profile.raw_analysis,
                    "six_views": profile.six_views,
                    "technology_arch": profile.technology_arch,
                    "project_background": profile.project_background,
                },
            },
        )
