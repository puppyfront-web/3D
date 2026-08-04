"""Single entry point for web-search context acquisition.

Two independent code paths previously each built their own web-search wiring:

- ``app/skills/builtins/company_analysis.py`` (skill "mode A") went through the
  ToolRegistry → ``WebSearchTool``.
- ``app/services/conversation_service.py::_handle_auto_fill`` instantiated
  ``WebSearchTool()`` directly.

Both ultimately call ``app.services.search.search`` (the provider-chain factory).
This helper collapses them into ONE call site so search behaviour — provider
precedence, settings reads, degradation — is defined in exactly one place
(Defect #11).

Task 1 (售前直出成品): adds optional ``context_hint`` — when provided, the raw
query is first rewritten by a single LLM call into a sharper search term, so
node-scoped / conversational searches are not bound to a fixed template.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.llm_service import get_llm_service

logger = logging.getLogger(__name__)


async def _rewrite_query(
    db: Optional[AsyncSession], raw_query: str, context_hint: str
) -> str:
    """Rewrite (raw_query, context_hint) into one sharp search term via LLM.

    Never raises — on any failure returns ``raw_query`` so the caller keeps
    working (search must never break the conversation).
    """
    if not context_hint or not context_hint.strip():
        return raw_query
    try:
        llm = await get_llm_service(db)
        result = await llm.generate_json(
            prompt=(
                f"用户输入：{raw_query}\n"
                f"上下文：{context_hint}\n"
                "请把以上信息改写成一个最精准、最适合用于网络搜索的中文搜索词"
                "（不要问句、不要解释、不要引号）。只输出 JSON：{\"query\": string}"
            ),
            system_prompt="你是搜索词优化助手，只输出 JSON。",
            temperature=0.2,
        )
        q = (result.get("query") or "").strip() if isinstance(result, dict) else ""
        return q or raw_query
    except Exception as e:  # noqa: BLE001 — degrade, never crash
        logger.warning("_rewrite_query failed (%s); using raw query.", e)
        return raw_query


async def acquire_web_context(
    db: Optional[AsyncSession],
    query: str,
    max_results: int = 5,
    context_hint: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Single entry point for web search context acquisition.

    When ``context_hint`` is provided (node title + user ask + material
    summary), the query is first rewritten by one LLM call into a sharper
    search term (Task 1). Returns ``(web_hits, summary)``.

    - ``web_hits``: normalised hit dicts (title / url / domain / snippet /
      published_at / source_type / confidence).
    - ``summary``: the ``external_search_summary`` dict carrying
      status / provider / degraded_reason / key_points / conflicts /
      missing_info / recommended_usage.

    Never raises — degrades gracefully to ``([], {"status": "failed"})`` so the
    calling skill/pipeline keeps running (see AGENT_SPEC §2.3).
    """
    empty_summary: Dict[str, Any] = {"status": "failed"}

    if not query or not query.strip():
        return [], {**empty_summary, "reason": "empty_query"}

    if db is None:
        # No DB session → cannot read runtime settings → degrade safely.
        return [], {**empty_summary, "reason": "no_db_session"}

    rewritten = await _rewrite_query(db, query, context_hint) if context_hint else query

    try:
        from app.services.search import search as run_search

        result = await run_search(db, rewritten, extra_config={"max_results": max_results})
    except Exception as e:
        # The search service is designed not to raise, but guard anyway so a
        # caller is never broken by a search failure.
        logger.warning("acquire_web_context: search failed for %r: %s", rewritten, e)
        return [], {**empty_summary, "reason": f"{type(e).__name__}: {e}"}

    # Normalise hits into plain dicts (SearchHit.to_dict rounds confidence).
    web_hits = [h.to_dict() for h in result.hits]

    summary = result.summary or {}
    external_search_summary: Dict[str, Any] = {
        "status": result.status,
        "provider": result.provider or "",
        "degraded_reason": result.degraded_reason,
        "key_points": summary.get("key_points", []),
        "conflicts": summary.get("conflicts", []),
        "missing_info": summary.get("missing_info", []),
        "recommended_usage": summary.get("recommended_usage", ""),
    }
    return web_hits, external_search_summary
