"""Task 4: conversational path searches the web then answers directly."""
import json
import pytest
import uuid


def _parse_sse(chunk: str):
    assert chunk.startswith("data: ")
    return json.loads(chunk[len("data: "):].strip())


@pytest.mark.asyncio
async def test_conversational_searches_then_answers(monkeypatch):
    from app.services import conversation_service as cs

    search_called = {"n": 0}
    captured = {"system_prompt": ""}

    async def fake_acquire(db, query, max_results=5, context_hint=None):
        search_called["n"] += 1
        return ([{"title": "裸眼3D百科", "snippet": "裸眼3D是…"}], {"status": "ok"})
    monkeypatch.setattr(cs, "acquire_web_context", fake_acquire)

    async def fake_stream(messages, system_prompt=None, temperature=0.7):
        captured["system_prompt"] = system_prompt or ""
        yield "裸眼3D是不戴眼镜就能看到立体效果的显示技术。"
    class _FakeLLM:
        def generate_with_history_stream(self, messages, system_prompt=None, temperature=0.7):
            return fake_stream(messages, system_prompt, temperature)
    async def fake_get_llm(db=None):
        return _FakeLLM()
    monkeypatch.setattr(cs, "get_llm_service", fake_get_llm)

    async def fake_save(self, db, conv_id, role, **kw):
        return None
    monkeypatch.setattr(cs.ConversationService, "save_message", fake_save)

    svc = cs.ConversationService.__new__(cs.ConversationService)
    chunks = []
    async for c in svc._handle_conversational(
        db=None, conversation_id=uuid.uuid4(),
        user_message="裸眼3D 和 LED 媒体立面有什么区别？", history=[],
    ):
        chunks.append(_parse_sse(c))

    # A real question must trigger a search.
    assert search_called["n"] == 1
    # New prompt must drop the consultant tone.
    sp = captured["system_prompt"]
    assert "推荐用户使用技能卡片" not in sp
    assert "建议下一步操作" not in sp


@pytest.mark.asyncio
async def test_conversational_skips_search_for_greetings(monkeypatch):
    from app.services import conversation_service as cs

    search_called = {"n": 0}
    async def fake_acquire(db, query, max_results=5, context_hint=None):
        search_called["n"] += 1
        return [], {"status": "ok"}
    monkeypatch.setattr(cs, "acquire_web_context", fake_acquire)

    async def fake_stream(messages, system_prompt=None, temperature=0.7):
        yield "你好！有什么可以帮你的？"
        return
    class _FakeLLM:
        def generate_with_history_stream(self, messages, system_prompt=None, temperature=0.7):
            return fake_stream(messages, system_prompt, temperature)
    async def fake_get_llm(db=None):
        return _FakeLLM()
    monkeypatch.setattr(cs, "get_llm_service", fake_get_llm)
    async def fake_save(self, db, conv_id, role, **kw):
        return None
    monkeypatch.setattr(cs.ConversationService, "save_message", fake_save)

    svc = cs.ConversationService.__new__(cs.ConversationService)
    async for _ in svc._handle_conversational(
        db=None, conversation_id=uuid.uuid4(), user_message="你好", history=[],
    ):
        pass
    assert search_called["n"] == 0
