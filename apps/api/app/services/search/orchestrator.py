"""Search orchestrator — runs the provider precedence chain.

Resolution order (first that can run wins):
  1. Tavily — if `web_search_tavily_api_key` is configured
  2. LLM-native — if a real (non-mock) LLM is configured; uses its web_search tool
  3. Degraded — returns status="failed" with a notice, never raises

A failed upstream provider triggers the next in the chain, so a Tavily timeout
falls through to the LLM-native provider automatically. The final degraded state
is surfaced to the caller as a result (not an exception) so the company_analysis
pipeline keeps running — objective fields are marked “未核实” instead.

Mode overrides (`web_search_mode`):
  auto       — full chain (default)
  tavily     — Tavily only, no fallback
  llm_native — LLM-native only, no Tavily
  disabled   — returns failed immediately (feature off)
"""

import logging
from typing import Any, Optional

from app.services.search.base import SearchProvider, WebSearchResult
from app.services.search.tavily_provider import TavilySearchProvider

logger = logging.getLogger(__name__)


class SearchOrchestrator:
    """Builds the active provider chain from runtime config and runs a query."""

    @staticmethod
    def build_chain(
        mode: str,
        tavily_api_key: str,
        llm_client: Any,
        llm_model: str,
    ) -> list:
        """Return the ordered list of providers to try, per mode.

        Providers are lazy: a Tavily provider with no key self-reports
        unavailable and is skipped at run time.
        """
        chain: list = []

        if mode == "disabled":
            return chain

        tavily = TavilySearchProvider(tavily_api_key) if tavily_api_key else None
        llm_native = _LLMNativeAdapter(llm_client, llm_model) if llm_client else None

        if mode == "tavily":
            if tavily:
                chain.append(tavily)
            return chain
        if mode == "llm_native":
            if llm_native:
                chain.append(llm_native)
            return chain

        # auto: Tavily first, LLM-native second
        if tavily:
            chain.append(tavily)
        if llm_native:
            chain.append(llm_native)
        return chain

    @staticmethod
    async def run(
        query: str,
        config: dict,
        llm_client: Any,
        llm_model: str,
    ) -> WebSearchResult:
        """Execute the precedence chain for one query.

        config keys: mode, tavily_api_key, max_results, timeout, min_confidence
        llm_client: AsyncOpenAI instance, or None if LLM provider is mock
        """
        mode = config.get("mode", "auto")
        max_results = int(config.get("max_results", 5))
        timeout = int(config.get("timeout", 15))
        min_confidence = float(config.get("min_confidence", 0.5))

        chain = SearchOrchestrator.build_chain(
            mode, config.get("tavily_api_key", ""), llm_client, llm_model
        )

        if not chain:
            logger.info("web_search: no provider available (mode=%s)", mode)
            return WebSearchResult(
                query=query, status="failed", provider="none",
                degraded_reason="no_provider",
            )

        last_result: Optional[WebSearchResult] = None
        for provider in chain:
            result = await provider.search(
                query=query,
                max_results=max_results,
                timeout=timeout,
                min_confidence=min_confidence,
            )
            # ok → done; failed/degraded → try next provider if any
            if result.status == "ok":
                return result
            last_result = result
            logger.info(
                "web_search provider %s returned %s (%s), trying next",
                provider.name, result.status, result.degraded_reason,
            )

        # Exhausted chain — return the last (best) degraded/failed result
        return last_result or WebSearchResult(
            query=query, status="failed", provider="none",
            degraded_reason="all_providers_failed",
        )


class _LLMNativeAdapter(SearchProvider):
    """Thin adapter that wraps llm_native_provider without a hard import cycle.

    We construct the real LLMNativeSearchProvider lazily so that importing this
    module doesn't require the OpenAI client to be available.
    """

    name = "llm_native"

    def __init__(self, client: Any, model: str):
        self._client = client
        self._model = model

    async def search(self, query, max_results=5, timeout=15, min_confidence=0.5):
        from app.services.search.llm_native_provider import LLMNativeSearchProvider
        provider = LLMNativeSearchProvider(self._client, self._model)
        return await provider.search(query, max_results, timeout, min_confidence)
