"""SearchOrchestrator precedence-chain tests (PRD §13 web_search, AGENT_SPEC §2.3).

The chain is Tavily → LLM-native → degraded. A failed/missing provider must
fall through to the next; the final degraded state is returned as a result,
never raised. These tests pin that contract with stub providers so they don't
depend on network or API keys.
"""

import pytest

from app.services.search.base import WebSearchResult
from app.services.search.orchestrator import SearchOrchestrator


class _StubProvider:
    """Minimal provider stub: returns a canned WebSearchResult."""

    def __init__(self, name: str, result: WebSearchResult):
        self.name = name
        self._result = result
        self.calls = 0

    async def search(self, query, max_results=5, timeout=15, min_confidence=0.5):
        self.calls += 1
        return self._result


def _ok(provider: str, n: int = 1):
    return WebSearchResult(
        query="q", status="ok", provider=provider,
        hits=[{"title": f"hit-{provider}-{i}", "url": f"https://x/{i}"} for i in range(n)],
    )


def _fail(provider: str, reason: str = "boom"):
    return WebSearchResult(query="q", status="failed", provider=provider, degraded_reason=reason)


@pytest.mark.asyncio
async def test_first_provider_ok_short_circuits(monkeypatch):
    """Tavily ok → LLM-native never tried."""
    tavily = _StubProvider("tavily", _ok("tavily", 2))
    llm = _StubProvider("llm_native", _ok("llm_native"))
    monkeypatch.setattr(
        SearchOrchestrator, "build_chain",
        staticmethod(lambda mode, key, client, model: [tavily, llm]),
    )
    res = await SearchOrchestrator.run("q", {"mode": "auto"}, None, "")
    assert res.status == "ok" and res.provider == "tavily"
    assert tavily.calls == 1 and llm.calls == 0


@pytest.mark.asyncio
async def test_failed_provider_falls_through(monkeypatch):
    """Tavily fails → LLM-native runs and its ok result wins."""
    tavily = _StubProvider("tavily", _fail("tavily"))
    llm = _StubProvider("llm_native", _ok("llm_native", 3))
    monkeypatch.setattr(
        SearchOrchestrator, "build_chain",
        staticmethod(lambda mode, key, client, model: [tavily, llm]),
    )
    res = await SearchOrchestrator.run("q", {"mode": "auto"}, None, "")
    assert res.status == "ok" and res.provider == "llm_native"
    assert tavily.calls == 1 and llm.calls == 1


@pytest.mark.asyncio
async def test_all_providers_fail_returns_last_degraded(monkeypatch):
    """Whole chain fails → last result returned, no exception."""
    tavily = _StubProvider("tavily", _fail("tavily", "timeout"))
    llm = _StubProvider("llm_native", _fail("llm_native", "no_tool"))
    monkeypatch.setattr(
        SearchOrchestrator, "build_chain",
        staticmethod(lambda mode, key, client, model: [tavily, llm]),
    )
    res = await SearchOrchestrator.run("q", {"mode": "auto"}, None, "")
    assert res.status == "failed"
    assert res.provider == "llm_native"  # last attempted
    assert res.degraded_reason == "no_tool"


@pytest.mark.asyncio
async def test_disabled_mode_returns_no_provider():
    """mode=disabled → empty chain → failed/no_provider, never raises."""
    res = await SearchOrchestrator.run("q", {"mode": "disabled"}, None, "")
    assert res.status == "failed"
    assert res.provider == "none"
    assert res.degraded_reason == "no_provider"


@pytest.mark.asyncio
async def test_build_chain_skips_providers_without_credentials():
    """build_chain drops Tavily when no api_key and LLM-native when no client."""
    chain = SearchOrchestrator.build_chain("auto", "", None, "")
    assert chain == [], "no key + no client → empty chain (degrades at run time)"
    # Tavily-only mode with a key includes just Tavily.
    chain = SearchOrchestrator.build_chain("tavily", "key123", None, "")
    assert len(chain) == 1 and chain[0].name == "tavily"


@pytest.mark.asyncio
async def test_tavily_parses_response(monkeypatch):
    """With a key + a successful Tavily response, hits are normalised with
    domain + confidence. Verifies the request payload shape too."""
    from app.services.search.tavily_provider import TavilySearchProvider

    captured = {}

    class _FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "answer": "AI 概要",
                "results": [
                    {"title": "华为官网", "url": "https://www.huawei.com",
                     "content": "全球领先ICT", "score": 0.9,
                     "published_date": "2024-01-01"},
                ],
            }

    class _FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None):
            captured["url"] = url
            captured["payload"] = json
            return _FakeResp()

    monkeypatch.setattr("app.services.search.tavily_provider.httpx.AsyncClient", _FakeClient)

    provider = TavilySearchProvider("key-123")
    assert provider.available is True
    result = await provider.search("华为", max_results=3)

    # Request shape: correct endpoint, key + query + max_results carried.
    assert captured["url"] == "https://api.tavily.com/search"
    assert captured["payload"]["api_key"] == "key-123"
    assert captured["payload"]["query"] == "华为"
    assert captured["payload"]["max_results"] == 3

    # Result normalised: ok status, one hit with domain + confidence.
    assert result.status == "ok"
    assert len(result.hits) == 1
    hit = result.hits[0]
    assert hit.title == "华为官网"
    assert hit.domain == "www.huawei.com"
    assert hit.confidence == 0.9


@pytest.mark.asyncio
async def test_tavily_degrades_on_http_error(monkeypatch):
    """A Tavily HTTP error → failed status (not raised) → orchestrator can
    fall through to the next provider."""
    from app.services.search.tavily_provider import TavilySearchProvider

    class _FakeResp:
        def raise_for_status(self):
            raise Exception("HTTP 500")

        def json(self):
            return {}

    class _FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None):
            return _FakeResp()

    monkeypatch.setattr("app.services.search.tavily_provider.httpx.AsyncClient", _FakeClient)
    result = await TavilySearchProvider("key-123").search("华为")
    assert result.status == "failed"
    assert result.provider == "tavily"
    assert "provider_error" in (result.degraded_reason or "")
