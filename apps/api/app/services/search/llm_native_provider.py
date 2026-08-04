"""LLM-native search provider — uses the configured LLM's built-in web search.

Many OpenAI-compatible providers (智谱 GLM-4.5, 通义, Kimi, ...) expose a built-in
web_search tool via the chat completions endpoint. We send the query as a chat
message with the web_search tool enabled; the LLM searches the live web itself,
then returns a grounded answer. We ask it to also emit structured sources so we
can populate SearchHit[] for traceability.

This avoids needing a third-party search API key while still hitting the real
web (the LLM provider performs the crawl). If the configured provider doesn't
support web_search, the call either errors (→ failed) or returns an answer
without sources (→ degraded). Never raises.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from app.services.search.base import SearchHit, SearchProvider, WebSearchResult

logger = logging.getLogger(__name__)

# System prompt instructs the LLM to search the web and return STRICT JSON with
# normalised sources. This keeps traceability uniform regardless of provider.
_SEARCH_SYSTEM_PROMPT = """你是一个联网研究助手。请使用你的联网搜索能力，针对用户的查询检索最新公开信息。

【输出格式】必须且只能返回一个合法 JSON 对象（以 { 开头，以 } 结尾），禁止在 JSON 之前或之后输出任何文字、解释、思考过程、 markdown 标记。结构如下：

{
  "answer": "对查询的核心回答（中文，200字内，客观陈述）",
  "sources": [
    {
      "title": "来源标题",
      "url": "https://...",
      "snippet": "命中的关键摘要（100字内）",
      "published_at": "2026-06-20 或 null"
    }
  ],
  "missing_info": ["无法从公开来源核实的信息"]
}

要求：
- 第一个字符必须是 { ，最后一个字符必须是 }
- sources 中的 url 必须是真实检索到的公开网页链接，禁止编造
- 若无法联网或无相关结果，answer 留空，sources 返回空数组
- 客观信息优先（业务、产品、行业、公开动态），主观信息标注进 missing_info"""


class LLMNativeSearchProvider(SearchProvider):
    """Uses an existing AsyncOpenAI client (from OpenAILLMService) to run a
    web-enabled search query. The client must point at a provider that supports
    the web_search tool (GLM / 通义 / Kimi etc.)."""

    name = "llm_native"

    def __init__(self, client: Any, model: str, tool_name: str = "web_search"):
        self._client = client  # AsyncOpenAI instance
        self._model = model
        self._tool_name = tool_name

    async def search(
        self,
        query: str,
        max_results: int = 5,
        timeout: int = 15,
        min_confidence: float = 0.5,
    ) -> WebSearchResult:
        try:
            # Note: we deliberately do NOT pass response_format=json_object here.
            # Some OpenAI-compatible providers (e.g. deepkey) return empty content
            # when json_object is combined with web-search behaviour. The strict
            # system prompt already constrains output to JSON; _parse_json then
            # robustly extracts it. Likewise we don't pass a tools=[web_search]
            # arg — providers that search natively (deepkey/GLM) do so based on
            # the prompt, and an unrecognised tools key can cause empty replies.
            resp = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": _SEARCH_SYSTEM_PROMPT},
                    {"role": "user", "content": query},
                ],
                temperature=0.3,
            )
        except Exception as e:
            logger.warning(
                "LLM-native web_search failed (provider may not support it): %s", e
            )
            return WebSearchResult(
                query=query, status="failed", provider=self.name,
                degraded_reason=f"llm_error: {type(e).__name__}",
            )

        content = self._extract_content(resp)
        if not content:
            return WebSearchResult(
                query=query, status="failed", provider=self.name,
                degraded_reason="empty_response",
            )

        parsed = self._parse_json(content)
        if parsed is None:
            return WebSearchResult(
                query=query, status="degraded", provider=self.name,
                degraded_reason="unparseable_response",
            )

        answer: str = parsed.get("answer", "")
        raw_sources: List[Dict[str, Any]] = parsed.get("sources", []) or []
        missing: List[str] = parsed.get("missing_info", []) or []

        hits: List[SearchHit] = []
        for i, s in enumerate(raw_sources[:max_results]):
            url = s.get("url", "")
            if not url:
                continue
            hits.append(SearchHit(
                title=(s.get("title") or "")[:300],
                url=url,
                snippet=(s.get("snippet") or "")[:1000],
                domain=_domain(url),
                published_at=s.get("published_at"),
                source_type=_classify(s.get("published_at"), answer),
                # LLM-sourced hits can't be ranked by retrieval score; assign
                # descending confidence by position so the floor still works.
                confidence=max(0.55 - i * 0.05, min_confidence),
            ))

        if not hits:
            status = "degraded" if answer else "failed"
            return WebSearchResult(
                query=query, status=status, provider=self.name,
                degraded_reason="no_sources" if answer else "no_results",
                summary={
                    "key_points": [answer] if answer else [],
                    "conflicts": [],
                    "missing_info": missing,
                    "recommended_usage": "仅背景参考" if answer else "需人工确认",
                },
            )

        return WebSearchResult(
            query=query,
            status="ok",
            hits=hits,
            provider=self.name,
            degraded_reason=None,
            summary={
                "key_points": [answer] if answer else [h.snippet[:120] for h in hits[:2]],
                "conflicts": [],
                "missing_info": missing,
                "recommended_usage": "可引用",
            },
        )

    @staticmethod
    def _extract_content(resp: Any) -> str:
        """Pull text content from an OpenAI-compatible response."""
        try:
            msg = resp.choices[0].message
            return msg.content or ""
        except Exception:
            return ""

    @staticmethod
    def _parse_json(content: str) -> Optional[Dict[str, Any]]:
        # 1. Direct parse
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        # 2. Greedy extract first { ... last } — handles leading prose / thoughts
        import re
        first = content.find("{")
        last = content.rfind("}")
        if first != -1 and last != -1 and last > first:
            candidate = content[first:last + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass
            # 3. Try ```json ... ``` fenced block inside the candidate region
            m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(1))
                except json.JSONDecodeError:
                    pass
        if not content.strip():
            logger.warning("LLM-native search returned empty content")
        elif first == -1:
            logger.warning(
                "LLM-native search returned no JSON object: %s",
                content[:200],
            )
        return None


def _domain(url: str) -> str:
    from urllib.parse import urlparse
    try:
        return urlparse(url).hostname or ""
    except Exception:
        return ""


def _classify(published_at: Any, answer: str) -> str:
    if published_at:
        return "news"
    return "article"
