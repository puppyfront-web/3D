"""Tavily search provider — real HTTP calls to https://api.tavily.com.

Tavily is purpose-built for AI agents: it returns title/url/content/score and an
LLM-ready answer. We map its response onto our normalised SearchHit.

API reference: https://docs.tavily.com/documentation/api-reference/endpoint/search
"""

import logging
from typing import Any, Dict, List
from urllib.parse import urlparse

import httpx

from app.services.search.base import SearchHit, SearchProvider, WebSearchResult

logger = logging.getLogger(__name__)

_TAVILY_URL = "https://api.tavily.com/search"


def _domain_from_url(url: str) -> str:
    try:
        host = urlparse(url).hostname or ""
        return host
    except Exception:
        return ""


def _classify_source(domain: str) -> str:
    """Best-effort source_type classification from domain."""
    if not domain:
        return "article"
    # gov / official sites
    if any(d in domain for d in (".gov.", ".gov.cn", ".gov", "gouv.", "gov.uk")):
        return "official"
    # obvious brand / corporate sites (no subdomain like news./blog.)
    first_label = domain.split(".")[0]
    if first_label in {"www", "en", "cn", "zh"}:
        return "official"
    return "article"


class TavilySearchProvider(SearchProvider):
    """Tavily API client. Requires an API key (configured via admin settings)."""

    name = "tavily"

    def __init__(self, api_key: str):
        self._api_key = api_key

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    async def search(
        self,
        query: str,
        max_results: int = 5,
        timeout: int = 15,
        min_confidence: float = 0.5,
    ) -> WebSearchResult:
        if not self.available:
            return WebSearchResult(
                query=query,
                status="failed",
                provider=self.name,
                degraded_reason="no_api_key",
            )

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    _TAVILY_URL,
                    json={
                        "api_key": self._api_key,
                        "query": query,
                        "max_results": max_results,
                        "include_answer": True,
                        "search_depth": "basic",
                    },
                )
                resp.raise_for_status()
                data: Dict[str, Any] = resp.json()
        except httpx.TimeoutException:
            logger.warning("Tavily search timed out for query=%r", query)
            return WebSearchResult(
                query=query, status="failed", provider=self.name,
                degraded_reason="timeout",
            )
        except Exception as e:
            logger.warning("Tavily search failed for query=%r: %s", query, e)
            return WebSearchResult(
                query=query, status="failed", provider=self.name,
                degraded_reason=f"provider_error: {type(e).__name__}",
            )

        raw_results: List[Dict[str, Any]] = data.get("results", []) or []
        answer: str = data.get("answer") or ""

        hits: List[SearchHit] = []
        for r in raw_results:
            url = r.get("url", "")
            domain = _domain_from_url(url)
            # Tavily returns a "score" in [0,1]
            score = float(r.get("score", 0.0))
            hits.append(SearchHit(
                title=r.get("title", "")[:300],
                url=url,
                snippet=(r.get("content") or "")[:1000],
                domain=domain,
                published_at=r.get("published_date"),
                source_type=_classify_source(domain),
                confidence=score,
            ))

        # Apply min-confidence floor
        usable = [h for h in hits if h.confidence >= min_confidence]

        if not usable:
            status = "degraded"
            reason = "low_confidence" if hits else "no_results"
        else:
            status = "ok"
            reason = None

        return WebSearchResult(
            query=query,
            status=status,
            hits=usable or hits,  # keep raw hits even when degraded for context
            summary=self._build_summary(query, answer, usable),
            provider=self.name,
            degraded_reason=reason,
        )

    @staticmethod
    def _build_summary(
        query: str, answer: str, hits: List[SearchHit]
    ) -> Dict[str, Any]:
        """Normalise Tavily's answer + top hits into our summary block."""
        key_points: List[str] = []
        if answer:
            key_points.append(answer.strip())
        # Take first sentence of each top hit snippet as a key point
        for h in hits[:3]:
            first = h.snippet.split("。")[0].split(". ")[0].strip()
            if first and first not in key_points:
                key_points.append(first)
        return {
            "key_points": key_points[:5],
            "conflicts": [],
            "missing_info": [],
            "recommended_usage": "可引用" if hits else "仅背景参考",
        }
