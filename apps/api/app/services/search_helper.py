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
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def acquire_web_context(
    db: Optional[AsyncSession],
    query: str,
    max_results: int = 5,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Single entry point for web search context acquisition.

    Returns ``(web_hits, summary)`` where:

    - ``web_hits`` is a list of normalised hit dicts (title / url / domain /
      snippet / published_at / source_type / confidence).
    - ``summary`` is the ``external_search_summary`` dict carrying
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

    try:
        from app.services.search import search as run_search

        result = await run_search(db, query, extra_config={"max_results": max_results})
    except Exception as e:
        # The search service is designed not to raise, but guard anyway so a
        # caller is never broken by a search failure.
        logger.warning("acquire_web_context: search failed for %r: %s", query, e)
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
