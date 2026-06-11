"""Regression tests for agent-streamed content persistence.

Bug (repro: 切换其他对话框回来就会变成这样):
  The proposal / visual-concept agent flows stream real content to the live
  frontend via SSE, but persist only a placeholder string
  ("[proposal context saved]" / "[visual concept context saved]") as the
  assistant message `content`, with the real output only in `metadata`.
  On conversation reload (switch away and come back) the frontend reads
  `message.content` and renders the raw placeholder.

Fix invariant: "what the user saw during streaming == what survives reload".
The persisted assistant message must carry the real streamed text + content
blocks as `content` / `rich_content`, mirroring the frontend's own collection
logic (apps/web/lib/chat-api.ts streamChat `done` handler).
"""

import json

import pytest


def _accumulator():
    # Lazy import so the integration test can run (and fail) against code that
    # does not yet define the accumulator.
    from app.services.conversation_service import _StreamAccumulator

    return _StreamAccumulator()


# ---------------------------------------------------------------------------
# Unit: the accumulator must mirror the frontend's SSE collection logic
# ---------------------------------------------------------------------------


def _sse(chunk_type: str, text=None, data=None) -> str:
    payload = {"type": chunk_type}
    if text is not None:
        payload["text"] = text
    if data is not None:
        payload["data"] = data
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


class TestStreamAccumulator:
    def test_collects_proposal_chunks(self):
        """A proposal generate turn: text deltas + proposal_section content
        block + skill_progress + action_buttons must all be captured."""
        acc = _accumulator()
        for chunk in [
            _sse("text_delta", text="正在生成策划案…"),
            _sse("skill_progress", data={"skill_id": "proposal_generation", "status": "running"}),
            _sse("content_block_start", data={"block_type": "proposal_section"}),
            _sse(
                "content_block_data",
                data={
                    "type": "proposal_section",
                    "data": {"content": "# 策划案正文", "used_cases": ["case-1"]},
                },
            ),
            _sse("content_block_end"),
            _sse("action_buttons", data={"buttons": [{"label": "确认策划案"}]}),
            _sse("done"),
        ]:
            acc.feed(chunk)

        # text_delta accumulated into content
        assert acc.text == "正在生成策划案…"
        # blocks mirror what the frontend renders
        types = [b.get("type") for b in acc.blocks]
        assert "proposal_section" in types
        assert "skill_progress" in types
        assert "action_buttons" in types
        # structural events are NOT collected as blocks
        assert "content_block_start" not in types
        assert "content_block_end" not in types
        assert "done" not in types
        # proposal_section block keeps its data (used_cases for 引用来源)
        proposal = next(b for b in acc.blocks if b.get("type") == "proposal_section")
        assert proposal["data"]["used_cases"] == ["case-1"]
        assert acc.rich_content == {"blocks": acc.blocks}

    def test_collects_visual_chunks(self):
        acc = _accumulator()
        for chunk in [
            _sse("visual_strategy", data={"style": "赛博科技风"}),
            _sse("visual_result", data={"image_url": "https://img/x.png"}),
            _sse("quality_check", data={"items": []}),
            _sse("action_buttons", data={"buttons": []}),
            _sse("done"),
        ]:
            acc.feed(chunk)

        types = [b.get("type") for b in acc.blocks]
        assert types == ["visual_strategy", "visual_result", "quality_check", "action_buttons"]
        assert acc.text == ""

    def test_empty_when_only_structural(self):
        acc = _accumulator()
        for chunk in [_sse("content_block_start"), _sse("done")]:
            acc.feed(chunk)
        assert acc.text == ""
        assert acc.blocks == []
        assert acc.rich_content is None

    def test_ignores_malformed(self):
        acc = _accumulator()
        acc.feed("not an sse line")
        acc.feed("data: {not json}")
        acc.feed(_sse("text_delta", text="ok"))
        assert acc.text == "ok"

    def test_error_text_not_collected(self):
        """Frontend routes `error` to onError, never into the message body."""
        acc = _accumulator()
        acc.feed(_sse("error", text="boom"))
        acc.feed(_sse("text_delta", text="real"))
        assert acc.text == "real"
        assert acc.blocks == []


# ---------------------------------------------------------------------------
# Handler-level: the agent handlers must persist real streamed content, so a
# conversation reload (get_history — what "切换其他对话框回来" reads) returns the
# real content, never a placeholder string.
# ---------------------------------------------------------------------------


async def _drain(gen):
    """Consume an async generator fully (the handlers yield SSE chunks)."""
    out = []
    async for chunk in gen:
        out.append(chunk)
    return out


class _StubProposalAgent:
    """Yields a representative proposal generate turn.

    Deliberately does NOT advance ctx to COMPLETED, so the auto-chain to the
    visual agent is skipped — this test isolates the proposal save path.
    """

    def __init__(self, *args, **kwargs):
        pass

    async def handle_message(self, message, ctx, db, project_id=None):
        from app.agents.proposal import _sse_chunk

        yield _sse_chunk("text_delta", text="正在生成策划案…")
        yield _sse_chunk("content_block_start", data={"block_type": "proposal_section"})
        yield _sse_chunk(
            "content_block_data",
            data={
                "type": "proposal_section",
                "data": {"content": "# 策划案正文", "used_cases": ["case-1"]},
            },
        )
        yield _sse_chunk("content_block_end")
        yield _sse_chunk("action_buttons", data={"buttons": [{"label": "确认策划案"}]})
        yield _sse_chunk("done")


class _StubVisualAgent:
    def __init__(self, *args, **kwargs):
        pass

    async def handle_message(self, message, ctx, db, project_id=None):
        from app.agents.visual_concept import _sse_chunk

        yield _sse_chunk("visual_strategy", data={"style": "赛博科技风"})
        yield _sse_chunk("visual_result", data={"image_url": "https://img/x.png"})
        yield _sse_chunk("action_buttons", data={"buttons": []})
        yield _sse_chunk("done")


@pytest.mark.asyncio
async def test_proposal_handler_persists_real_content(db_session, monkeypatch):
    """The proposal agent handler must persist streamed text + proposal_section
    block (with 引用来源 used_cases), not '[proposal context saved]'."""
    import uuid as _uuid

    from app.models.conversation import Conversation
    from app.services.conversation_service import ConversationService

    monkeypatch.setattr("app.agents.proposal.ProposalAgent", _StubProposalAgent)

    conv = Conversation(id=_uuid.uuid4(), title="策划案测试")
    db_session.add(conv)
    await db_session.commit()

    service = ConversationService()
    await _drain(service._handle_proposal_agent(db_session, conv.id, "帮我设计一套完整的展示方案"))

    # RELOAD path — get_history is what the frontend reads after switching back
    messages = await service.get_history(db_session, conv.id)
    assistants = [m for m in messages if m.role == "assistant"]
    assert len(assistants) == 1
    msg = assistants[0]

    assert msg.content == "正在生成策划案…"
    assert msg.content != "[proposal context saved]"
    assert msg.content_type == "rich"
    assert msg.rich_content is not None
    types = [b.get("type") for b in msg.rich_content.get("blocks", [])]
    assert "proposal_section" in types
    assert "action_buttons" in types
    proposal = next(b for b in msg.rich_content["blocks"] if b.get("type") == "proposal_section")
    assert proposal["data"]["used_cases"] == ["case-1"]


@pytest.mark.asyncio
async def test_visual_handler_persists_real_content(db_session, monkeypatch):
    """The visual agent handler must persist streamed blocks (visual_result),
    not '[visual concept context saved]'."""
    import uuid as _uuid

    from app.models.conversation import Conversation
    from app.services.conversation_service import ConversationService

    monkeypatch.setattr("app.agents.visual_concept.VisualConceptAgent", _StubVisualAgent)

    conv = Conversation(id=_uuid.uuid4(), title="视觉测试")
    db_session.add(conv)
    await db_session.commit()

    service = ConversationService()
    await _drain(service._handle_visual_concept(db_session, conv.id, "生成概念图", intent=None))

    messages = await service.get_history(db_session, conv.id)
    assistants = [m for m in messages if m.role == "assistant"]
    assert len(assistants) == 1
    msg = assistants[0]

    assert msg.content != "[visual concept context saved]"
    assert msg.content_type == "rich"
    assert msg.rich_content is not None
    types = [b.get("type") for b in msg.rich_content.get("blocks", [])]
    assert "visual_result" in types
    assert "visual_strategy" in types
