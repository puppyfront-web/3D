"""Factory for the search orchestrator — reads config and wires providers.

Mirrors the pattern of app.services.llm_service.get_llm_service: read settings
DB-first with .env fallback, then construct the runtime objects.
"""

import logging
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.search.base import WebSearchResult
from app.services.search.orchestrator import SearchOrchestrator

logger = logging.getLogger(__name__)


async def search(
    db: AsyncSession, query: str, extra_config: Optional[dict] = None
) -> WebSearchResult:
    """Run a web search using the configured provider precedence chain.

    Reads web_search_* settings (DB-first, .env fallback) plus the llm_* settings
    to build the LLM-native client when applicable. Never raises — returns a
    WebSearchResult with status=failed on any problem.

    extra_config lets a caller override per-call settings (e.g. max_results).
    """
    from app.services.settings_service import SettingsService

    keys = [
        "web_search_enabled", "web_search_mode", "web_search_tavily_api_key",
        "web_search_max_results", "web_search_timeout", "web_search_min_confidence",
        "llm_provider", "llm_api_key", "llm_base_url", "llm_model",
    ]
    cfg = await SettingsService.get_raw_many(db, keys)

    enabled = _to_bool(cfg.get("web_search_enabled"), default=True)
    if not enabled:
        return WebSearchResult(
            query=query, status="failed", provider="none",
            degraded_reason="disabled_by_config",
        )

    config = {
        "mode": cfg.get("web_search_mode") or "auto",
        "tavily_api_key": cfg.get("web_search_tavily_api_key") or "",
        "max_results": extra_config.get("max_results") if extra_config else None
        or int(cfg.get("web_search_max_results") or 5),
        "timeout": int(cfg.get("web_search_timeout") or 15),
        "min_confidence": float(cfg.get("web_search_min_confidence") or 0.5),
    }

    llm_client = _maybe_build_llm_client(
        cfg.get("llm_provider"),
        cfg.get("llm_api_key"),
        cfg.get("llm_base_url"),
    )
    llm_model = cfg.get("llm_model") or "gpt-4o"

    return await SearchOrchestrator.run(query, config, llm_client, llm_model)


def _maybe_build_llm_client(
    provider: str, api_key: str, base_url: str
) -> Optional[Any]:
    """Return an AsyncOpenAI client only for a real (non-mock) OpenAI-compatible
    provider. Returns None for mock/no-key → orchestrator skips LLM-native."""
    if provider not in ("openai", "custom"):
        return None
    if not api_key:
        return None
    import httpx
    from openai import AsyncOpenAI
    return AsyncOpenAI(
        api_key=api_key,
        base_url=base_url or None,
        timeout=httpx.Timeout(60.0, connect=10.0),
    )


def _to_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")
