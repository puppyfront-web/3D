"""Task 2: node-scoped conversation emits a finished draft, not advisory text."""
import json
import pytest
import uuid


def _parse_sse(chunk: str):
    assert chunk.startswith("data: ")
    return json.loads(chunk[len("data: "):].strip())


class _FakeNode:
    def __init__(self):
        self.id = uuid.uuid4()
        self.title = "企业简介"
        self.node_key = "company_profile"
        self.content = {"extracted": ["现有事实A"], "planning": [], "ui_suggestion": [], "pending_questions": []}
        self.sources = []


@pytest.mark.asyncio
async def test_node_edit_emits_node_draft_and_no_advisory(monkeypatch):
    from app.services import conversation_service as cs

    captured = {"system_prompt": ""}

    # 1) Fake node load.
    async def fake_get_node(db, node_id):
        return _FakeNode()

    from app.services import canvas_service as canvas_svc
    monkeypatch.setattr(canvas_svc.canvas_service, "get_node", fake_get_node)

    # 2) Fake web search — no context, just return one hit.
    async def fake_acquire(db, query, max_results=5, context_hint=None):
        return ([{"title": "公司官网", "domain": "example.com", "snippet": "成立于2010年"}], {"status": "ok"})
    monkeypatch.setattr(cs, "acquire_web_context", fake_acquire)

    # 3) Fake LLM — stream finished copy that CONTAINS the marker so we can
    #    assert pending-splitting, and is NOT advisory.
    async def fake_stream(messages, system_prompt=None, temperature=0.7):
        captured["system_prompt"] = system_prompt or ""
        for piece in ["XX科技是一家专注智能制造的企业，成立于2010年。",
                      "\n\n【还需你提供】\n- 营业执照上的成立时间\n- 主营业务具体描述"]:
            yield piece

    class _FakeLLM:
        def generate_with_history_stream(self, messages, system_prompt=None, temperature=0.7):
            return fake_stream(messages, system_prompt, temperature)

    monkeypatch.setattr(cs, "get_llm_service", lambda db=None: _obj_async(_FakeLLM()))

    # 4) Stub save_message (DB not available in this unit test).
    async def fake_save(self, db, conv_id, role, **kw):
        return None
    monkeypatch.setattr(cs.ConversationService, "save_message", fake_save)

    svc = cs.ConversationService.__new__(cs.ConversationService)
    chunks = []
    async for c in svc._handle_node_edit(
        db=None, conversation_id=uuid.uuid4(), user_message="帮我补充企业简介",
        node_id=str(_FakeNode().id), history=[], thread_id=uuid.uuid4(),
    ):
        chunks.append(_parse_sse(c))

    # system_prompt must NOT instruct advisory output.
    sp = captured["system_prompt"]
    assert "输出修改建议" not in sp
    assert "指出当前内容的不足" not in sp
    assert "直接" in sp and "成品" in sp

    # A node_draft block must be emitted.
    drafts = [c for c in chunks if c.get("type") == "node_draft"]
    assert len(drafts) == 1
    data = drafts[0]["data"]
    assert data["planning"] and "XX科技" in data["planning"][0]
    assert "营业执照上的成立时间" in data["pending_questions"]
    assert any(s["type"] == "web_search" for s in data["sources"])

    # Planning must read as finished copy, not advisory text.
    joined = "".join(data["planning"])
    assert "建议" not in joined and "应该" not in joined


async def _obj_async(obj):
    """Awaitable wrapper returning obj — matches `await get_llm_service(db)`."""
    return obj
