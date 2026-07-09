"""Talking Points Search Tool — search the 话术库 by scenario / industry / tag.

Lets the planning and tone agents pull reusable presales scripts so messaging
stays consistent and traceable (PRD §12.6 / §13). Writes a retrieval_log so
话术 lookups are auditable alongside knowledge/case searches (PRD §9.4).
"""

import time
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import or_, select

from app.models.retrieval import RetrievalLog
from app.models.talking_point import TalkingPoint
from app.tools.base import BaseTool, ToolContext, ToolManifest, ToolResult


class TalkingPointsSearchTool(BaseTool):
    """Search active talking points by scenario, industry, or keyword."""

    manifest = ToolManifest(
        tool_id="talking_points_search",
        name="话术检索",
        description="按场景/行业/关键词检索售前话术，供策划与定调保持表达一致",
        category="retrieval",
        input_schema={
            "type": "object",
            "properties": {
                "scenario": {"type": "string", "description": "场景筛选（如首次接洽/异议处理）"},
                "industry": {"type": "string", "description": "行业筛选"},
                "keyword": {"type": "string", "description": "关键词模糊匹配标题/内容"},
                "limit": {"type": "integer", "description": "返回数量上限", "default": 5},
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "talking_points": {"type": "array"},
                "total": {"type": "integer"},
            },
        },
    )

    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        if context.db is None:
            return ToolResult(success=False, error="No database session")

        scenario = params.get("scenario")
        industry = params.get("industry")
        keyword = params.get("keyword")
        limit = min(params.get("limit", 5), 20)

        start = time.monotonic()

        stmt = select(TalkingPoint).where(TalkingPoint.is_active.is_(True))
        if scenario:
            stmt = stmt.where(TalkingPoint.scenario == scenario)
        if industry:
            stmt = stmt.where(TalkingPoint.industry == industry)
        if keyword:
            kw = f"%{keyword}%"
            stmt = stmt.where(
                or_(
                    TalkingPoint.title.ilike(kw),
                    TalkingPoint.content.ilike(kw),
                )
            )
        stmt = stmt.limit(limit)

        rows = (await context.db.execute(stmt)).scalars().all()
        items: List[Dict[str, Any]] = [
            {
                "id": str(t.id),
                "scenario": t.scenario,
                "title": t.title,
                "content": t.content,
                "industry": t.industry,
                "tags": t.tags,
            }
            for t in rows
        ]

        elapsed_ms = int((time.monotonic() - start) * 1000)
        structured = {
            k: v for k, v in {
                "scenario": scenario,
                "industry": industry,
                "keyword": keyword,
                "limit": limit,
            }.items() if v
        }
        context.db.add(RetrievalLog(
            id=uuid.uuid4(),
            query=f"talking_points:{keyword or scenario or industry or '全部'}",
            retrieval_type="talking_points",
            results_count=len(items),
            latency_ms=elapsed_ms,
            triggered_by="talking_points_search",
            structured_query_json=structured,
            retrieved_items_json=[
                {"id": it["id"], "source": "talking_point", "title": it["title"]}
                for it in items[:20]
            ],
        ))
        await context.db.flush()

        return ToolResult(success=True, data={"talking_points": items, "total": len(items)})
