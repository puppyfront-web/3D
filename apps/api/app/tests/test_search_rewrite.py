"""Task 1: acquire_web_context rewrites the query via LLM when context_hint is given."""
import pytest


@pytest.mark.asyncio
async def test_acquire_rewrites_query_with_context_hint(monkeypatch):
    from app.services import search_helper

    captured = {}

    class _FakeHit:
        def to_dict(self):
            return {"title": "t", "url": "u", "snippet": "s"}

    class _FakeResult:
        hits = [_FakeHit()]
        status = "ok"
        provider = "fake"
        degraded_reason = None
        summary = {}

    async def fake_run_search(db, query, extra_config=None):
        captured["query"] = query
        return _FakeResult()

    async def fake_llm(db=None):
        class _LLM:
            async def generate_json(self, prompt, system_prompt=None, temperature=0.3):
                return {"query": "智造科技 公司简介 主营业务 成立时间"}
        return _LLM()

    monkeypatch.setattr(search_helper, "get_llm_service", fake_llm)
    # search_helper imports run_search lazily inside the function:
    import app.services.search as search_mod
    monkeypatch.setattr(search_mod, "search", fake_run_search)

    await search_helper.acquire_web_context(
        db=object(), query="帮我补充企业简介节点", context_hint="节点：企业简介；用户问：帮我补充"
    )
    assert captured["query"] == "智造科技 公司简介 主营业务 成立时间"


@pytest.mark.asyncio
async def test_acquire_falls_back_to_raw_query_when_rewrite_fails(monkeypatch):
    from app.services import search_helper

    captured = {}

    class _FakeResult:
        hits = []
        status = "ok"
        provider = "fake"
        degraded_reason = None
        summary = {}

    async def fake_run_search(db, query, extra_config=None):
        captured["query"] = query
        return _FakeResult()

    async def failing_llm(db=None):
        raise RuntimeError("llm down")

    monkeypatch.setattr(search_helper, "get_llm_service", failing_llm)
    import app.services.search as search_mod
    monkeypatch.setattr(search_mod, "search", fake_run_search)

    await search_helper.acquire_web_context(
        db=object(), query="原始问题", context_hint="some hint"
    )
    # Rewrite raised → must degrade to the raw query, never crash.
    assert captured["query"] == "原始问题"


@pytest.mark.asyncio
async def test_acquire_without_context_hint_skips_rewrite(monkeypatch):
    from app.services import search_helper

    rewrite_called = {"n": 0}
    captured = {}

    class _FakeResult:
        hits = []
        status = "ok"
        provider = "fake"
        degraded_reason = None
        summary = {}

    async def fake_run_search(db, query, extra_config=None):
        captured["query"] = query
        return _FakeResult()

    async def fake_llm(db=None):
        rewrite_called["n"] += 1
        class _LLM:
            async def generate_json(self, *a, **kw):
                return {"query": "should-not-be-used"}
        return _LLM()

    monkeypatch.setattr(search_helper, "get_llm_service", fake_llm)
    import app.services.search as search_mod
    monkeypatch.setattr(search_mod, "search", fake_run_search)

    await search_helper.acquire_web_context(db=object(), query="裸眼3D")
    assert rewrite_called["n"] == 0
    assert captured["query"] == "裸眼3D"
