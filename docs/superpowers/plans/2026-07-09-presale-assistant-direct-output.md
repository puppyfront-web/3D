# 售前问答助手「直出成品」改造 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把售前问答助手从「给指导性建议」改造成「直接产出可用成品」——节点对话直出成品 + 一键采纳、全局问答搜后直接答、意图松绑、搜索词智能化。

**Architecture:** 方案 A「旁路预检索」——在调 LLM 之前先用智能改写的 query 调一次 `acquire_web_context`，把 web 命中塞进 system prompt，再让 LLM 流式生成成品。不引入 LLM tool-calling，复用现有 `fill_canvas` 写回范式与 `visual-concept-actions` 按钮模式。节点对话用一次流式 LLM 调用产出成品正文（= `text_delta`），缺料时在正文末尾用固定标记 `【还需你提供】` 列出，流结束后正则切分为结构化 `node_draft` block。

**Tech Stack:** 后端 FastAPI + SQLAlchemy async + pytest；前端 Next.js + TypeScript + Tailwind。

**Spec:** [docs/superpowers/specs/2026-07-09-presale-assistant-direct-output-design.md](../specs/2026-07-09-presale-assistant-direct-output-design.md)

## Global Constraints

- **后端测试运行位置**：在 `apps/api` 目录下运行 pytest：`cd apps/api && pytest app/tests/<file>::<test> -v`（项目用 conftest fixtures：`db_session`、`canvas_project_with_version`、`stub_llm` 等）。
- **前端检查**：在 `apps/web` 下运行 `pnpm typecheck` 与 `pnpm lint`（若无 pnpm，用项目已有的 npm/yarn 等价脚本）。
- **前端 Next.js 警告**：`apps/web/AGENTS.md` 指出本项目 Next.js 有 breaking changes——写前端代码前先读 `node_modules/next/dist/docs/` 里相关文档，遵循其约定与弃用提示。
- **不引入 LLM tool-calling**：联网一律走 `acquire_web_context` 旁路预检索。
- **引用可追溯、不得编造**：所有面向用户的 LLM 输出保留 `GLOBAL_CAPABILITY_CONSTRAINT` 的反编造约束；成品中基于搜索/资料的部分要在 sources 标注。
- **测试断言口径**：成品文案不得含「建议 / 应该 / 可以提炼 / 需要考虑」式空话（照搬 `test_canvas_orchestrator.py:236` 的断言写法）。
- **每个任务结束都 commit**，commit message 用 `feat`/`refactor`/`test` 前缀。
- **不动**：`canvas_agent_orchestrator.py` 的 fill_canvas 管线、Skill 路由架构、Conversation 数据模型。
- **语言**：所有面向用户的 prompt 与文案用中文；代码注释跟随周围风格（中英混用即可）。

## File Structure

**后端（apps/api）— 修改：**
- `app/services/search_helper.py` — 加 `context_hint` 参数 + `_rewrite_query`，做搜索词智能改写。
- `app/services/conversation_service.py` — `_handle_node_edit` 重写为直出成品 + 联网 + 发 `node_draft`；`_CONVERSATION_SYSTEM_PROMPT` 重写；`_handle_conversational` 加搜后直答。
- `app/services/react_intent.py` + `app/services/intent_service.py` — `conversational` 定义去掉「修改建议」。
- `app/routers/canvas.py` — 新增 `POST /projects/{pid}/nodes/{nid}/adopt` 接口。

**后端（apps/api）— 新建测试：**
- `app/tests/test_search_rewrite.py` — Task 1。
- `app/tests/test_node_edit_direct_output.py` — Task 2。
- `app/tests/test_node_adopt.py` — Task 3。
- `app/tests/test_conversational_search.py` — Task 4。
- `app/tests/test_intent_relaxed.py` — Task 5。

**后端（apps/api）— schema：**
- `app/schemas/canvas.py` — 加 `NodeAdoptIn` 请求体。

**前端（apps/web）— 修改：**
- `lib/canvas-api.ts` — 加 `adoptNode` client。
- `components/canvas/conversation-panel.tsx` — `renderContentBlock` 加 `node_draft` 分支 + 接收 `projectId`/`onNodeAdopted`；`ConversationPanel` 新增 `onNodeAdopted` prop。

**前端（apps/web）— 新建：**
- `components/canvas/node-draft-block.tsx` — 渲染成品预览 + 「采纳到节点」按钮。

---

## Task 1: 搜索词智能改写（`acquire_web_context` + `context_hint`）

**Files:**
- Modify: `apps/api/app/services/search_helper.py`
- Test: `apps/api/app/tests/test_search_rewrite.py`

**Interfaces:**
- Produces: `acquire_web_context(db, query, max_results=5, context_hint=None)` — 新增可选 `context_hint: Optional[str]`。当提供时，先调一次 LLM `generate_json` 把 `(query, context_hint)` 改写成单个精准搜索词，再喂给 provider 链；改写失败则降级用原 `query`。

- [ ] **Step 1: Write the failing test**

Create `apps/api/app/tests/test_search_rewrite.py`:

```python
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

    async def fake_llm():
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

    async def failing_llm():
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

    async def fake_llm():
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && pytest app/tests/test_search_rewrite.py -v`
Expected: FAIL — `acquire_web_context() got an unexpected keyword argument 'context_hint'` (or `get_llm_service` not imported).

- [ ] **Step 3: Implement the rewrite**

Replace the whole content of `apps/api/app/services/search_helper.py` with:

```python
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

Task 1 (售前直出成品): adds optional ``context_hint`` — when provided, the raw
query is first rewritten by a single LLM call into a sharper search term, so
node-scoped / conversational searches are not bound to a fixed template.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def _rewrite_query(
    db: Optional[AsyncSession], raw_query: str, context_hint: str
) -> str:
    """Rewrite (raw_query, context_hint) into one sharp search term via LLM.

    Never raises — on any failure returns ``raw_query`` so the caller keeps
    working (search must never break the conversation).
    """
    if not context_hint or not context_hint.strip():
        return raw_query
    try:
        from app.services.llm_service import get_llm_service

        llm = await get_llm_service(db)
        result = await llm.generate_json(
            prompt=(
                f"用户输入：{raw_query}\n"
                f"上下文：{context_hint}\n"
                "请把以上信息改写成一个最精准、最适合用于网络搜索的中文搜索词"
                "（不要问句、不要解释、不要引号）。只输出 JSON：{\"query\": string}"
            ),
            system_prompt="你是搜索词优化助手，只输出 JSON。",
            temperature=0.2,
        )
        q = (result.get("query") or "").strip() if isinstance(result, dict) else ""
        return q or raw_query
    except Exception as e:  # noqa: BLE001 — degrade, never crash
        logger.warning("_rewrite_query failed (%s); using raw query.", e)
        return raw_query


async def acquire_web_context(
    db: Optional[AsyncSession],
    query: str,
    max_results: int = 5,
    context_hint: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Single entry point for web search context acquisition.

    When ``context_hint`` is provided (node title + user ask + material
    summary), the query is first rewritten by one LLM call into a sharper
    search term (Task 1). Returns ``(web_hits, summary)``.

    - ``web_hits``: normalised hit dicts (title / url / domain / snippet /
      published_at / source_type / confidence).
    - ``summary``: the ``external_search_summary`` dict carrying
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

    rewritten = await _rewrite_query(db, query, context_hint) if context_hint else query

    try:
        from app.services.search import search as run_search

        result = await run_search(db, rewritten, extra_config={"max_results": max_results})
    except Exception as e:
        # The search service is designed not to raise, but guard anyway so a
        # caller is never broken by a search failure.
        logger.warning("acquire_web_context: search failed for %r: %s", rewritten, e)
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && pytest app/tests/test_search_rewrite.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/services/search_helper.py apps/api/app/tests/test_search_rewrite.py
git commit -m "feat(search): acquire_web_context 支持 context_hint 智能改写搜索词"
```

---

## Task 2: 节点对话 `_handle_node_edit` 直出成品 + 联网 + `node_draft`

**Files:**
- Modify: `apps/api/app/services/conversation_service.py:1340-1433`（`_handle_node_edit`）
- Test: `apps/api/app/tests/test_node_edit_direct_output.py`

**Interfaces:**
- Consumes: Task 1 的 `acquire_web_context(db, query, max_results=5, context_hint=None)`。
- Produces: 节点对话 SSE 流末尾新增一个 `node_draft` block，形状：
  ```json
  {"type": "node_draft", "data": {
    "planning": ["成品正文段落..."],
    "pending_questions": ["还需用户提供的具体项..."],
    "sources": [{"type": "web_search", "name": "...", "quote": "..."}]
  }}
  ```
  供 Task 3（adopt）与 Task 7（前端渲染）消费。

- [ ] **Step 1: Write the failing test**

Create `apps/api/app/tests/test_node_edit_direct_output.py`:

```python
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
```

> Note: the helper `_obj_async` lets `await get_llm_service(db)` resolve to the fake `_FakeLLM` instance. If the import path of `get_llm_service` inside `conversation_service` differs, adjust the `monkeypatch.setattr(cs, "get_llm_service", ...)` target to match the name actually imported at module top.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && pytest app/tests/test_node_edit_direct_output.py -v`
Expected: FAIL — system_prompt still contains advisory instructions / no `node_draft` emitted.

- [ ] **Step 3: Rewrite `_handle_node_edit`**

Open `apps/api/app/services/conversation_service.py`. At the top of the file, ensure these imports exist (add any missing):

```python
from app.services.search_helper import acquire_web_context
```

(The module already imports `get_llm_service`, `re`, `json`, `uuid`.)

Then replace the entire `_handle_node_edit` method (currently lines ~1340-1433) with:

```python
    async def _handle_node_edit(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
        user_message: str,
        node_id: str,
        history: List[Dict[str, str]],
        thread_id: uuid.UUID,
    ) -> AsyncGenerator[str, None]:
        """Handle a node-scoped conversation (PRD §15) — DIRECT-OUTPUT mode.

        Loads the node's current content + sources + a web-search pass, then
        asks the LLM — streaming — to WRITE the finished copy for THIS single
        node (not advise on how to write it). The streamed body is shown to
        the user as-is; after streaming we split out an optional
        「【还需你提供】」tail into pending questions and emit a structured
        ``node_draft`` block so the UI can offer a one-click 「采纳到节点」.

        Per product decision (单节点隔离 + AI 直出成品 → 用户一键采纳):
          - Reply IS the finished node copy; the user adopts it via the
            adopt endpoint (Task 3) when satisfied — we do NOT write here.
          - Only the current node is in scope.
        """
        from app.services.canvas_service import canvas_service

        try:
            node = await canvas_service.get_node(db, uuid.UUID(node_id))
        except Exception:
            logger.exception("node_edit: failed to load node %s", node_id)
            yield f"data: {json.dumps({'type': 'text_delta', 'text': '无法加载该节点，请返回全局对话后重试。'}, ensure_ascii=False)}\n\n"
            return

        if not node:
            yield f"data: {json.dumps({'type': 'text_delta', 'text': '未找到该节点，可能已被删除。'}, ensure_ascii=False)}\n\n"
            return

        node_title = node.title or node.node_key or "该节点"
        content = node.content or {}
        planning = content.get("planning", []) or []
        extracted = content.get("extracted", []) or []
        pending = content.get("pending_questions", []) or []
        sources = node.sources or []
        sources_brief = (
            ", ".join(
                f"{s.source_name or s.source_type}({s.confidence or '—'})"
                for s in sources[:5]
            )
            or "（暂无来源）"
        )

        # ── Task 1: web-search pass with a context-aware rewritten query ──
        context_hint = f"画布节点：{node_title}；用户要求：{user_message}；已有资料：{self._fmt_slot(extracted)}"
        web_hits: List[Dict[str, Any]] = []
        web_summary: Dict[str, Any] = {}
        try:
            web_hits, web_summary = await acquire_web_context(
                db, user_message, max_results=5, context_hint=context_hint
            )
        except Exception:
            logger.exception("node_edit: web search failed for node %s; continuing without.", node_id)

        web_block = (
            "（无网络命中）"
            if not web_hits
            else "\n".join(
                f"- {h.get('title') or h.get('domain')}：{(h.get('snippet') or '').strip()[:120]}"
                for h in web_hits[:5]
            )
        )

        # ── Build the node-edit system prompt (direct-output, not advisory) ──
        context_block = (
            f"当前节点：{node_title}\n\n"
            f"【已有资料提取】\n{self._fmt_slot(extracted)}\n\n"
            f"【已有策划内容】\n{self._fmt_slot(planning)}\n\n"
            f"【待确认项】\n{self._fmt_slot(pending)}\n\n"
            f"【信息来源】{sources_brief}\n\n"
            f"【网络搜索命中】\n{web_block}\n"
        )
        system_prompt = (
            "你是花生ONE 售前文案撰写助手。用户正在「节点级对话」中，要你为画布上的单个节点撰写内容。\n"
            "硬性约束：\n"
            "1. 只为「当前节点」撰写内容，绝不要涉及其它节点。\n"
            "2. 直接输出该节点可用的成品售前文案——也就是用户采纳后能直接写进节点的内容。"
            "不要输出「建议这样写」「应该包含 X」「需要考虑 Y」之类的元指导或方法论。\n"
            "3. 不得使用「建议、应该、可以提炼、需要考虑」等空泛建议措辞；写就是了。\n"
            "4. 内容要基于【已有资料提取】和【网络搜索命中】。引用必须可追溯、不得编造；"
            "基于网络命中的内容即视为来自网络搜索，基于已有资料的视为来自用户资料。\n"
            "5. 只有当关键信息确实缺失、必须用户客观提供时，才在成品正文最末尾另起一段，"
            "以「【还需你提供】」为标题，每行一项列出具体缺失项及其用途，例如：\n"
            "   【还需你提供】\n"
            "   - 营业执照上的成立时间：用于企业简介基础信息\n"
            "   - 主营业务的具体描述：用于准确表述业务范围\n"
            "   若无缺失，不要输出该段。\n"
            "6. 若用户要的内容明显超出该节点范围（涉及多个板块），在正文开头用一句话提示"
            "「这超出本节点范围，建议在全局对话处理」，然后仍尽量给出本节点能写的部分。\n"
            f"\n{context_block}"
        )

        thinking_text = f"正在结合资料与联网搜索为节点「{node_title}」撰写内容…"
        yield f"data: {json.dumps({'type': 'thinking_delta', 'text': thinking_text}, ensure_ascii=False)}\n\n"

        llm = await get_llm_service(db)
        full_text = ""
        async for chunk in llm.generate_with_history_stream(
            messages=history,
            system_prompt=system_prompt,
            temperature=0.5,
        ):
            full_text += chunk
            yield f"data: {json.dumps({'type': 'text_delta', 'text': chunk}, ensure_ascii=False)}\n\n"

        # ── Split finished copy vs pending-questions tail, emit node_draft ──
        planning_items, pending_items = self._split_node_draft(full_text)
        draft_sources = [
            {
                "type": "web_search",
                "name": h.get("title") or h.get("domain") or "网络来源",
                "quote": (h.get("snippet") or "").strip()[:200],
            }
            for h in web_hits[:3]
        ]
        node_draft = {
            "type": "node_draft",
            "data": {
                "planning": planning_items,
                "pending_questions": pending_items,
                "sources": draft_sources,
            },
        }
        yield f"data: {json.dumps(node_draft, ensure_ascii=False)}\n\n"

        await self.save_message(
            db, conversation_id, "assistant",
            content=full_text,
            thread_id=thread_id,
            content_type="text",
            metadata={
                "intent": "node_edit",
                "node_id": node_id,
                "node_title": node_title,
                "node_draft": node_draft["data"],
            },
            auto_commit=True,
        )

    @staticmethod
    def _split_node_draft(raw: str) -> tuple:
        """Split streamed copy into (planning_items, pending_questions).

        Anything after the「【还需你提供】」marker is parsed as a bullet list
        of pending questions; the rest is the finished copy, split into
        paragraphs. Always returns two lists (never None).
        """
        marker = "【还需你提供】"
        body, pending_block = raw, ""
        if marker in raw:
            body, _, pending_block = raw.partition(marker)
        planning = [p.strip() for p in body.strip().split("\n\n") if p.strip()]
        pending = []
        for line in pending_block.strip().splitlines():
            item = re.sub(r"^[\s\-•*]+", "", line).strip()
            # drop the trailing "：用途" rationale but keep the asked item readable
            item = item.split("：", 1)[0].strip() if "：" in item else item
            if item:
                pending.append(item)
        return planning, pending
```

Also update the class's docstring/import notes if the old `_handle_node_edit` docstring referenced "advisory text / manual apply" — replace those lines with the direct-output description above (already done in the new method docstring).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && pytest app/tests/test_node_edit_direct_output.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full conversation test suite to check for regressions**

Run: `cd apps/api && pytest app/tests/ -k "conversation or canvas" -v`
Expected: no new failures caused by this change (pre-existing failures unrelated to node_edit are acceptable — note them).

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/services/conversation_service.py apps/api/app/tests/test_node_edit_direct_output.py
git commit -m "feat(node-edit): 节点对话直出成品 + 联网补料 + node_draft block"
```

---

## Task 3: 「采纳到节点」后端接口

**Files:**
- Modify: `apps/api/app/schemas/canvas.py`（加 `NodeAdoptIn`）
- Modify: `apps/api/app/routers/canvas.py`（加 adopt 接口）
- Test: `apps/api/app/tests/test_node_adopt.py`

**Interfaces:**
- Consumes: `canvas_service.update_node(db, project_id, node_id, content=..., status=...)`、`canvas_service.get_node`、`NodeSource` model（`app.models.canvas`）。
- Produces: `POST /api/v1/projects/{pid}/nodes/{nid}/adopt`，body 为 `NodeAdoptIn`，返回更新后的 `CanvasNodeOut`。前端 Task 6/7 调用它。

- [ ] **Step 1: Write the failing test**

Create `apps/api/app/tests/test_node_adopt.py`:

```python
"""Task 3: adopt endpoint merges draft into the node, sets filled, writes a NodeSource."""
import pytest
import uuid


@pytest.mark.asyncio
async def test_adopt_writes_merged_content_status_filled_and_source(
    db_session, canvas_project_with_version
):
    # canvas_project_with_version yields (project_id, version_id) — see conftest.
    project_id, version_id = canvas_project_with_version
    from sqlalchemy import select
    from app.models.canvas import CanvasNode, Canvas, NodeSource

    # Pick the company_profile node created by the fixture.
    node = (
        await db_session.execute(
            select(CanvasNode)
            .join(Canvas, CanvasNode.canvas_id == Canvas.id)
            .where(Canvas.project_version_id == version_id)
            .where(CanvasNode.node_key == "company_profile")
        )
    ).scalar_one()
    # Pre-existing ui_suggestion must be preserved on adopt.
    node.content = {"extracted": ["旧事实"], "planning": [], "ui_suggestion": ["保留我"], "pending_questions": []}
    await db_session.flush()

    from app.services.canvas_adopt_service import adopt_node_draft

    updated = await adopt_node_draft(
        db_session,
        project_id=project_id,
        node_id=node.id,
        planning=["XX科技专注智能制造，成立于2010年。"],
        pending_questions=["营业执照上的成立时间"],
        sources=[{"type": "web_search", "name": "公司官网", "quote": "成立于2010年"}],
    )

    assert updated.status == "filled"
    assert updated.content["planning"] == ["XX科技专注智能制造，成立于2010年。"]
    assert updated.content["pending_questions"] == ["营业执照上的成立时间"]
    # ui_suggestion preserved (merge, not blind overwrite).
    assert updated.content["ui_suggestion"] == ["保留我"]
    # A NodeSource row was written.
    srcs = (
        await db_session.execute(select(NodeSource).where(NodeSource.node_id == node.id))
    ).scalars().all()
    assert any(s.source_type == "ai_completed" and s.source_name == "对话采纳" for s in srcs)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && pytest app/tests/test_node_adopt.py -v`
Expected: FAIL — `cannot import name 'adopt_node_draft'` / `canvas_adopt_service` missing.

- [ ] **Step 3: Create the adopt service**

Create `apps/api/app/services/canvas_adopt_service.py`:

```python
"""Task 3: adopt a node-edit draft into the canvas node.

Mirrors the write-back discipline of ``canvas_agent_orchestrator.fill_canvas``:
preserve unchanged slots, overwrite ``planning``/``pending_questions``, set
status=filled, and append a ``NodeSource`` for provenance.
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.canvas import CanvasNode, NodeSource
from app.services.canvas_service import canvas_service

logger = logging.getLogger(__name__)


async def adopt_node_draft(
    db: AsyncSession,
    *,
    project_id: uuid.UUID,
    node_id: uuid.UUID,
    planning: List[str],
    pending_questions: Optional[List[str]] = None,
    extracted: Optional[List[str]] = None,
    sources: Optional[List[Dict[str, Any]]] = None,
) -> CanvasNode:
    """Merge the adopted draft into the node and mark it filled.

    - Keeps the old ``ui_suggestion`` and (unless overridden) ``extracted``.
    - Overwrites ``planning`` and ``pending_questions`` from the draft.
    - Sets status=filled.
    - Appends a ``NodeSource(ai_completed, "对话采纳")`` plus one row per
      ``web_search`` source in ``sources`` for provenance.
    Raises ForbiddenException (via update_node) if the node's version is not
    current or doesn't belong to ``project_id``.
    """
    node = await canvas_service.get_node(db, node_id)
    old = node.content or {}
    merged = {
        "extracted": list(extracted) if extracted is not None else list(old.get("extracted", [])),
        "planning": list(planning),
        "ui_suggestion": list(old.get("ui_suggestion", [])),
        "pending_questions": list(pending_questions) if pending_questions is not None
        else list(old.get("pending_questions", [])),
    }

    updated = await canvas_service.update_node(
        db,
        project_id=project_id,
        node_id=node_id,
        content=merged,
        status="filled",
    )

    # Provenance — primary adopt row.
    db.add(
        NodeSource(
            id=uuid.uuid4(),
            node_id=node.id,
            source_type="ai_completed",
            source_name="对话采纳",
            confidence="medium",
            quote=planning[0] if planning else None,
        )
    )
    for s in sources or []:
        if s.get("type") != "web_search":
            continue
        db.add(
            NodeSource(
                id=uuid.uuid4(),
                node_id=node.id,
                source_type="web_search",
                source_name=s.get("name") or "网络来源",
                confidence="low",
                quote=s.get("quote"),
            )
        )
    await db.flush()
    return updated
```

- [ ] **Step 4: Run the service test to verify it passes**

Run: `cd apps/api && pytest app/tests/test_node_adopt.py -v`
Expected: PASS.

- [ ] **Step 5: Add the request schema and HTTP route**

In `apps/api/app/schemas/canvas.py`, add (next to the other Pydantic models; match the file's existing import of `BaseModel`):

```python
class NodeAdoptIn(APIBaseModel):
    """Body for POST /projects/{pid}/nodes/{nid}/adopt (Task 3)."""
    planning: List[str] = Field(default_factory=list)
    pending_questions: List[str] = Field(default_factory=list)
    extracted: Optional[List[str]] = None
    sources: Optional[List[Dict[str, Any]]] = None
```

(`List`, `Optional`, `Dict`, `Any`, `Field`, `APIBaseModel` are all already imported at the top of `schemas/canvas.py` — no new imports needed.)

In `apps/api/app/routers/canvas.py`, add to the imports near the top:

```python
from app.schemas.canvas import (
    CanvasNodeCreate,
    CanvasNodeOut,
    CanvasNodeUpdate,
    CanvasOut,
    NodeAdoptIn,               # ← add
    ProjectVersionCreate,
    ProjectVersionOut,
    VersionRestoreOut,
)
from app.services.canvas_adopt_service import adopt_node_draft   # ← add
```

Then add this route after the existing `update_node` PATCH route (around line 278):

```python
@router.post(
    "/projects/{project_id}/nodes/{node_id}/adopt",
    response_model=Response[CanvasNodeOut],
)
async def adopt_node(
    project_id: uuid.UUID,
    node_id: uuid.UUID,
    body: NodeAdoptIn,
    db: AsyncSession = Depends(get_db),
):
    """Adopt a node-edit draft (from the node-scoped conversation) into the
    node: merge content, set status=filled, append provenance NodeSources.
    Like PATCH .../nodes/{id}, this does NOT auto-snapshot.
    """
    node = await adopt_node_draft(
        db,
        project_id=project_id,
        node_id=node_id,
        planning=body.planning,
        pending_questions=body.pending_questions,
        extracted=body.extracted,
        sources=body.sources,
    )
    await db.commit()
    node = await canvas_service.get_node(db, node_id)
    return Response(data=_to_node_out(node), message="已采纳到节点")
```

- [ ] **Step 6: Run router-level smoke + type check**

Run: `cd apps/api && pytest app/tests/test_node_adopt.py -v`
Expected: PASS.

Verify the route is wired (no import errors at app startup):
Run: `cd apps/api && python -c "from app.routers import canvas; print([r.path for r in canvas.router.routes if 'adopt' in r.path])"`
Expected: prints `['/projects/{project_id}/nodes/{node_id}/adopt']`.

- [ ] **Step 7: Commit**

```bash
git add apps/api/app/services/canvas_adopt_service.py apps/api/app/schemas/canvas.py apps/api/app/routers/canvas.py apps/api/app/tests/test_node_adopt.py
git commit -m "feat(canvas): 采纳节点对话成品到节点（adopt 接口 + 合并写回 + 溯源）"
```

---

## Task 4: 全局问答 `_handle_conversational` 搜后直接答

**Files:**
- Modify: `apps/api/app/services/conversation_service.py`（`_CONVERSATION_SYSTEM_PROMPT` 常量 + `_handle_conversational` 方法）
- Test: `apps/api/app/tests/test_conversational_search.py`

**Interfaces:**
- Consumes: Task 1 的 `acquire_web_context(db, query, max_results=5, context_hint=None)`。
- Produces: conversational 路径现在会先搜后答；system prompt 去掉顾问口吻。

- [ ] **Step 1: Locate `_handle_conversational`**

Run: `cd apps/api && grep -n "_handle_conversational" app/services/conversation_service.py`
Expected: shows the method definition and its call sites. Read that method to see its current signature and body (it currently just calls `generate_with_history_stream` with `_CONVERSATION_SYSTEM_PROMPT`).

- [ ] **Step 2: Write the failing test**

Create `apps/api/app/tests/test_conversational_search.py`:

```python
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd apps/api && pytest app/tests/test_conversational_search.py -v`
Expected: FAIL — conversational path doesn't call `acquire_web_context` yet.

- [ ] **Step 4: Rewrite the system prompt and the handler**

In `apps/api/app/services/conversation_service.py`, replace the `_CONVERSATION_SYSTEM_PROMPT` constant (lines ~22-38) with:

```python
# System prompt for conversational mode — direct answers, not advice.
_CONVERSATION_SYSTEM_PROMPT = """你是花生ONE 展厅+文旅 售前问答助手。

回答原则：
1. 能直接回答就直接回答，专业、具体、落地。不要用「建议你考虑…」「你可以去…」式空话。
2. 用户问的是事实/区别/参数/方案思路时，基于【网络搜索命中】和已有上下文直接作答，并在行内简述依据。
3. 如果缺少关键信息（场地面积、屏幕尺寸、预算、工期等）才能给出确切结论，明确告诉用户「为了给你准确结论，我还需要：X、Y（具体）」，而不是泛泛地建议。
4. 不要编造案例、报价、屏幕参数或工期；不承诺最终投屏效果。
5. 涉及以下领域：3D 展示幕墙、裸眼 3D、LED 媒体立面；展厅设计与展陈规划；文旅项目策划（夜游、沉浸式、光影秀）；多媒体展项设计（互动装置、数字沙盘、AR/VR）。
""" + GLOBAL_CAPABILITY_CONSTRAINT
```

Then replace the entire `_handle_conversational` method (currently `conversation_service.py:1271-1338`). The current implementation uses a `rich_stream = getattr(llm, "generate_with_history_stream_rich", None)` branch (real thinking trace) with a fallback to plain `generate_with_history_stream` — **preserve that structure**; the only changes are (a) a web-search pass before streaming, (b) folding the hits into the system prompt, and (c) using the local `system_prompt` variable instead of the bare constant. Replace the method with:

```python
    async def _handle_conversational(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
        user_message: str,
        history: List[Dict[str, str]],
    ) -> AsyncGenerator[str, None]:
        """Handle conversational intent with streaming LLM response.

        Task 4: searches the web first when the user asks a real question
        (not a greeting / tiny message), then answers directly with the hits
        folded into the system prompt. Preserves the rich-stream thinking
        trace + fallback behaviour of the original.
        """
        llm = await get_llm_service(db)
        full_text = ""

        # ── Task 4: web-search pass for real questions (skip greetings/tiny) ──
        msg = (user_message or "").strip()
        web_hits: List[Dict[str, Any]] = []
        if msg and not self._is_social_greeting(msg) and len(msg) >= 4:
            try:
                web_hits, _ = await acquire_web_context(
                    db, msg, max_results=5, context_hint=msg
                )
            except Exception:
                logger.exception("conversational: web search failed; continuing.")

        system_prompt = _CONVERSATION_SYSTEM_PROMPT
        if web_hits:
            web_block = "\n".join(
                f"- {h.get('title') or h.get('domain')}：{(h.get('snippet') or '').strip()[:120]}"
                for h in web_hits[:5]
            )
            system_prompt = (
                system_prompt
                + f"\n\n【网络搜索命中】（回答时可引用，标注来自网络）\n{web_block}\n"
            )

        rich_stream = getattr(llm, "generate_with_history_stream_rich", None)

        yield f"data: {json.dumps({'type': 'thinking_delta', 'text': '正在检索网络信息…' if web_hits else '正在理解你的问题并组织回复…'}, ensure_ascii=False)}\n\n"

        if rich_stream is not None:
            got_real_thinking = False
            first_content_sent = False
            async for kind, text in rich_stream(
                messages=history,
                system_prompt=system_prompt,
                temperature=0.7,
            ):
                if kind == "thinking":
                    if not got_real_thinking:
                        got_real_thinking = True
                    yield f"data: {json.dumps({'type': 'thinking_delta', 'text': text}, ensure_ascii=False)}\n\n"
                else:
                    if not first_content_sent:
                        first_content_sent = True
                        if not got_real_thinking:
                            yield f"data: {json.dumps({'type': 'thinking_delta', 'text': '已理解需求，正在组织回复…'}, ensure_ascii=False)}\n\n"
                    full_text += text
                    yield f"data: {json.dumps({'type': 'text_delta', 'text': text}, ensure_ascii=False)}\n\n"
        else:
            async for chunk in llm.generate_with_history_stream(
                messages=history,
                system_prompt=system_prompt,
                temperature=0.7,
            ):
                full_text += chunk
                yield f"data: {json.dumps({'type': 'text_delta', 'text': chunk}, ensure_ascii=False)}\n\n"

        # Save complete assistant message
        await self.save_message(
            db, conversation_id, "assistant",
            content=full_text,
            content_type="text",
            metadata={"intent": "conversational"},
            auto_commit=True,
        )
```

The method signature `(self, db, conversation_id, user_message, history)` and all 5 call sites (lines 646/663/718/922 + the `rich_stream` comment at 797) are unchanged.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd apps/api && pytest app/tests/test_conversational_search.py -v`
Expected: 2 PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/services/conversation_service.py apps/api/app/tests/test_conversational_search.py
git commit -m "feat(chat): 全局问答搜后直接答，去掉顾问口吻"
```

---

## Task 5: 意图识别松绑（`conversational` 重新定义）

**Files:**
- Modify: `apps/api/app/services/react_intent.py:41`
- Modify: `apps/api/app/services/intent_service.py:191`
- Test: `apps/api/app/tests/test_intent_relaxed.py`

**Interfaces:**
- Produces: `conversational` intent now covers free-form questions, not just "修改建议".

- [ ] **Step 1: Write the failing test**

Create `apps/api/app/tests/test_intent_relaxed.py`:

```python
"""Task 5: conversational intent definition no longer says '修改建议' and
covers free-form presales questions."""
import inspect
from app.services import react_intent, intent_service


def test_react_intent_definition_relaxed():
    src = inspect.getsource(react_intent)
    assert "修改建议" not in src
    assert "自由提问" in src or "问答" in src


def test_intent_service_definition_relaxed():
    src = inspect.getsource(intent_service)
    assert "修改建议" not in src
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && pytest app/tests/test_intent_relaxed.py -v`
Expected: FAIL — both files still contain "修改建议".

- [ ] **Step 3: Update both definitions**

In `apps/api/app/services/react_intent.py:41`, change:
```text
- "conversational": 闲聊、追问、解释、修改建议
```
to:
```text
- "conversational": 问答、咨询、解释、闲聊、追问、各类自由提问
```

In `apps/api/app/services/intent_service.py:191`, change:
```text
- "conversational": 闲聊、追问、解释、修改建议
```
to:
```text
- "conversational": 问答、咨询、解释、闲聊、追问、各类自由提问
```

(Use `Edit` with the exact old string for each file. Do not change anything else in those prompts.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && pytest app/tests/test_intent_relaxed.py -v`
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/services/react_intent.py apps/api/app/services/intent_service.py apps/api/app/tests/test_intent_relaxed.py
git commit -m "refactor(intent): 松绑 conversational 定义，覆盖自由问答"
```

---

## Task 6: 前端 `adoptNode` client

**Files:**
- Modify: `apps/web/lib/canvas-api.ts`
- (前端无单元测试设施；用类型检查 + lint 保证。)

**Interfaces:**
- Consumes: Task 3 的 `POST /api/v1/projects/{pid}/nodes/{nid}/adopt`。
- Produces: `adoptNode(projectId, nodeId, body)` 给 Task 7 用。

- [ ] **Step 1: Add the client method**

In `apps/web/lib/canvas-api.ts`, after the existing `updateNode` function (around line 154), add:

```typescript
/** Adopt a node-edit draft (from the node-scoped conversation) into the node.
 * Backend: POST /api/v1/projects/{pid}/nodes/{nid}/adopt (Task 3). */
export interface NodeAdoptInput {
  planning: string[];
  pending_questions?: string[];
  extracted?: string[];
  sources?: Array<{ type: string; name?: string; quote?: string }>;
}

export async function adoptNode(
  projectId: string,
  nodeId: string,
  body: NodeAdoptInput,
): Promise<ApiResponse<CanvasNode>> {
  return canvasFetch<CanvasNode>(
    `/api/v1/projects/${projectId}/nodes/${nodeId}/adopt`,
    { method: "POST", body: JSON.stringify(body) },
  );
}
```

- [ ] **Step 2: Type check + lint**

Run: `cd apps/web && pnpm typecheck && pnpm lint`
Expected: no errors (adjust the command if the project uses npm/yarn — check `apps/web/package.json` scripts).

- [ ] **Step 3: Commit**

```bash
git add apps/web/lib/canvas-api.ts
git commit -m "feat(web): 新增 adoptNode client（采纳节点对话成品）"
```

---

## Task 7: 前端 `node_draft` 渲染 + 「采纳到节点」按钮

**Files:**
- Create: `apps/web/components/canvas/node-draft-block.tsx`
- Modify: `apps/web/components/canvas/conversation-panel.tsx`
- Modify: `apps/web/app/workspace/canvas/[projectId]/page.tsx`（把刷新回调传给 panel）

**Interfaces:**
- Consumes: Task 6 的 `adoptNode`；`chat-api.ts` 已自动把 `node_draft` 收进 `richContent.blocks`（无需改 chat-api）。
- Produces: 节点对话的 AI 回复下方显示成品预览 + 「采纳到节点」按钮，点击采纳并刷新画布。

- [ ] **Step 1: Read the Next.js doc per AGENTS.md**

Per `apps/web/AGENTS.md`, before writing client component code, read the relevant guide under `node_modules/next/dist/docs/` (client components / hooks). Heed any deprecation notices that affect `"use client"` components and `fetch` usage.

- [ ] **Step 2: Create `NodeDraftBlock`**

Create `apps/web/components/canvas/node-draft-block.tsx`:

```tsx
"use client";

// Renders the structured node_draft emitted by the node-scoped conversation
// (backend _handle_node_edit, Task 2) and offers a one-click 「采纳到节点」
// that POSTs to the adopt endpoint (Task 3) via adoptNode (Task 6).

import { useState } from "react";
import { Check, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { adoptNode } from "@/lib/canvas-api";

export interface NodeDraftData {
  planning: string[];
  pending_questions?: string[];
  sources?: Array<{ type: string; name?: string; quote?: string }>;
}

export function NodeDraftBlock({
  projectId,
  nodeId,
  data,
  onAdopted,
}: {
  projectId: string;
  nodeId: string;
  data: NodeDraftData;
  onAdopted?: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [adopted, setAdopted] = useState(false);

  async function handleAdopt() {
    if (busy || adopted) return;
    setBusy(true);
    const res = await adoptNode(projectId, nodeId, {
      planning: data.planning,
      pending_questions: data.pending_questions,
      sources: data.sources,
    });
    setBusy(false);
    if (res.success) {
      setAdopted(true);
      toast.success("已采纳到节点");
      onAdopted?.();
    } else {
      toast.error(res.message ?? "采纳失败，请重试");
    }
  }

  const pending = data.pending_questions ?? [];
  const sources = data.sources ?? [];

  return (
    <div className="rounded-lg border border-primary/30 bg-primary-fixed/40 p-3 space-y-2">
      <div className="flex items-center gap-1.5 text-[10px] text-primary font-semibold uppercase tracking-wider">
        <Check className="h-3 w-3" />
        已生成节点内容
      </div>
      <div className="text-xs text-on-surface whitespace-pre-wrap space-y-2">
        {data.planning.map((p, i) => (
          <p key={i}>{p}</p>
        ))}
      </div>
      {pending.length > 0 ? (
        <div className="text-xs text-tertiary">
          <div className="font-semibold mb-1">为补全本节点，还需要你提供：</div>
          <ul className="space-y-1">
            {pending.map((q, i) => (
              <li key={i}>• {q}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {sources.length > 0 ? (
        <div className="text-[10px] text-outline">
          来源：{sources.map((s) => s.name || s.type).join("、")}
        </div>
      ) : null}
      <button
        onClick={handleAdopt}
        disabled={busy || adopted}
        className="w-full mt-1 inline-flex items-center justify-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-semibold text-primary-fill disabled:opacity-60 hover:opacity-90"
      >
        {busy ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <Check className="h-3.5 w-3.5" />
        )}
        {adopted ? "已采纳" : "采纳到节点"}
      </button>
    </div>
  );
}
```

- [ ] **Step 3: Wire it into `renderContentBlock`**

In `apps/web/components/canvas/conversation-panel.tsx`:

1. Add the import near the other component imports (after the `CompanyAnalysisCard` import):
```typescript
import { NodeDraftBlock, type NodeDraftData } from "@/components/canvas/node-draft-block";
```

2. Change the `renderContentBlock` signature so callers can pass node context. Find `function renderContentBlock(block: ContentBlock, key: string) {` and change it to:
```typescript
function renderContentBlock(
  block: ContentBlock,
  key: string,
  ctx?: { projectId?: string; activeNodeId?: string | null; onNodeAdopted?: () => void },
) {
```

3. Add a `node_draft` branch right after the `plan_progress` branch (before the fallback):
```typescript
  if (block.type === "node_draft") {
    const draft = (block.data ?? {}) as unknown as NodeDraftData;
    if (ctx?.projectId && ctx?.activeNodeId) {
      return (
        <NodeDraftBlock
          key={key}
          projectId={ctx.projectId}
          nodeId={ctx.activeNodeId}
          data={draft}
          onAdopted={ctx.onNodeAdopted}
        />
      );
    }
    return null;
  }
```

4. Update the call site inside `AssistantMessage`. Change `function AssistantMessage({ message }: { message: ChatMessage }) {` to also accept context:
```typescript
function AssistantMessage({
  message,
  ctx,
}: {
  message: ChatMessage;
  ctx?: { projectId?: string; activeNodeId?: string | null; onNodeAdopted?: () => void };
}) {
```
and change the blocks map line to pass `ctx`:
```typescript
{blocks.map((block, index) => renderContentBlock(block, `${message.id}-${index}`, ctx))}
```

5. In the `ConversationPanel` component body, find where `AssistantMessage` is rendered for persisted messages (search the JSX for `<AssistantMessage`). Pass `ctx={{ projectId, activeNodeId, onNodeAdopted }}`. Also do the same for the streaming assistant bubble if it renders blocks via `renderContentBlock` — search for `streamingBlocks.map` and pass the same `ctx`.

6. Add `onNodeAdopted` to the `ConversationPanel` props. Find the props destructure:
```typescript
export function ConversationPanel({
  projectId,
  initialPrompt,
  activeNodeId,
  activeNodeTitle,
  onClearNode,
}: {
  projectId: string;
  initialPrompt?: string;
  activeNodeId?: string | null;
  activeNodeTitle?: string;
  onClearNode?: () => void;
}) {
```
and extend it with the new optional callback:
```typescript
export function ConversationPanel({
  projectId,
  initialPrompt,
  activeNodeId,
  activeNodeTitle,
  onClearNode,
  onNodeAdopted,
}: {
  projectId: string;
  initialPrompt?: string;
  activeNodeId?: string | null;
  activeNodeTitle?: string;
  onClearNode?: () => void;
  /** Called after a node draft is adopted, so the canvas can reload. */
  onNodeAdopted?: () => void;
}) {
```

- [ ] **Step 4: Pass a refresh callback from the canvas page**

The canvas page already has a `loadCurrent` useCallback (defined at `apps/web/app/workspace/canvas/[projectId]/page.tsx:182`) that re-fetches the current canvas via `getCurrentCanvas(projectId)` and re-`hydrate`s the canvas store. Reuse it as the adopt-refresh callback — no new function needed.

In `apps/web/app/workspace/canvas/[projectId]/page.tsx:556`, extend the existing `<ConversationPanel>` JSX with the new prop:

```tsx
      <ConversationPanel
        projectId={projectId}
        initialPrompt={initialPrompt}
        activeNodeId={conversationNodeId}
        activeNodeTitle={activeNodeTitle}
        onClearNode={() => setConversationNode(null)}
        onNodeAdopted={() => loadCurrent()}
      />
```

`loadCurrent` takes an optional `{ keepSelection?: boolean }`; calling it with no args reloads the canvas from the current version, so the adopted node's content/status refreshes on screen.

- [ ] **Step 5: Type check + lint**

Run: `cd apps/web && pnpm typecheck && pnpm lint`
Expected: no errors. Fix any unused-import or type issues introduced.

- [ ] **Step 6: Manual smoke test**

Start the app (per project convention) and verify:
1. Open a project canvas, click a node (e.g. 企业简介) to enter node-scoped chat.
2. Ask "帮我补充这个节点".
3. Confirm the reply is finished copy (not「建议这样写」) and shows a 「采纳到节点」 button + optional「还需要你提供」list.
4. Click 采纳 → confirm a success toast and the node content/status updates on the canvas.

- [ ] **Step 7: Commit**

```bash
git add apps/web/components/canvas/node-draft-block.tsx apps/web/components/canvas/conversation-panel.tsx apps/web/app/workspace/canvas/[projectId]/page.tsx
git commit -m "feat(web): node_draft 成品预览 + 一键采纳到节点"
```

---

## 收尾：全量自检

- [ ] **Step 1: 全量后端测试**

Run: `cd apps/api && pytest app/tests/ -v`
Expected: 本次新增的 5 个测试文件全绿；记录任何与本次改动无关的既有失败。

- [ ] **Step 2: 前端类型检查 + lint**

Run: `cd apps/web && pnpm typecheck && pnpm lint`
Expected: 通过。

- [ ] **Step 3: 人工验收（对照 spec 验收标准）**

逐条核对 [spec 验收标准](../specs/2026-07-09-presale-assistant-direct-output-design.md#验收标准) 7 条。重点：
- 节点对话直出成品，不再「教你写」。
- 采纳按钮可用，节点 status=filled、有溯源。
- 缺料时给出具体「还需你提供」清单。
- 全局问答直接答，联网生效。
- 自由问答落到 conversational。

- [ ] **Step 4: 提交收尾（如有未提交的修复）**

仅在前面步骤有额外修复时执行：
```bash
git add -A
git commit -m "test: 收尾修复 + 全量自检通过"
```
