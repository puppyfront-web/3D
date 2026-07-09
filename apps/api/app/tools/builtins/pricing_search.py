"""Pricing Search Tool — search the 报价经验库 by industry / project type.

Returns historical pricing reference ranges so the planner can ground budget /
duration expectations in real prior engagements (PRD §12.7). All figures are
reference-only and must be human-confirmed — the tool never returns a quote to
use verbatim. Writes a retrieval_log (PRD §9.4).
"""

import time
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import or_, select

from app.models.pricing_experience import PricingExperience
from app.models.retrieval import RetrievalLog
from app.tools.base import BaseTool, ToolContext, ToolManifest, ToolResult


class PricingSearchTool(BaseTool):
    """Search active pricing experiences by industry / project type / keyword."""

    manifest = ToolManifest(
        tool_id="pricing_search",
        name="报价经验检索",
        description="按行业/项目类型检索历史报价经验区间（仅供参考，需人工确认）",
        category="retrieval",
        input_schema={
            "type": "object",
            "properties": {
                "industry": {"type": "string", "description": "行业筛选"},
                "project_type": {"type": "string", "description": "项目类型筛选"},
                "keyword": {"type": "string", "description": "关键词模糊匹配标题/备注"},
                "limit": {"type": "integer", "description": "返回数量上限", "default": 5},
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "pricing_experiences": {"type": "array"},
                "total": {"type": "integer"},
            },
        },
    )

    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        if context.db is None:
            return ToolResult(success=False, error="No database session")

        industry = params.get("industry")
        project_type = params.get("project_type")
        keyword = params.get("keyword")
        limit = min(params.get("limit", 5), 20)

        start = time.monotonic()

        stmt = select(PricingExperience).where(PricingExperience.is_active.is_(True))
        if industry:
            stmt = stmt.where(PricingExperience.industry == industry)
        if project_type:
            stmt = stmt.where(PricingExperience.project_type == project_type)
        if keyword:
            kw = f"%{keyword}%"
            stmt = stmt.where(
                or_(
                    PricingExperience.title.ilike(kw),
                    PricingExperience.notes.ilike(kw),
                )
            )
        stmt = stmt.limit(limit)

        rows = (await context.db.execute(stmt)).scalars().all()
        items: List[Dict[str, Any]] = [
            {
                "id": str(p.id),
                "title": p.title,
                "industry": p.industry,
                "project_type": p.project_type,
                "budget_range": p.budget_range,
                "duration": p.duration,
                "notes": p.notes,
            }
            for p in rows
        ]

        elapsed_ms = int((time.monotonic() - start) * 1000)
        structured = {
            k: v for k, v in {
                "industry": industry,
                "project_type": project_type,
                "keyword": keyword,
                "limit": limit,
            }.items() if v
        }
        context.db.add(RetrievalLog(
            id=uuid.uuid4(),
            query=f"pricing:{keyword or industry or project_type or '全部'}",
            retrieval_type="pricing_experience",
            results_count=len(items),
            latency_ms=elapsed_ms,
            triggered_by="pricing_search",
            structured_query_json=structured,
            retrieved_items_json=[
                {"id": it["id"], "source": "pricing_experience", "title": it["title"]}
                for it in items[:20]
            ],
        ))
        await context.db.flush()

        return ToolResult(
            success=True,
            data={"pricing_experiences": items, "total": len(items)},
        )
