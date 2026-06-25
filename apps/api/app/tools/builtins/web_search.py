"""Web Search Tool — bounded external information retrieval.

Thin adapter over app.services.search: builds the provider chain from runtime
settings (Tavily → LLM-native → degraded) and returns a normalised ToolResult.

Design rules (see docs/superpowers/specs/2026-06-25-web-search-tool-boundary.md):
  - Never raises. Failures surface as status="degraded"/"failed" so callers can
    keep running (e.g. company_analysis marks objective fields “未核实”).
  - No free-form crawling — provider scope, max_results, timeout, domain trust
    are all controlled by config, not by the LLM.
  - Returns a structured summary (key_points / conflicts / missing_info) so
    results can flow straight into rag_context / Artifact without re-prompting.
"""

import logging
from typing import Any, Dict

from app.tools.base import BaseTool, ToolContext, ToolManifest, ToolResult

logger = logging.getLogger(__name__)


class WebSearchTool(BaseTool):
    """Search the public web for external information, bounded by config."""

    manifest = ToolManifest(
        tool_id="web_search",
        name="联网搜索",
        description=(
            "在受控边界内检索公开网页信息，返回可追溯来源与结构化摘要。"
            "Provider 优先级：Tavily → LLM 自带搜索 → 降级提示。失败不阻断流程。"
        ),
        category="retrieval",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "检索查询文本"},
                "max_results": {
                    "type": "integer",
                    "description": "返回结果上限，覆盖全局配置",
                },
            },
            "required": ["query"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "status": {"type": "string", "enum": ["ok", "degraded", "failed"]},
                "results": {"type": "array"},
                "summary": {"type": "object"},
                "provider": {"type": "string"},
                "degraded_reason": {"type": "string"},
            },
        },
    )

    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        query = params.get("query", "")
        if not query or not query.strip():
            return ToolResult(success=False, error="query is required")

        if context.db is None:
            # No DB session → cannot read runtime settings → degrade safely.
            return ToolResult(
                success=True,
                data={
                    "query": query,
                    "status": "failed",
                    "results": [],
                    "summary": {},
                    "provider": "none",
                    "degraded_reason": "no_db_session",
                },
            )

        try:
            from app.services.search import search as run_search

            extra = {}
            if "max_results" in params:
                extra["max_results"] = params["max_results"]

            result = await run_search(context.db, query, extra_config=extra)
        except Exception as e:
            # Last-resort guard: the search service is designed not to raise,
            # but if something unexpected happens we still must not break the
            # calling skill — degrade instead.
            logger.exception("WebSearchTool unexpected error: %s", e)
            return ToolResult(
                success=True,
                data={
                    "query": query,
                    "status": "failed",
                    "results": [],
                    "summary": {},
                    "provider": "none",
                    "degraded_reason": f"tool_error: {type(e).__name__}",
                },
            )

        # success=True even when status=failed/degraded: the *tool call* itself
        # succeeded and returned structured data; only the search did not.
        return ToolResult(success=True, data=result.to_dict())
