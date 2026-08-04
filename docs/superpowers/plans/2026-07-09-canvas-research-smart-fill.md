# 画布「采集 → 智能归档」实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把售前助手从"搜资料只为自己回答"升级为"搜索 → 整理可见 → 智能归档进画布模块(人确认 + 版本化)→ 生成设计 Brief(复用策划案 skill)",贯通用户输入 → 搜索 → 画像 → Brief 的主流程。

**Architecture:** 一个 `canvas_research_service` 承担三件事——(1) 引擎 `research_and_propose`(ask 模式:搜索 + 一次整理 LLM pass → Proposal,不写库);(2) 派生 `build_fill_proposal_from_canvas`(auto 模式:从 fill_canvas 已写结果读出 Proposal,所见即所写);(3) 写回 `accept_fill_proposal`(创建新 `ProjectVersion` 快照 + 按 node_key 合并节点 + 追加 `NodeSource` 溯源)。三者共用同一 Proposal 形状 + 同一 SSE block `canvas_fill_proposal`。Brief 复用现有 `proposal_generation` skill + 现有 `proposal_section` block。

**Tech Stack:** FastAPI + SQLAlchemy async + pytest(后端 apps/api);Next.js + TypeScript + Tailwind v4 + Material-3 tokens(前端 apps/web,npm,无 typecheck 脚本)。

## 关键事实(Explore 已核实,实现以此为准)

- **版本模型是 `ProjectVersion`,不是 `CanvasVersion`。** 版本 helper:`canvas_service.create_version(db, project_id, version_name=None, change_summary=None, based_on_version_id=None, created_by=None) -> ProjectVersion`(canvas_service.py:262-359)。它自动 demote 同项目其它 `is_current=True`、把 `project.current_version_id` 指向新版本,不 commit(调用方 owning 事务)。
- **`CanvasNode.node_key`** 是稳定标识(models/canvas.py:173)。每板块 7 节点共 21,板/节点标题见 canvas_service.py:45-88 `_DEFAULT_GROUPS`。
- **`CanvasNode.content` 形状**:`{extracted:[], planning:[], ui_suggestion:[], pending_questions:[]}`;`status`: draft→filling→filled|pending_review。
- **`acquire_web_context(db, query, max_results=5, context_hint=None) -> (web_hits, summary)`**(search_helper.py:59-64)。hit 字段:`title/url/snippet/domain/published_at/source_type/confidence`(无 name/source_name)。summary:`status/provider/degraded_reason/key_points/conflicts/missing_info/recommended_usage`。
- **LLMService**:`generate(prompt, system_prompt=None, temperature=0.7, max_tokens=2000) -> str` 与 `generate_json(prompt, system_prompt=None, temperature=0.3) -> Dict`。取实例:`await get_llm_service(db)`。单一 `llm_model` 设置,无快模型开关——本计划一律用 `temperature=0.2`。
- **反编造约束原文**(canvas_agent_orchestrator.py:1050-1057 `_build_planning_prompt` 内):
  > 硬性约束：\n1. 不得补充事实以外的新信息（不新增数据、年份、产品名、客户名等）。\n2. 不得编造、不得使用「建议、应该、可以」等空泛建议措辞。\n3. 某节点事实为空数组时，该节点也返回空数组 []。\n4. 文案是对事实的精炼表达，可以重组语序、突出卖点，但信息量不得超过事实。
- **SSE `node_draft` 是裸顶层对象 yield**(conversation_service.py:1466-1474),非 content_block 三联包。本计划 `canvas_fill_proposal` 沿用裸 yield 范式,前端 chat-api 默认分支自动收。
- **NodeSource**:source_type 取值含 `web_search`/`ai_completed`;confidence 是 String(low/medium/high);字段 node_id/source_type/source_name/quote/confidence/metadata_json。
- **`proposal_generation` skill manifest**:input_schema=`{project_id, requirement_text, template_id, sop_workflow_id}`(无 company_profile_id);chat 模式接收预渲染 `context_pack: str`;输出 proposal_sections/citations/missing_info。从对话调度:`SkillRunner(registry).run_with_react(skill_id, input_data, context)`。
- **前端 ContentBlock.type 是闭合联合**(types/index.ts:673-694,末尾是 `"node_draft"`),加新 block 必须扩联合。`renderContentBlock(block, key, ctx?)` 的 `ctx={projectId?, activeNodeId?, onNodeAdopted?}`(conversation-panel.tsx:120)。`canvasFetch<T>(endpoint, options)` 解 `{success,data,message}` 信封(canvas-api.ts:23)。`loadCurrent()` 刷新画布(page.tsx:182)。

## 与 spec 的 reconciliation(实现决策)

spec 写"一个引擎,三处复用",但字面让 auto 模式也跑引擎 + 再跑 fill_canvas 会导致:(a) 双 LLM pass;(b) 可见 Proposal 与实际写入内容不一致。spec 本意 auto 是"让用户看到**填了什么**"(过去时)。故:
- **auto(首条)**:fill_canvas 照常写(保留 ui_expert/tone/consistency)→ `build_fill_proposal_from_canvas` 从写回结果派生 Proposal → emit。所见=所写,零额外 LLM。
- **ask(后续)**:`research_and_propose` 跑引擎(整理 pass)→ 达门槛才 emit → 用户采纳 → `/fill-accept` → `accept_fill_proposal` 版本化写回。
- **Brief**:复用 `proposal_generation` skill,产物用现有 `proposal_section` block(Brief 即策划案,不新增 design_brief block)。

spec 非目标"不重构 fill_canvas"遵守:新引擎自带反编造约束拷贝,不动 fill_canvas 本体。

## Global Constraints

- **搜索整理结果默认可见**:不再隐形塞 prompt;首条 auto 派生可见、后续 ask 整理后列出。
- **写回前人确认**:ask 模式绝不自动写库;只有首条 auto(fill_canvas 既有行为)和用户点「采纳」(`/fill-accept`)才写。
- **版本化写回**:每次 ask 采纳 `accept_fill_proposal` 创建新 `ProjectVersion` 快照(`canvas_service.create_version`),可回退。auto 首条沿用 fill_canvas 当前版本(其行为本就如此,不改)。
- **可追溯**:每条 web 命中写入时追加 `NodeSource(source_type="web_search")`;Proposal 的 citations 带 url。
- **反编造**:整理 pass 要点无「建议/应该/可以」;断言照搬 test_canvas_orchestrator.py:235 风格。
- **不双重搜索**:`_handle_conversational` 已带 `acquire_web_context`;引擎接受预取 `web_hits` 复用。
- **不写死**:模板/板块/节点从当前画布动态读取,不硬编码 21 节点清单。
- **前端验证命令**:`cd apps/web && node_modules/.bin/tsc --noEmit && npm run lint`(项目用 npm,无 typecheck 脚本)。
- **后端验证命令**:`cd apps/api && pytest app/tests/<file>.py -v`。

---

## 文件结构

**新建:**
- `apps/api/app/services/canvas_research_service.py` — 引擎 + 派生 + 写回 + Proposal 形状 + 反编造常量(单一职责服务)。
- `apps/api/app/tests/test_canvas_research_service.py` — 引擎/派生/写回单测。
- `apps/api/app/tests/test_canvas_fill_proposal_sse.py` — SSE 触发单测(auto/ask/门槛)。
- `apps/api/app/tests/test_canvas_fill_accept.py` — `/fill-accept` 接口单测。
- `apps/api/app/tests/test_canvas_brief.py` — Brief 生成单测。
- `apps/web/components/canvas/canvas-fill-proposal-block.tsx` — Proposal 渲染(auto 只读 / ask 勾选采纳)。

**修改:**
- `apps/api/app/services/conversation_service.py` — `_handle_auto_fill` 派生并 emit Proposal;`_handle_conversational` ask 模式 emit;首条 auto 后 emit Brief。
- `apps/api/app/routers/canvas.py` — 新增 `POST /projects/{pid}/canvas/fill-accept`。
- `apps/api/app/schemas/canvas.py` — 新增 `CanvasFillAcceptIn`。
- `apps/web/types/index.ts` — ContentBlock.type 联合加 `"canvas_fill_proposal"`。
- `apps/web/components/canvas/conversation-panel.tsx` — renderContentBlock 加 canvas_fill_proposal 分支 + ctx 扩 onCanvasAccepted。
- `apps/web/lib/canvas-api.ts` — 加 `acceptCanvasFill(projectId, body)` + 输入接口。
- `apps/web/app/workspace/canvas/[projectId]/page.tsx` — ConversationPanel 传 `onCanvasAccepted={() => loadCurrent()}`。

---

## Task 1: `canvas_research_service` 引擎 + 派生 + Proposal 形状

**Files:**
- Create: `apps/api/app/services/canvas_research_service.py`
- Test: `apps/api/app/tests/test_canvas_research_service.py`

**Interfaces:**
- Consumes: `acquire_web_context`(search_helper.py)、`get_llm_service`(llm_service.py)、`canvas_service.get_current_version` + `get_canvas`、`CanvasNode`/`NodeSource`/`ProjectVersion`(models/canvas.py)、`canvas_service.create_version`。
- Produces:
  - `Proposal` 形状(dict):`{"mode":"auto"|"ask","boards":[{"board_key","board_title","nodes":[{"node_key","node_title","points":[str],"citations":[{"name","url","snippet","type"}],"pending_questions":[str]}]}],"summary":{"key_points":[str],"missing_info":[str]}}`
  - `async def research_and_propose(db, project_id, context_hint, mode="ask", web_hits=None) -> Proposal`(ask 引擎,不写库)
  - `async def build_fill_proposal_from_canvas(db, project_id) -> Proposal`(auto 派生,从当前画布读)
  - `async def accept_fill_proposal(db, project_id, body, user_id=None) -> ProjectVersion`(写回,Task 4 用)
  - `def filter_new_points(proposal, nodes_by_key) -> Proposal`(去重门槛,Task 6 用)

- [ ] **Step 1: 写失败测试**

Create `apps/api/app/tests/test_canvas_research_service.py`:

```python
"""画布「采集→智能归档」引擎/派生/写回 单测。"""
import json
from unittest.mock import AsyncMock, patch

import pytest

from app.services import canvas_research_service as crs
from app.services.canvas_research_service import (
    accept_fill_proposal,
    build_fill_proposal_from_canvas,
    filter_new_points,
    research_and_propose,
)

pytestmark = pytest.mark.asyncio


def _fake_llm_returning(payload: dict):
    """Fake LLM whose generate_json returns the given payload."""
    llm = AsyncMock()
    llm.generate_json = AsyncMock(return_value=payload)
    return llm


async def test_research_and_propose_shape_and_no_advice_words(
    db_session, canvas_project_with_version
):
    """引擎返回 Proposal 形状;要点无「建议/应该/可以」。"""
    project_id, version_id = canvas_project_with_version

    hits = [{
        "title": "甲公司简介", "url": "https://example.com/about",
        "snippet": "甲公司成立于 2015 年，专注裸眼 3D 显示。",
        "domain": "example.com", "published_at": None,
        "source_type": "official", "confidence": 0.9,
    }]
    summary = {"status": "ok", "key_points": ["成立于2015"], "missing_info": []}
    organize_payload = {
        "boards": [{
            "board_key": "company_intro",
            "nodes": [{
                "node_key": "company_profile",
                "points": ["成立于 2015 年，专注裸眼 3D 显示"],
                "citations": [{"name": "甲公司简介", "url": "https://example.com/about",
                               "snippet": "甲公司成立于 2015 年"}],
                "pending_questions": [],
            }],
        }],
        "summary": {"key_points": ["成立于2015"], "missing_info": []},
    }
    fake_llm = _fake_llm_returning(organize_payload)
    with patch.object(crs, "acquire_web_context", AsyncMock(return_value=(hits, summary))), \
         patch.object(crs, "get_llm_service", AsyncMock(return_value=fake_llm)):
        proposal = await research_and_propose(
            db_session, project_id, context_hint="甲公司", mode="ask"
        )
    assert proposal["mode"] == "ask"
    assert proposal["boards"][0]["board_key"] == "company_intro"
    node = proposal["boards"][0]["nodes"][0]
    assert node["node_key"] == "company_profile"
    assert node["node_title"] == "企业简介"  # 从画布补全
    assert node["points"] and "成立于" in node["points"][0]
    assert node["citations"][0]["url"].startswith("http")
    blob = json.dumps(proposal, ensure_ascii=False)
    for w in ("建议", "应该", "可以"):
        assert w not in blob, f"Proposal 含禁词 {w}"


async def test_research_and_propose_uses_prefetched_hits_no_double_search(
    db_session, canvas_project_with_version
):
    """传入 web_hits 时不再触发 acquire_web_context。"""
    project_id, version_id = canvas_project_with_version
    hits = [{"title": "t", "url": "https://x", "snippet": "s", "domain": "x",
             "published_at": None, "source_type": "article", "confidence": 0.5}]
    fake_llm = _fake_llm_returning({"boards": [], "summary": {"key_points": [], "missing_info": []}})
    acq = AsyncMock(return_value=(hits, {"status": "ok", "key_points": [], "missing_info": []}))
    with patch.object(crs, "acquire_web_context", acq), \
         patch.object(crs, "get_llm_service", AsyncMock(return_value=fake_llm)):
        await research_and_propose(db_session, project_id, context_hint="x", mode="ask", web_hits=hits)
    acq.assert_not_awaited()  # 不二次搜索


async def test_research_and_propose_degrades_on_search_failure(
    db_session, canvas_project_with_version
):
    """搜索失败 → 返回空 Proposal,不抛异常。"""
    project_id, version_id = canvas_project_with_version
    with patch.object(crs, "acquire_web_context",
                      AsyncMock(return_value=([], {"status": "failed", "key_points": [], "missing_info": []}))), \
         patch.object(crs, "get_llm_service",
                      AsyncMock(return_value=_fake_llm_returning({"boards": [], "summary": {}}))):
        proposal = await research_and_propose(db_session, project_id, context_hint="x", mode="ask")
    assert proposal["boards"] == []


def test_filter_new_points_drops_duplicates():
    """已有 planning 的要点被过滤;全新要点保留。"""
    class N:
        def __init__(self, planning):
            self.content = {"planning": planning}
    nodes_by_key = {"company_profile": N(["成立于 2015 年，专注裸眼 3D 显示"])}
    proposal = {
        "mode": "ask",
        "boards": [
            {"board_key": "company_intro", "board_title": "企业介绍", "nodes": [
                {"node_key": "company_profile", "node_title": "企业简介",
                 "points": ["成立于 2015 年，专注裸眼 3D 显示", "员工 300 人"],
                 "citations": [], "pending_questions": []},
            ]},
        ],
        "summary": {"key_points": [], "missing_info": []},
    }
    out = filter_new_points(proposal, nodes_by_key)
    kept = out["boards"][0]["nodes"][0]["points"]
    assert kept == ["员工 300 人"]


def test_filter_new_points_empty_when_all_dup():
    class N:
        def __init__(self, planning):
            self.content = {"planning": planning}
    nodes_by_key = {"company_profile": N(["已有要点"])}
    proposal = {
        "mode": "ask", "boards": [
            {"board_key": "company_intro", "board_title": "x", "nodes": [
                {"node_key": "company_profile", "node_title": "x",
                 "points": ["已有要点"], "citations": [], "pending_questions": []}],
            }],
        "summary": {"key_points": [], "missing_info": []},
    }
    out = filter_new_points(proposal, nodes_by_key)
    assert out["boards"] == []  # 全重复 → 清空,上层据此不 emit
```

> **fixture 契约:** `canvas_project_with_version` 已存在于 test_node_adopt.py(也镜像于 test_canvas_orchestrator.py),它依赖 `db_session`,**yield `(project_id: UUID, version_id: UUID)`**。**在每个新测试文件顶部,从 test_node_adopt.py 逐字拷贝** `_make_project_with_canvas`(含其顶部 imports:Role/User/Company/Project/canvas_service/uuid/Tuple 等)与 `canvas_project_with_version` 两个 fixture(沿用上一轮 Task 3 已接受的自包含范式;后续可统一提到 conftest)。测试同时请求 `db_session` 与 `canvas_project_with_version`(同一 function-scope session),用 `db_session` 操作库、用 `project_id`(UUID,非 Project 对象)调服务。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd apps/api && pytest app/tests/test_canvas_research_service.py -v`
Expected: FAIL —— `ModuleNotFoundError: app.services.canvas_research_service`。

- [ ] **Step 3: 实现服务**

Create `apps/api/app/services/canvas_research_service.py`:

```python
"""画布「采集 → 智能归档」服务。

三件事:
  1. research_and_propose —— ask 模式引擎:搜索 + 一次整理 LLM pass → Proposal(不写库)
  2. build_fill_proposal_from_canvas —— auto 模式派生:从当前画布已写结果读出 Proposal
  3. accept_fill_proposal —— 版本化写回:新建 ProjectVersion 快照 + 按 node_key 合并 + NodeSource 溯源

三者共用同一 Proposal 形状,前端同一 SSE block `canvas_fill_proposal`。
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.canvas import CanvasNode, NodeSource, ProjectVersion
from app.services import canvas_service
from app.services.llm_service import get_llm_service
from app.services.search_helper import acquire_web_context

# ---- 反编造约束(逐字拷贝自 fill_canvas _build_planning_prompt,不重构 fill_canvas) ----
_ANTI_FABRICATION_CONSTRAINTS = (
    "硬性约束：\n"
    "1. 不得补充事实以外的新信息（不新增数据、年份、产品名、客户名等）。\n"
    "2. 不得编造、不得使用「建议、应该、可以」等空泛建议措辞。\n"
    "3. 某节点事实为空数组时，该节点也返回空数组 []。\n"
    "4. 文案是对事实的精炼表达，可以重组语序、突出卖点，但信息量不得超过事实。\n"
)

_ORGANIZE_SYSTEM = (
    "你是企业资料整理助手。根据网络搜索命中和企业上下文，把事实要点归类到画布的各个模块节点。"
    "只整理搜索命中中明确出现的事实，不得编造，不得使用「建议/应该/可以」等空泛建议措辞。"
    "每个要点必须能在搜索命中里找到出处；找不到出处的，归到该节点 pending_questions 并标明缺失。"
)

# 规范化要点用于去重(去空白 + 去标点 + 小写)
_PUNCT_RE = re.compile(r"[\s，。、,.;:！!？?\"'()（）\-—]+")


def _norm(text: str) -> str:
    return _PUNCT_RE.sub("", str(text)).lower()


# ---- 画布读取 ----

async def _current_canvas_nodes_by_board(
    db: AsyncSession, project_id
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, CanvasNode]]:
    """读当前版本的画布,返回 (boards_meta, nodes_by_key)。

    boards_meta: {board_key: {"board_key","board_title","node_keys":[...]}}
    nodes_by_key: {node_key: CanvasNode}
    """
    version = await canvas_service.get_current_version(db, project_id)
    canvas = await canvas_service.get_canvas(db, version.id)
    boards_meta: Dict[str, Dict[str, Any]] = {}
    nodes_by_key: Dict[str, CanvasNode] = {}
    for group in canvas.groups:
        bk = group.group_key
        boards_meta.setdefault(bk, {"board_key": bk, "board_title": group.title, "node_keys": []})
        for node in group.nodes:
            key = node.node_key or node.title
            nodes_by_key[key] = node
            boards_meta[bk]["node_keys"].append(key)
    return boards_meta, nodes_by_key


def _hits_to_text(hits: List[Dict[str, Any]]) -> str:
    lines = []
    for i, h in enumerate(hits, 1):
        lines.append(
            f"[{i}] {h.get('title','')}\n来源:{h.get('domain') or h.get('url','')}\n"
            f"摘要:{h.get('snippet','')}\n链接:{h.get('url','')}"
        )
    return "\n\n".join(lines)


def _build_organize_prompt(
    boards_meta: Dict[str, Dict[str, Any]],
    hits_text: str,
    context_hint: str,
) -> str:
    modules_desc = []
    for bk, meta in boards_meta.items():
        # 仅给 board + node_key 清单,不泄漏已有内容(让 LLM 基于命中归类)
        modules_desc.append(
            f"- 板块 {bk}（{meta['board_title']}）节点: {', '.join(meta['node_keys'])}"
        )
    return (
        f"企业上下文/需求:\n{context_hint}\n\n"
        f"网络搜索命中:\n{hits_text}\n\n"
        f"画布目标模块（board_key → 节点 node_key 清单）:\n"
        + "\n".join(modules_desc)
        + "\n\n"
        + _ANTI_FABRICATION_CONSTRAINTS
        + "\n请把搜索命中的事实要点归类到上面的节点。严格输出 JSON,结构如下,不要任何额外文字:\n"
        "{\n"
        '  "boards": [\n'
        '    {"board_key": "...", "nodes": [\n'
        '      {"node_key": "...", "points": ["事实要点"], '
        '"citations": [{"name":"...","url":"...","snippet":"..."}], '
        '"pending_questions": ["找不到出处时写这里"]}\n'
        '    ]}\n'
        '  ],\n'
        '  "summary": {"key_points": ["..."], "missing_info": ["..."]}\n'
        "}\n"
        "只返回能从命中找到出处的要点;无事实的节点不要出现在结果里。"
    )


def _normalize_citations(raw: Any) -> List[Dict[str, Any]]:
    out = []
    if not isinstance(raw, list):
        return out
    for c in raw:
        if not isinstance(c, dict):
            continue
        out.append({
            "name": str(c.get("name") or c.get("title") or "网络来源"),
            "url": str(c.get("url") or ""),
            "snippet": str(c.get("snippet") or ""),
            "type": "web_search",
        })
    return out


def _attach_titles(
    payload: Dict[str, Any],
    boards_meta: Dict[str, Dict[str, Any]],
    nodes_by_key: Dict[str, CanvasNode],
    mode: str,
) -> Dict[str, Any]:
    """校验 node_key 合法 + 补 board_title/node_title + 规范 citations + 设 mode。"""
    boards_out = []
    for board in payload.get("boards", []) or []:
        bk = board.get("board_key")
        meta = boards_meta.get(bk)
        if meta is None:
            continue  # 非法 board_key 丢弃
        nodes_out = []
        for n in board.get("nodes", []) or []:
            nk = n.get("node_key")
            node = nodes_by_key.get(nk)
            if node is None or nk not in meta["node_keys"]:
                continue  # 非法 node_key 或跨板归属错误 → 丢弃
            points = [str(p) for p in (n.get("points") or []) if str(p).strip()]
            if not points and not (n.get("pending_questions") or []):
                continue
            nodes_out.append({
                "node_key": nk,
                "node_title": node.title,
                "points": points,
                "citations": _normalize_citations(n.get("citations")),
                "pending_questions": [str(q) for q in (n.get("pending_questions") or []) if str(q).strip()],
            })
        if nodes_out:
            boards_out.append({
                "board_key": bk,
                "board_title": meta["board_title"],
                "nodes": nodes_out,
            })
    summary = payload.get("summary") or {}
    return {
        "mode": mode,
        "boards": boards_out,
        "summary": {
            "key_points": [str(k) for k in (summary.get("key_points") or []) if str(k).strip()],
            "missing_info": [str(m) for m in (summary.get("missing_info") or []) if str(m).strip()],
        },
    }


# ---- ask 引擎 ----

async def research_and_propose(
    db: AsyncSession,
    project_id,
    context_hint: str,
    mode: str = "ask",
    web_hits: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """ask 模式引擎:搜索(或复用预取 hits)+ 一次整理 pass → Proposal。不写库。"""
    boards_meta, nodes_by_key = await _current_canvas_nodes_by_board(db, project_id)

    if web_hits is None:
        hits, _summary = await acquire_web_context(
            db, context_hint, max_results=5, context_hint=context_hint
        )
    else:
        hits = web_hits

    if not hits:
        return {
            "mode": mode,
            "boards": [],
            "summary": {"key_points": [], "missing_info": ["未检索到相关公开信息"]},
        }

    llm = await get_llm_service(db)
    payload = await llm.generate_json(
        _build_organize_prompt(boards_meta, _hits_to_text(hits), context_hint),
        system_prompt=_ORGANIZE_SYSTEM,
        temperature=0.2,
    )
    if not isinstance(payload, dict):
        payload = {}
    return _attach_titles(payload, boards_meta, nodes_by_key, mode)


# ---- auto 派生(从 fill_canvas 已写结果读出 Proposal;所见即所写) ----

async def build_fill_proposal_from_canvas(
    db: AsyncSession, project_id
) -> Dict[str, Any]:
    """auto 模式:读当前画布已写节点,派生 Proposal(mode=auto,只读展示)。"""
    boards_meta, nodes_by_key = await _current_canvas_nodes_by_board(db, project_id)
    # 按 board 聚合;同 board 下每个有 planning 的节点出一个 entry
    boards_out = []
    for bk, meta in boards_meta.items():
        nodes_out = []
        for nk in meta["node_keys"]:
            node = nodes_by_key.get(nk)
            if node is None:
                continue
            content = node.content or {}
            planning = list(content.get("planning") or [])
            if not planning:
                continue
            citations = []
            for s in (node.sources or []):
                if s.source_type == "web_search":
                    citations.append({
                        "name": s.source_name or "网络来源",
                        "url": (s.metadata_json or {}).get("url", "") if s.metadata_json else "",
                        "snippet": s.quote or "",
                        "type": "web_search",
                    })
            nodes_out.append({
                "node_key": nk,
                "node_title": node.title,
                "points": planning,
                "citations": citations,
                "pending_questions": list(content.get("pending_questions") or []),
            })
        if nodes_out:
            boards_out.append({
                "board_key": bk,
                "board_title": meta["board_title"],
                "nodes": nodes_out,
            })
    return {"mode": "auto", "boards": boards_out,
            "summary": {"key_points": [], "missing_info": []}}


# ---- 去重门槛(ask 模式用,只保留新增要点) ----

def filter_new_points(
    proposal: Dict[str, Any], nodes_by_key: Dict[str, CanvasNode]
) -> Dict[str, Any]:
    new_boards = []
    for board in proposal.get("boards", []):
        new_nodes = []
        for n in board.get("nodes", []):
            node = nodes_by_key.get(n["node_key"])
            if node is None:
                continue
            old = set(_norm(p) for p in (node.content or {}).get("planning", []) or [])
            fresh = [p for p in n.get("points", []) if _norm(p) not in old]
            if fresh:
                n["points"] = fresh
                new_nodes.append(n)
        if new_nodes:
            board["nodes"] = new_nodes
            new_boards.append(board)
    proposal["boards"] = new_boards
    return proposal


# ---- 写回(Task 4 实现 accept_fill_proposal;此处占位签名供 import,Task 4 填体) ----

async def accept_fill_proposal(
    db: AsyncSession,
    project_id,
    body: Dict[str, Any],
    user_id=None,
) -> ProjectVersion:
    raise NotImplementedError("Task 4 implements this")
```

> `accept_fill_proposal` 在本任务只给签名(便于 import 不报错),Task 4 填实现。这样 Task 6 的前端 import 链不阻塞。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd apps/api && pytest app/tests/test_canvas_research_service.py -v`
Expected: 5 PASS(research shape / no-advice / no-double-search / degrade / filter_new_points ×2)。

- [ ] **Step 5: 提交**

```bash
git add apps/api/app/services/canvas_research_service.py apps/api/app/tests/test_canvas_research_service.py
git commit -m "feat(canvas): 采集→智能归档 引擎/派生/Proposal 形状"
```

---

## Task 2: auto 模式 SSE `canvas_fill_proposal` 可见化

**Files:**
- Modify: `apps/api/app/services/conversation_service.py`(`_handle_auto_fill` ~1651-1712)
- Test: `apps/api/app/tests/test_canvas_fill_proposal_sse.py`

**Interfaces:**
- Consumes: Task 1 的 `build_fill_proposal_from_canvas`。
- Produces: 首条消息 fill_canvas 写完后,额外 emit 一个裸 `canvas_fill_proposal` SSE block(mode=auto)。

- [ ] **Step 1: 写失败测试**

Create `apps/api/app/tests/test_canvas_fill_proposal_sse.py`:

```python
"""auto/ask 模式的 canvas_fill_proposal SSE 触发 + 门槛。

直接调用内部 handler(_handle_auto_fill / _handle_conversational),mock 掉
save_message / llm / 搜索 / fill_canvas,断言裸 SSE 事件。注意:
  - ConversationService() 无参构造(见 conversation_service.py:132)。
  - _handle_auto_fill 的签名是 (db, conversation_id, user_message, project_id, force=False)。
  - _handle_auto_fill 内 acquire_web_context 与 canvas_agent_orchestrator 都是【局部 import】,
    故 patch 源:app.services.search_helper.acquire_web_context、
    app.services.canvas_agent_orchestrator.canvas_agent_orchestrator.fill_canvas。
  - _handle_conversational 用【模块级】acquire_web_context(conversation_service.py:17),
    故 patch:app.services.conversation_service.acquire_web_context。
"""
import json
import uuid as _uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.services import canvas_research_service as crs
from app.services.conversation_service import ConversationService

pytestmark = pytest.mark.asyncio


async def _collect(stream):
    out = []
    async for chunk in stream:
        out.append(chunk)
    return out


def _parse_events(chunks):
    events = []
    for c in chunks:
        text = c.decode() if isinstance(c, (bytes, bytearray)) else c
        for line in text.splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[len("data: "):]))
    return events


async def test_auto_fill_emits_canvas_fill_proposal(
    canvas_project_with_version, db_session, monkeypatch
):
    """首条 auto-fill 后 emit canvas_fill_proposal(mode=auto)。"""
    project_id, version_id = canvas_project_with_version
    proposal = {
        "mode": "auto",
        "boards": [{
            "board_key": "company_intro", "board_title": "企业介绍",
            "nodes": [{
                "node_key": "company_profile", "node_title": "企业简介",
                "points": ["成立于 2015 年"], "citations": [], "pending_questions": [],
            }],
        }],
        "summary": {"key_points": [], "missing_info": []},
    }
    svc = ConversationService()
    monkeypatch.setattr(svc, "save_message", AsyncMock())          # 不落库
    monkeypatch.setattr(svc, "_load_ref_docs_context", AsyncMock(return_value=(None, [])))
    with patch("app.services.search_helper.acquire_web_context",
               AsyncMock(return_value=([], {"status": "ok", "key_points": [], "missing_info": []}))), \
         patch("app.services.canvas_agent_orchestrator.canvas_agent_orchestrator.fill_canvas",
               AsyncMock(return_value={"success": True, "filled_count": 1, "node_ids": [], "errors": []})), \
         patch.object(crs, "build_fill_proposal_from_canvas", AsyncMock(return_value=proposal)):
        events = _parse_events(await _collect(svc._handle_auto_fill(
            db_session, _uuid.uuid4(), "帮我介绍一下甲公司", str(project_id)
        )))
    types = [e.get("type") for e in events]
    assert "canvas_fill_proposal" in types
    block = next(e for e in events if e.get("type") == "canvas_fill_proposal")
    assert block["data"]["mode"] == "auto"
    assert block["data"]["boards"][0]["nodes"][0]["points"]
```

> Task 6 会在本文件追加 `test_conversational_emits_ask_proposal_on_new_info` 与 `test_conversational_no_proposal_when_all_dup`(直接调 `_handle_conversational`)。本任务先只放 auto 用例。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd apps/api && pytest app/tests/test_canvas_fill_proposal_sse.py::test_auto_fill_emits_canvas_fill_proposal -v`
Expected: FAIL —— 事件里没有 `canvas_fill_proposal`。

- [ ] **Step 3: 在 `_handle_auto_fill` 注入 emit**

在 `apps/api/app/services/conversation_service.py` 顶部 import 处加:

```python
from app.services import canvas_research_service
```

在 `_handle_auto_fill` 内,`fill_canvas` commit 成功之后(conversation_service.py:1664 `await fill_db.commit()` 之后)、summary 构造(conversation_service.py:1678)之前,插入派生 + emit:

```python
        # 可见化:从 fill_canvas 写回结果派生 Proposal,让用户看到填了什么(所见即所写)
        try:
            proposal = await canvas_research_service.build_fill_proposal_from_canvas(
                db, proj_uuid
            )
            if proposal.get("boards"):
                yield f"data: {json.dumps({'type': 'canvas_fill_proposal', 'data': proposal}, ensure_ascii=False)}\n\n"
        except Exception:
            # 派生失败不阻断主流程(fill 已成功)
            pass
```

> `db`、`proj_uuid`、`json` 均在该函数作用域内已有。`build_fill_proposal_from_canvas` 用主 SSE session 的 `db`(只读)。它内部经 `canvas_service.get_current_version` + `get_canvas` 读画布;`get_canvas` 带 `populate_existing()`(canvas_service.py:415-436),故能读到上面 `fill_db.commit()` 刚写入的节点内容,不存在主 session 读到旧缓存的风险。`canvas_research_service` 在本任务加为**模块级** import(顶部),供 Task 6/8 复用。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd apps/api && pytest app/tests/test_canvas_fill_proposal_sse.py::test_auto_fill_emits_canvas_fill_proposal -v`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add apps/api/app/services/conversation_service.py apps/api/app/tests/test_canvas_fill_proposal_sse.py
git commit -m "feat(canvas): 首条 auto-fill 派生并 emit canvas_fill_proposal(可见化)"
```

---

## Task 3: 前端 `canvas_fill_proposal` 渲染(auto 只读)

**Files:**
- Create: `apps/web/components/canvas/canvas-fill-proposal-block.tsx`
- Modify: `apps/web/types/index.ts`(ContentBlock.type 联合)
- Modify: `apps/web/components/canvas/conversation-panel.tsx`(renderContentBlock 分支 + ctx)

**Interfaces:**
- Consumes: SSE `canvas_fill_proposal` block(chats-api 默认分支自动收进 `richContent.blocks`)。
- Produces: 对话里渲染「采集了什么、填进哪些模块」分组要点 + 来源;auto 模式只读(ask 模式的勾选/采纳在 Task 7 加)。

- [ ] **Step 1: 读 Next.js 文档(per apps/web/AGENTS.md)**

读 `apps/web/node_modules/next/dist/docs/` 下 client components / hooks 相关指引,留意 `"use client"` 与 `fetch` 用法的弃用提示。

- [ ] **Step 2: 扩 ContentBlock.type 联合**

在 `apps/web/types/index.ts` ContentBlock.type 联合末尾(`"node_draft"` 之后)加:

```typescript
    | "canvas_fill_proposal";
```

- [ ] **Step 3: 创建 `CanvasFillProposalBlock`**

Create `apps/web/components/canvas/canvas-fill-proposal-block.tsx`:

```tsx
"use client";

// Renders the canvas_fill_proposal SSE block emitted by the research→smart-fill
// pipeline. auto mode (first message): read-only summary of what was filled,
// grouped by board → node, with source citations. ask mode (Task 7): adds
// per-node checkboxes + 「采纳所选」 that POSTs to /canvas/fill-accept.

import { useState } from "react";
import { Check, Loader2, Search } from "lucide-react";

export interface FillCitation {
  name?: string;
  url?: string;
  snippet?: string;
  type?: string;
}

export interface FillProposalNode {
  node_key: string;
  node_title: string;
  points: string[];
  citations?: FillCitation[];
  pending_questions?: string[];
}

export interface FillProposalBoard {
  board_key: string;
  board_title: string;
  nodes: FillProposalNode[];
}

export interface CanvasFillProposalData {
  mode: "auto" | "ask";
  boards: FillProposalBoard[];
  summary?: { key_points?: string[]; missing_info?: string[] };
}

export function CanvasFillProposalBlock({
  data,
}: {
  data: CanvasFillProposalData;
  onAccepted?: () => void; // Task 7 ask 模式用;auto 模式不传
}) {
  const isAuto = data.mode === "auto";
  const boards = data.boards ?? [];
  return (
    <div className="rounded-lg border border-primary/30 bg-primary-fixed/40 p-3 space-y-3">
      <div className="flex items-center gap-1.5 text-[10px] text-primary font-semibold uppercase tracking-wider">
        <Search className="h-3 w-3" />
        {isAuto ? "已采集并填充到画布" : "搜索到可归档的内容"}
      </div>

      {boards.map((b) => (
        <div key={b.board_key} className="space-y-1.5">
          <div className="text-xs font-semibold text-on-surface">{b.board_title}</div>
          {b.nodes.map((n) => (
            <div key={n.node_key} className="pl-2 border-l border-outline/40 space-y-1">
              <div className="text-[11px] text-tertiary">{n.node_title}</div>
              <div className="text-xs text-on-surface whitespace-pre-wrap space-y-0.5">
                {n.points.map((p, i) => (
                  <p key={i}>• {p}</p>
                ))}
              </div>
              {(n.pending_questions ?? []).length > 0 ? (
                <div className="text-[11px] text-outline">
                  待确认：{(n.pending_questions ?? []).join("；")}
                </div>
              ) : null}
              {(n.citations ?? []).length > 0 ? (
                <div className="text-[10px] text-outline">
                  来源：
                  {(n.citations ?? []).map((c, i) => (
                    <span key={i}>
                      {i > 0 ? "、" : ""}
                      {c.url ? (
                        <a href={c.url} target="_blank" rel="noreferrer" className="underline">
                          {c.name || c.url}
                        </a>
                      ) : (
                        c.name || "网络来源"
                      )}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      ))}

      {!isAuto && (data.summary?.missing_info ?? []).length > 0 ? (
        <div className="text-[11px] text-tertiary">
          缺失信息：{(data.summary?.missing_info ?? []).join("；")}
        </div>
      ) : null}
    </div>
  );
}
```

> ask 模式的勾选/采纳按钮在 Task 7 扩展(届时该组件接 `projectId` + `onAccepted` + 内部 selected 状态 + 调 `acceptCanvasFill`)。本任务只做只读渲染,但预留 `onAccepted` prop 签名避免 Task 7 改 props 接口。

- [ ] **Step 4: 接进 `renderContentBlock`**

在 `apps/web/components/canvas/conversation-panel.tsx` import 处加:

```typescript
import {
  CanvasFillProposalBlock,
  type CanvasFillProposalData,
} from "@/components/canvas/canvas-fill-proposal-block";
```

在 `renderContentBlock` 的 `node_draft` 分支之后加(canvas_fill_proposal 不依赖 activeNodeId,它是全局采集结果):

```typescript
  if (block.type === "canvas_fill_proposal") {
    const proposal = (block.data ?? {}) as unknown as CanvasFillProposalData;
    return <CanvasFillProposalBlock key={key} data={proposal} />;
  }
```

- [ ] **Step 5: tsc + lint**

Run: `cd apps/web && node_modules/.bin/tsc --noEmit && npm run lint`
Expected: 无错。

- [ ] **Step 6: 提交**

```bash
git add apps/web/components/canvas/canvas-fill-proposal-block.tsx apps/web/types/index.ts apps/web/components/canvas/conversation-panel.tsx
git commit -m "feat(web): canvas_fill_proposal 渲染(auto 只读,采集可见化)"
```

---

## Task 4: `accept_fill_proposal` 版本化写回

**Files:**
- Modify: `apps/api/app/services/canvas_research_service.py`(填 `accept_fill_proposal` 实现)
- Test: `apps/api/app/tests/test_canvas_research_service.py`(追加用例)

**Interfaces:**
- Consumes: Task 1 的签名;`canvas_service.create_version` + `get_canvas`;`CanvasNode`/`NodeSource`。
- Produces: `accept_fill_proposal(db, project_id, body, user_id=None) -> ProjectVersion` —— 新建版本快照 → 对每个选中 node 合并(保留 ui_suggestion/extracted、覆盖 planning/pending、status=filled)→ 每条 citation 追加 `NodeSource(web_search)`。body 形状同 Proposal 的 boards 子集(`{boards:[{board_key,nodes:[{node_key,points,citations}]}], change_summary?}`)。

- [ ] **Step 1: 写失败测试**

在 `apps/api/app/tests/test_canvas_research_service.py` 追加:

```python
async def test_accept_fill_proposal_creates_version_and_merges(
    db_session, canvas_project_with_version
):
    """采纳:新建 ProjectVersion(is_current 翻转)、节点 planning 被覆盖、
    ui_suggestion/extracted 保留、status=filled、citation 写 NodeSource。"""
    from sqlalchemy import select
    from app.models.canvas import CanvasNode, NodeSource, ProjectVersion

    project_id, version_id = canvas_project_with_version

    # 先给目标节点塞一点既有 ui_suggestion(验证保留)
    node = await _first_node_in_version(db_session, None, "company_profile", project_id=project_id)
    node.content = {"extracted": ["旧 extracted"], "planning": [],
                    "ui_suggestion": ["旧 ui 建议"], "pending_questions": []}
    await db_session.flush()

    body = {
        "boards": [{
            "board_key": "company_intro",
            "nodes": [{
                "node_key": "company_profile",
                "points": ["成立于 2016 年", "员工 200 人"],
                "citations": [{"name": "官网", "url": "https://x", "snippet": "..."}],
            }],
        }],
        "change_summary": "采集填充：1 个节点",
    }
    new_version = await accept_fill_proposal(db_session, project_id, body, user_id=None)
    await db_session.commit()

    assert isinstance(new_version, ProjectVersion)
    assert new_version.is_current is True
    old = await db_session.get(ProjectVersion, version_id)
    assert old.is_current is False  # 旧版本被 demote

    # 新版本上的节点被合并写回(create_version 克隆了旧画布,故 ui_suggestion/extracted 保留)
    new_node = await _first_node_in_version(db_session, new_version.id, "company_profile")
    c = new_node.content
    assert c["planning"] == ["成立于 2016 年", "员工 200 人"]
    assert c["ui_suggestion"] == ["旧 ui 建议"]  # 保留
    assert c["extracted"] == ["旧 extracted"]    # 保留
    assert new_node.status == "filled"
    srcs = (await db_session.execute(
        select(NodeSource).where(NodeSource.node_id == new_node.id)
    )).scalars().all()
    web_srcs = [s for s in srcs if s.source_type == "web_search"]
    assert any(s.source_name == "官网" for s in web_srcs)


async def test_accept_fill_proposal_rejects_illegal_node_key(
    db_session, canvas_project_with_version
):
    project_id, version_id = canvas_project_with_version
    body = {"boards": [{"board_key": "company_intro",
                        "nodes": [{"node_key": "DOES_NOT_EXIST", "points": ["x"], "citations": []}]}]}
    with pytest.raises(Exception):
        await accept_fill_proposal(db_session, project_id, body)


# --- helpers ---
async def _first_node_in_version(db, version_id, node_key, project_id=None):
    from app.services import canvas_service
    if version_id is None:
        version_id = (await canvas_service.get_current_version(db, project_id)).id
    canvas = await canvas_service.get_canvas(db, version_id)
    for g in canvas.groups:
        for n in g.nodes:
            if (n.node_key or n.title) == node_key:
                return n
    raise AssertionError(f"node {node_key} not found")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd apps/api && pytest app/tests/test_canvas_research_service.py::test_accept_fill_proposal_creates_version_and_merges -v`
Expected: FAIL —— `NotImplementedError`(Task 1 占位)。

- [ ] **Step 3: 实现 `accept_fill_proposal`**

在 `apps/api/app/services/canvas_research_service.py` 把 `accept_fill_proposal` 的 `raise NotImplementedError(...)` 体替换为:

```python
async def accept_fill_proposal(
    db: AsyncSession,
    project_id,
    body: Dict[str, Any],
    user_id=None,
) -> ProjectVersion:
    """版本化写回:新建 ProjectVersion 快照 → 按 node_key 合并节点 → 追加 NodeSource。

    body: {"boards":[{"board_key","nodes":[{"node_key","points","citations"}]}],
           "change_summary"?: str}
    合并语义(与 adopt_node_draft 一致):保留 ui_suggestion/extracted,覆盖 planning/pending,
    status=filled;每条 citation(type=web_search 或缺省)写一行 NodeSource(web_search)。
    """
    import uuid as _uuid

    # 1) 新建版本快照(自动 demote 旧 current + 翻 is_current)
    new_version = await canvas_service.create_version(
        db,
        project_id,
        version_name=None,
        change_summary=body.get("change_summary") or "采集填充",
        based_on_version_id=None,
        created_by=user_id,
    )
    canvas = await canvas_service.get_canvas(db, new_version.id)

    # 建 (board_key -> set(node_key)) 与 node 查表
    board_nodes: Dict[str, Dict[str, CanvasNode]] = {}
    for group in canvas.groups:
        board_nodes.setdefault(group.group_key, {})
        for n in group.nodes:
            board_nodes[group.group_key][n.node_key or n.title] = n

    # 2) 对每个选中 node 合并 + 写溯源
    for board in body.get("boards", []) or []:
        bk = board.get("board_key")
        node_map = board_nodes.get(bk)
        if node_map is None:
            continue  # 非法 board 跳过(整体已在 create_version 后,不回滚)
        for entry in board.get("nodes", []) or []:
            nk = entry.get("node_key")
            node = node_map.get(nk)
            if node is None:
                raise ValueError(f"非法 node_key: {nk}(board={bk})")
            points = [str(p) for p in (entry.get("points") or []) if str(p).strip()]
            citations = entry.get("citations") or []
            old = node.content or {}
            node.content = {
                "extracted": list(old.get("extracted") or []),
                "planning": points,
                "ui_suggestion": list(old.get("ui_suggestion") or []),
                "pending_questions": list(old.get("pending_questions") or []),
            }
            node.status = "filled" if points else (node.status or "draft")
            db.add(node)
            for c in citations:
                if not isinstance(c, dict):
                    continue
                db.add(NodeSource(
                    id=_uuid.uuid4(),
                    node_id=node.id,
                    source_type="web_search",
                    source_name=str(c.get("name") or "网络来源"),
                    confidence="low",
                    quote=str(c.get("snippet") or "")[:500] or None,
                    metadata_json={"url": c.get("url", "")},
                ))
    return new_version
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd apps/api && pytest app/tests/test_canvas_research_service.py -v`
Expected: 全部 PASS(含新加 2 个 + 原 5 个)。

- [ ] **Step 5: 提交**

```bash
git add apps/api/app/services/canvas_research_service.py apps/api/app/tests/test_canvas_research_service.py
git commit -m "feat(canvas): accept_fill_proposal 版本化写回(新快照+合并+溯源)"
```

---

## Task 5: `POST /fill-accept` 接口

**Files:**
- Modify: `apps/api/app/schemas/canvas.py`(加 `CanvasFillAcceptIn`)
- Modify: `apps/api/app/routers/canvas.py`(加路由)
- Test: `apps/api/app/tests/test_canvas_fill_accept.py`

**Interfaces:**
- Consumes: Task 4 的 `accept_fill_proposal`。
- Produces: `POST /api/v1/projects/{pid}/canvas/fill-accept`,body 为 `CanvasFillAcceptIn`,返回新版本 + 更新后画布(沿用 CanvasOut)。

- [ ] **Step 1: 写失败测试**

Create `apps/api/app/tests/test_canvas_fill_accept.py`:

```python
"""POST /api/v1/projects/{pid}/canvas/fill-accept 版本化写回。

用 `client` fixture(conftest.py:159,auth 在测试里已旁路,无需 headers,见 test_canvas.py)。
`canvas_project_with_version` yield (project_id, version_id)。
"""
import pytest

pytestmark = pytest.mark.asyncio


async def test_fill_accept_writes_versioned_and_returns_filled_canvas(
    client, canvas_project_with_version
):
    project_id, version_id = canvas_project_with_version
    body = {
        "boards": [{
            "board_key": "company_intro",
            "nodes": [{
                "node_key": "company_profile",
                "points": ["成立于 2017 年"],
                "citations": [{"name": "官网", "url": "https://x", "snippet": "..."}],
            }],
        }],
        "change_summary": "采集填充：1 节点",
    }
    resp = await client.post(
        f"/api/v1/projects/{project_id}/canvas/fill-accept", json=body
    )
    assert resp.status_code == 200, resp.text
    canvas = resp.json()["data"]  # CanvasOut(camelCase): groups/nodes/edges
    cp = next(n for n in canvas["nodes"] if n["nodeKey"] == "company_profile")
    assert cp["status"] == "filled"
    assert "成立于 2017 年" in cp["content"]["planning"]
```

> 非法 node_key 的拒绝由 Task 4 单元测试(`test_accept_fill_proposal_rejects_illegal_node_key`)覆盖;router 层不额外做 404 校验(MVP 无多租户/鉴权,test_canvas.py 范式亦无)。后续对外再加项目存在性校验返回 404。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd apps/api && pytest app/tests/test_canvas_fill_accept.py -v`
Expected: FAIL —— 404(路由不存在)。

- [ ] **Step 3: 加 schema**

在 `apps/api/app/schemas/canvas.py` 加(紧邻 `NodeAdoptIn`):

```python
class CanvasFillAcceptIn(APIBaseModel):
    """用户勾选采纳的采集提案(body 由前端回传,服务端再校验 node_key)。"""
    boards: List[Dict[str, Any]]
    change_summary: Optional[str] = None
```

> 若 `List`/`Dict`/`Any` 未在该文件 import,补 `from typing import Any, Dict, List, Optional`。`APIBaseModel` 沿用文件既有基类。

- [ ] **Step 4: 加路由**

在 `apps/api/app/routers/canvas.py` 顶部 import 处加:

```python
from app.services.canvas_research_service import accept_fill_proposal
```

并在 `adopt_node` 路由之后(`canvas.py:308` 附近)加(沿用 adopt 的 response/commit 范式):

```python
@router.post(
    "/projects/{project_id}/canvas/fill-accept",
    response_model=Response[CanvasOut],
)
async def accept_canvas_fill(
    project_id: uuid.UUID,
    body: CanvasFillAcceptIn,
    db: AsyncSession = Depends(get_db),
):
    """采纳采集提案:创建新版本快照 + 按 node_key 合并节点 + 追加 web_search 溯源。"""
    new_version = await accept_fill_proposal(
        db,
        project_id=project_id,
        body=body.model_dump(),
    )
    await db.commit()
    canvas = await canvas_service.get_canvas(db, new_version.id)
    return Response(data=_to_canvas_out(canvas), message="已采纳并生成新版本")
```

> `_to_canvas_out(canvas, is_read_only=False)`、`CanvasOut`、`Response`、`get_db`、`uuid`、`canvas_service`、`AsyncSession`/`Depends` 均为本文件既有(routers/canvas.py:70 定义 `_to_canvas_out`,adopt 路由已用 `canvas_service`/`uuid`/`Response`)。返回结构 = `_to_canvas_out(canvas)` 即 CanvasOut(groups/nodes/edges),与 GET canvas 接口一致;`new_version` 仅用于 `get_canvas(db, new_version.id)` 取新版本画布,不传给 `_to_canvas_out`。

- [ ] **Step 5: 跑测试确认通过**

Run: `cd apps/api && pytest app/tests/test_canvas_fill_accept.py -v`
Expected: 1 PASS。

- [ ] **Step 6: 提交**

```bash
git add apps/api/app/schemas/canvas.py apps/api/app/routers/canvas.py apps/api/app/tests/test_canvas_fill_accept.py
git commit -m "feat(canvas): POST /canvas/fill-accept 版本化采纳接口"
```

---

## Task 6: ask 模式引擎接入 `_handle_conversational` + 门槛

**Files:**
- Modify: `apps/api/app/services/conversation_service.py`(`_handle_conversational` ~1272)
- Test: `apps/api/app/tests/test_canvas_fill_proposal_sse.py`(补 ask 用例)

**Interfaces:**
- Consumes: Task 1 的 `research_and_propose(mode="ask", web_hits=...)` + `filter_new_points` + `_current_canvas_nodes_by_board`。
- Produces: 后续问答搜到模块相关**新增**要点时,在直答之后 emit `canvas_fill_proposal`(mode=ask,不写库);寒暄/无关/全重复 → 不 emit。

- [ ] **Step 1: 写失败测试**

在 `apps/api/app/tests/test_canvas_fill_proposal_sse.py` 追加(直接调 `_handle_conversational`,见文件顶部关于 patch 目标的说明):

```python
async def test_conversational_emits_ask_proposal_on_new_info(
    canvas_project_with_version, db_session, monkeypatch
):
    """后续问答搜到模块相关新增要点 → 直答后 emit canvas_fill_proposal(mode=ask)。"""
    project_id, version_id = canvas_project_with_version
    ask_proposal = {
        "mode": "ask",
        "boards": [{
            "board_key": "company_intro", "board_title": "企业介绍",
            "nodes": [{
                "node_key": "company_scale", "node_title": "企业规模",
                "points": ["员工 500 人"], "citations": [], "pending_questions": [],
            }],
        }],
        "summary": {"key_points": [], "missing_info": []},
    }
    # 假 LLM:走 fallback 流式路径(置 rich=None,触发 generate_with_history_stream)
    fake_llm = AsyncMock()
    fake_llm.generate_with_history_stream_rich = None
    async def _stream(*a, **k):
        yield "已为你查到相关信息。"
    fake_llm.generate_with_history_stream = _stream
    svc = ConversationService()
    monkeypatch.setattr(svc, "save_message", AsyncMock())
    with patch("app.services.conversation_service.get_llm_service",
               AsyncMock(return_value=fake_llm)), \
         patch("app.services.conversation_service.acquire_web_context",
               AsyncMock(return_value=([{"title": "t", "url": "https://x", "snippet": "s",
                  "domain": "x", "published_at": None, "source_type": "article",
                  "confidence": 0.5}], {"status": "ok", "key_points": [], "missing_info": []}))), \
         patch.object(crs, "research_and_propose", AsyncMock(return_value=ask_proposal)):
        events = _parse_events(await _collect(svc._handle_conversational(
            db_session, _uuid.uuid4(), "甲公司有多少员工", [], str(project_id)
        )))
    types = [e.get("type") for e in events]
    assert "canvas_fill_proposal" in types
    block = next(e for e in events if e.get("type") == "canvas_fill_proposal")
    assert block["data"]["mode"] == "ask"


async def test_conversational_no_proposal_when_all_dup(
    canvas_project_with_version, db_session, monkeypatch
):
    """全重复要点 → filter_new_points 清空 boards → 不 emit。"""
    from app.services import canvas_service

    project_id, version_id = canvas_project_with_version
    # 预置 company_profile 节点已有该要点,使 filter_new_points 判定为重复
    ver = await canvas_service.get_current_version(db_session, project_id)
    cv = await canvas_service.get_canvas(db_session, ver.id)
    for g in cv.groups:
        for n in g.nodes:
            if (n.node_key or n.title) == "company_profile":
                n.content = {"extracted": [], "planning": ["已存在的要点"],
                             "ui_suggestion": [], "pending_questions": []}
    await db_session.commit()

    dup_proposal = {
        "mode": "ask",
        "boards": [{
            "board_key": "company_intro", "board_title": "企业介绍",
            "nodes": [{
                "node_key": "company_profile", "node_title": "企业简介",
                "points": ["已存在的要点"], "citations": [], "pending_questions": [],
            }],
        }],
        "summary": {"key_points": [], "missing_info": []},
    }
    fake_llm = AsyncMock()
    fake_llm.generate_with_history_stream_rich = None
    async def _stream2(*a, **k):
        yield "已知。"
    fake_llm.generate_with_history_stream = _stream2
    svc = ConversationService()
    monkeypatch.setattr(svc, "save_message", AsyncMock())
    with patch("app.services.conversation_service.get_llm_service",
               AsyncMock(return_value=fake_llm)), \
         patch("app.services.conversation_service.acquire_web_context",
               AsyncMock(return_value=([], {"status": "ok", "key_points": [], "missing_info": []}))), \
         patch.object(crs, "research_and_propose", AsyncMock(return_value=dup_proposal)):
        events = _parse_events(await _collect(svc._handle_conversational(
            db_session, _uuid.uuid4(), "甲公司情况", [], str(project_id)
        )))
    types = [e.get("type") for e in events]
    assert "canvas_fill_proposal" not in types
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd apps/api && pytest app/tests/test_canvas_fill_proposal_sse.py::test_conversational_emits_ask_proposal_on_new_info -v`
Expected: FAIL —— Step 3 之前 `_handle_conversational` 签名还未收 `project_id`(TypeError:参数过多)且未 emit ask 提案。

- [ ] **Step 3: 给 `_handle_conversational` 透传 project_id + 注入 ask 引擎**

`_handle_conversational` 当前签名没有 project_id(只有 conversation_id),而引擎需要它。`process_message_stream` 的派发处已算好 `project_id`(conversation_service.py:~574,用于 auto_fill 调用),故把它透传进来。

1) 改签名(conversation_service.py:1264),末尾加可选参数:

```python
    async def _handle_conversational(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
        user_message: str,
        history: List[Dict[str, str]],
        project_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
```

2) 改两处调用点(conversation_service.py:639-641 与 656-658),各加 `project_id` 实参:

```python
                    async for chunk in self._handle_conversational(
                        db, conv_uuid, user_message, history, project_id
                    ):
```

> 两处 `_handle_conversational` 调用都在 `process_message_stream` 内,`project_id` 已在该作用域(conversation_service.py:~574 算出,633 行已用于 auto_fill)。

3) 在 `_handle_conversational` 内,流式直答(text_delta)结束之后(conversation_service.py:1333 之后)、`save_message`(1336)之前,插入 ask 引擎(复用已取的 `web_hits`,不二次搜索):

```python
        # ask 模式:把搜到的模块相关「新增」要点整理成提案,问用户是否归档(不写库)
        if project_id and web_hits and not self._is_social_greeting(msg) and len(msg) >= 4:
            try:
                proposal = await canvas_research_service.research_and_propose(
                    db, project_id, context_hint=msg, mode="ask", web_hits=web_hits,
                )
                if proposal.get("boards"):
                    _, nodes_by_key = await canvas_research_service._current_canvas_nodes_by_board(
                        db, project_id
                    )
                    proposal = canvas_research_service.filter_new_points(proposal, nodes_by_key)
                    if proposal.get("boards"):
                        yield f"data: {json.dumps({'type': 'canvas_fill_proposal', 'data': proposal}, ensure_ascii=False)}\n\n"
            except Exception:
                logger.exception("conversational: research_and_propose failed; skipping proposal")
```

> `web_hits`(conversation_service.py:1283)、`msg`(1282)、`db`、`json`、`logger`、`canvas_research_service`(Task 2 模块级 import)均在作用域内。引擎接收 `web_hits=` 故内部不再触发 `acquire_web_context`(无双重搜索)。`research_and_propose` 被 mock 时其内部 `_current_canvas_nodes_by_board` 不执行,故此处显式再调一次取真实节点做去重。这段在直答流完之后,保证「先答问题、后提案」顺序。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd apps/api && pytest app/tests/test_canvas_fill_proposal_sse.py -v`
Expected: 全 PASS。

- [ ] **Step 5: 提交**

```bash
git add apps/api/app/services/conversation_service.py apps/api/app/tests/test_canvas_fill_proposal_sse.py
git commit -m "feat(canvas): ask 模式引擎接入 conversational + 新增门槛"
```

---

## Task 7: 前端 ask 模式勾选 + 采纳(`acceptCanvasFill`)

**Files:**
- Modify: `apps/web/components/canvas/canvas-fill-proposal-block.tsx`(ask 模式加勾选 + 采纳按钮)
- Modify: `apps/web/lib/canvas-api.ts`(加 `acceptCanvasFill`)
- Modify: `apps/web/components/canvas/conversation-panel.tsx`(ctx 扩 `onCanvasAccepted` + 透传 projectId)
- Modify: `apps/web/app/workspace/canvas/[projectId]/page.tsx`(传 `onCanvasAccepted={() => loadCurrent()}`)

**Interfaces:**
- Consumes: Task 5 的 `POST /canvas/fill-accept`。
- Produces: ask 模式每节点勾选(默认勾)+「采纳所选」→ POST → toast → `loadCurrent()` 刷新 → block 切「已采纳」。

- [ ] **Step 1: 加 `acceptCanvasFill` client**

在 `apps/web/lib/canvas-api.ts`(`adoptNode` 之后)加:

```typescript
export interface CanvasFillAcceptInput {
  boards: Array<{
    board_key: string;
    nodes: Array<{
      node_key: string;
      points: string[];
      citations?: Array<{ name?: string; url?: string; snippet?: string }>;
    }>;
  }>;
  change_summary?: string;
}

export async function acceptCanvasFill(
  projectId: string,
  body: CanvasFillAcceptInput,
): Promise<ApiResponse<CanvasNode>> {
  return canvasFetch<CanvasNode>(
    `/api/v1/projects/${projectId}/canvas/fill-accept`,
    { method: "POST", body: JSON.stringify(body) },
  );
}
```

> 返回类型沿用 `ApiResponse<...>`(CanvasNode 或 any;以文件既有 `ApiResponse` 泛型范式为准,填服务端实际返回形状)。import `CanvasNode` 若未在文件则用 `unknown` 或文件既有类型。

- [ ] **Step 2: ask 模式渲染勾选 + 采纳**

在 `apps/web/components/canvas/canvas-fill-proposal-block.tsx` 改造:组件接 `projectId` + `onAccepted`,内部 `selected` 状态(node_key set,默认全选),ask 模式渲染勾选框 +「采纳所选」按钮。完整文件:

```tsx
"use client";

import { useMemo, useState } from "react";
import { Check, Loader2, Search } from "lucide-react";
import { toast } from "sonner";
import { acceptCanvasFill } from "@/lib/canvas-api";

export interface FillCitation {
  name?: string;
  url?: string;
  snippet?: string;
  type?: string;
}
export interface FillProposalNode {
  node_key: string;
  node_title: string;
  points: string[];
  citations?: FillCitation[];
  pending_questions?: string[];
}
export interface FillProposalBoard {
  board_key: string;
  board_title: string;
  nodes: FillProposalNode[];
}
export interface CanvasFillProposalData {
  mode: "auto" | "ask";
  boards: FillProposalBoard[];
  summary?: { key_points?: string[]; missing_info?: string[] };
}

export function CanvasFillProposalBlock({
  data,
  projectId,
  onAccepted,
}: {
  data: CanvasFillProposalData;
  projectId?: string;
  onAccepted?: () => void;
}) {
  const isAuto = data.mode === "auto";
  const boards = data.boards ?? [];

  // ask 模式:默认全选
  const allKeys = useMemo(
    () => boards.flatMap((b) => b.nodes.map((n) => `${b.board_key}/${n.node_key}`)),
    [boards],
  );
  const [selected, setSelected] = useState<Set<string>>(() => new Set(allKeys));
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  function toggle(key: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  async function handleAccept() {
    if (busy || done || !projectId) return;
    setBusy(true);
    const payload = {
      boards: boards
        .map((b) => ({
          board_key: b.board_key,
          nodes: b.nodes
            .filter((n) => selected.has(`${b.board_key}/${n.node_key}`))
            .map((n) => ({
              node_key: n.node_key,
              points: n.points,
              citations: n.citations ?? [],
            })),
        }))
        .filter((b) => b.nodes.length > 0),
      change_summary: `采集采纳：${selected.size} 个节点`,
    };
    const res = await acceptCanvasFill(projectId, payload);
    setBusy(false);
    if (res.success) {
      setDone(true);
      toast.success("已采纳到画布");
      onAccepted?.();
    } else {
      toast.error(res.message ?? "采纳失败，请重试");
    }
  }

  return (
    <div className="rounded-lg border border-primary/30 bg-primary-fixed/40 p-3 space-y-3">
      <div className="flex items-center gap-1.5 text-[10px] text-primary font-semibold uppercase tracking-wider">
        <Search className="h-3 w-3" />
        {isAuto ? "已采集并填充到画布" : "搜索到可归档的内容"}
      </div>

      {boards.map((b) => (
        <div key={b.board_key} className="space-y-1.5">
          <div className="text-xs font-semibold text-on-surface">{b.board_title}</div>
          {b.nodes.map((n) => {
            const key = `${b.board_key}/${n.node_key}`;
            const checked = selected.has(key);
            return (
              <div key={key} className="pl-2 border-l border-outline/40 space-y-1">
                <div className="flex items-center gap-1.5">
                  {!isAuto ? (
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggle(key)}
                      className="h-3 w-3 accent-primary"
                    />
                  ) : null}
                  <span className="text-[11px] text-tertiary">{n.node_title}</span>
                </div>
                <div className="text-xs text-on-surface whitespace-pre-wrap space-y-0.5">
                  {n.points.map((p, i) => (
                    <p key={i}>• {p}</p>
                  ))}
                </div>
                {(n.pending_questions ?? []).length > 0 ? (
                  <div className="text-[11px] text-outline">
                    待确认：{(n.pending_questions ?? []).join("；")}
                  </div>
                ) : null}
                {(n.citations ?? []).length > 0 ? (
                  <div className="text-[10px] text-outline">
                    来源：
                    {(n.citations ?? []).map((c, i) => (
                      <span key={i}>
                        {i > 0 ? "、" : ""}
                        {c.url ? (
                          <a href={c.url} target="_blank" rel="noreferrer" className="underline">
                            {c.name || c.url}
                          </a>
                        ) : (
                          c.name || "网络来源"
                        )}
                      </span>
                    ))}
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      ))}

      {!isAuto && (data.summary?.missing_info ?? []).length > 0 ? (
        <div className="text-[11px] text-tertiary">
          缺失信息：{(data.summary?.missing_info ?? []).join("；")}
        </div>
      ) : null}

      {!isAuto ? (
        <button
          onClick={handleAccept}
          disabled={busy || done || selected.size === 0}
          className="w-full mt-1 inline-flex items-center justify-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-semibold text-on-primary disabled:opacity-60 hover:opacity-90"
        >
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
          {done ? "已采纳" : `采纳所选（${selected.size}）`}
        </button>
      ) : null}
    </div>
  );
}
```

> 按钮文案用 `text-on-primary`(NOT `text-primary-fill`——该 token 不存在,沿用 version-panel.tsx 的 `bg-primary text-on-primary` 范式)。

- [ ] **Step 3: renderContentBlock 透传 ctx**

在 `apps/web/components/canvas/conversation-panel.tsx`,把 Task 3 的 canvas_fill_proposal 分支改为透传 projectId + onAccepted:

```typescript
  if (block.type === "canvas_fill_proposal") {
    const proposal = (block.data ?? {}) as unknown as CanvasFillProposalData;
    return (
      <CanvasFillProposalBlock
        key={key}
        data={proposal}
        projectId={ctx?.projectId}
        onAccepted={ctx?.onCanvasAccepted}
      />
    );
  }
```

并把 `renderContentBlock` 与 `AssistantMessage` 的 `ctx` 类型扩展加 `onCanvasAccepted?: () => void`(在现有 `{ projectId?; activeNodeId?; onNodeAdopted? }` 后追加)。`ConversationPanel` props 加 `onCanvasAccepted?: () => void`,并在渲染 `AssistantMessage` 与 streaming blocks 处把 `ctx={{ projectId, activeNodeId, onNodeAdopted, onCanvasAccepted }}` 透下去(Task 7 已为 node_draft 做过同样透传,照搬)。

- [ ] **Step 4: 画布页传刷新回调**

在 `apps/web/app/workspace/canvas/[projectId]/page.tsx` 的 `<ConversationPanel>`(line ~556)加:

```tsx
        onCanvasAccepted={() => loadCurrent()}
```

> `loadCurrent` 已存在(page.tsx:182),采纳后刷新当前画布。

- [ ] **Step 5: tsc + lint**

Run: `cd apps/web && node_modules/.bin/tsc --noEmit && npm run lint`
Expected: 无错。

- [ ] **Step 6: 提交**

```bash
git add apps/web/components/canvas/canvas-fill-proposal-block.tsx apps/web/lib/canvas-api.ts apps/web/components/canvas/conversation-panel.tsx apps/web/app/workspace/canvas/[projectId]/page.tsx
git commit -m "feat(web): ask 模式勾选采纳 + acceptCanvasFill + 刷新回调"
```

---

## Task 8: Brief 生成(复用 `proposal_generation` skill)

**Files:**
- Modify: `apps/api/app/services/conversation_service.py`(`_handle_auto_fill` 末尾,首条 auto 贯通到 Brief)
- Test: `apps/api/app/tests/test_canvas_brief.py`

**Interfaces:**
- Consumes: Task 1 的 `build_fill_proposal_from_canvas`(序列化画布为画像文本);`SkillRunner` + `proposal_generation` skill(输入 `{project_id, requirement_text, context_pack}`);既有 `proposal_section` content block。
- Produces: 首条 auto-fill 完成后,把已填画布(企业画像)+ 项目上下文喂给 `proposal_generation`,把策划案作为设计 Brief,以现有 `proposal_section` block emit。

- [ ] **Step 1: 写失败测试**

Create `apps/api/app/tests/test_canvas_brief.py`:

```python
"""首条 auto-fill 完成后,基于已填画布生成设计 Brief(proposal_generation)。

直接调 _handle_auto_fill;Brief 以【现有 proposal_section block】 emit,data = skill output 整体
(与 _handle_skill_execution:865 一致)。SkillRunner/SkillContext/服务在 _handle_auto_fill 内
局部 import,故 patch 其源模块。
"""
import json
import uuid as _uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import canvas_research_service as crs
from app.services.conversation_service import ConversationService

pytestmark = pytest.mark.asyncio


async def _collect(stream):
    out = []
    async for chunk in stream:
        out.append(chunk)
    return out


def _parse_events(chunks):
    events = []
    for c in chunks:
        text = c.decode() if isinstance(c, (bytes, bytearray)) else c
        for line in text.splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[len("data: "):]))
    return events


class _FakeSkillResult:
    def __init__(self, output):
        self.output = output


async def test_auto_fill_then_brief(canvas_project_with_version, db_session, monkeypatch):
    project_id, version_id = canvas_project_with_version
    proposal = {
        "mode": "auto", "boards": [{
            "board_key": "company_intro", "board_title": "企业介绍",
            "nodes": [{"node_key": "company_profile", "node_title": "企业简介",
                       "points": ["成立于 2015 年"], "citations": [], "pending_questions": []}],
        }], "summary": {"key_points": [], "missing_info": []},
    }
    skill_output = {
        "proposal_sections": [{"title": "需求理解", "content": "基于画布画像"}],
        "citations": [], "missing_info": [],
    }
    svc = ConversationService()
    monkeypatch.setattr(svc, "save_message", AsyncMock())
    monkeypatch.setattr(svc, "_load_ref_docs_context", AsyncMock(return_value=(None, [])))
    runner = MagicMock()
    runner.run_with_react = AsyncMock(return_value=_FakeSkillResult(skill_output))
    with patch("app.services.search_helper.acquire_web_context",
               AsyncMock(return_value=([], {"status": "ok", "key_points": [], "missing_info": []}))), \
         patch("app.services.canvas_agent_orchestrator.canvas_agent_orchestrator.fill_canvas",
               AsyncMock(return_value={"success": True, "filled_count": 1, "node_ids": [], "errors": []})), \
         patch.object(crs, "build_fill_proposal_from_canvas", AsyncMock(return_value=proposal)), \
         patch("app.skills.runner.SkillRunner", return_value=runner), \
         patch("app.services.conversation_service.get_llm_service", AsyncMock(return_value=AsyncMock())), \
         patch("app.services.embedding_service.get_embedding_service", AsyncMock(return_value=AsyncMock())), \
         patch("app.services.image_service.get_image_service", AsyncMock(return_value=AsyncMock())):
        events = _parse_events(await _collect(svc._handle_auto_fill(
            db_session, _uuid.uuid4(), "帮我介绍一下甲公司", str(project_id)
        )))
    ps = [e for e in events if e.get("type") == "proposal_section"]
    assert ps, "首条 auto 后应 emit Brief(proposal_section)"
    assert ps[0]["data"]["proposal_sections"]  # data 是完整 skill output
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd apps/api && pytest app/tests/test_canvas_brief.py -v`
Expected: FAIL —— 无 proposal_section(Brief 未接)。

- [ ] **Step 3: 在 `_handle_auto_fill` 末尾接 Brief**

在 Task 2 的 canvas_fill_proposal emit **之后**(conversation_service.py:1664 commit 之后、Task 2 emit 之后、1678 summary 之前),接设计 Brief。镜像 `_handle_skill_execution`(conversation_service.py:766-797)的 skill 执行范式:**独立 session + SkillRegistry.get_instance() + SkillContext(user_id=None) + run_with_react**,避免 SQLite 单写者死锁。Brief 复用现有 `proposal_section` block(data = skill output 整体,与 conversation_service.py:865 一致),不新增 design_brief block。

```python
        # 设计 Brief:基于已填画布(企业画像)+ 项目上下文,调 proposal_generation 生成策划案
        try:
            from app.skills.base import SkillContext
            from app.skills.registry import SkillRegistry
            from app.skills.runner import SkillRunner
            from app.db.session import async_session_factory as _asf
            from app.services.embedding_service import get_embedding_service
            from app.services.image_service import get_image_service

            # 把已填画布序列化成企业画像文本(重新派生,解耦 Task 2 变量作用域)
            brief_proposal = await canvas_research_service.build_fill_proposal_from_canvas(
                db, proj_uuid
            )
            profile_text = _serialize_proposal_to_profile(brief_proposal)
            async with _asf() as skill_db:
                skill_ctx = SkillContext(
                    project_id=str(proj_uuid),   # SkillContext.project_id: Optional[str]
                    user_id=None,                # _handle_auto_fill 无 user_id 入参
                    db=skill_db,
                    llm_service=await get_llm_service(skill_db),
                    embedding_service=await get_embedding_service(skill_db),
                    image_service=await get_image_service(skill_db),
                )
                registry = SkillRegistry.get_instance()
                runner = SkillRunner(registry)
                skill_result = await runner.run_with_react(
                    "proposal_generation",
                    {
                        "project_id": str(proj_uuid),
                        "requirement_text": user_message or "",
                        "context_pack": profile_text,
                    },
                    skill_ctx,
                )
            skill_output = getattr(skill_result, "output", None) or {}
            if skill_output:
                yield f"data: {json.dumps({'type': 'proposal_section', 'data': skill_output}, ensure_ascii=False)}\n\n"
        except Exception:
            logger.exception("auto_fill: brief generation failed; continuing")
```

并在 `conversation_service.py` 加模块级序列化 helper(类外,靠近其它模块级 helper,Task 2 的 `canvas_research_service` import 之后即可):

```python
def _serialize_proposal_to_profile(proposal: dict) -> str:
    """把 canvas_fill_proposal 的 Proposal 序列化成企业画像文本,作为 proposal_generation 的 context_pack。"""
    lines = ["【企业画像（来自画布采集填充）】"]
    for board in proposal.get("boards", []):
        lines.append(f"\n## {board.get('board_title','')}")
        for n in board.get("nodes", []):
            pts = n.get("points") or []
            if pts:
                lines.append(f"- {n.get('node_title','')}：{'；'.join(pts)}")
    summary = proposal.get("summary") or {}
    if summary.get("missing_info"):
        lines.append("\n【待确认/缺失信息】：" + "；".join(summary["missing_info"]))
    return "\n".join(lines)
```

> `get_llm_service` 已模块级 import(conversation_service.py:16);`SkillContext`/`SkillRegistry`/`SkillRunner`/`async_session_factory`/`get_embedding_service`/`get_image_service` 在本块**局部 import**(与 _handle_skill_execution:691-695、774-775 一致)。Brief 失败不阻断主流程(画布已填、可见化已 emit)。`proposal_section` block 的 data 是 skill output 整体(conversation_service.py:865 范式),前端既有 proposal_section 渲染不变。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd apps/api && pytest app/tests/test_canvas_brief.py -v`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add apps/api/app/services/conversation_service.py apps/api/app/tests/test_canvas_brief.py
git commit -m "feat(canvas): 首条 auto-fill 后生成设计 Brief(复用 proposal_generation)"
```

---

## 收尾:全量自检

- [ ] **Step 1: 全量后端测试**

Run: `cd apps/api && pytest app/tests/ -v`
Expected: 本次新增 4 个测试文件全绿;记录任何与本次改动无关的既有失败(已知 pre-existing:无)。

- [ ] **Step 2: 前端 tsc + lint**

Run: `cd apps/web && node_modules/.bin/tsc --noEmit && npm run lint`
Expected: 通过。

- [ ] **Step 3: 人工验收(对照 spec 验收标准 7 条)**

1. 首条消息后画布被填,且对话里可见「采集了什么、填进哪些模块」的分组要点 + 来源。→ Task 2+3
2. 后续问答搜到模块相关新信息 → 出现提案(分组 + 来源 + 勾选 + 采纳);无关问题只答不提案。→ Task 6+7
3. 勾选 + 采纳 → 模块内容更新、status=filled、有 NodeSource 溯源、生成新版本(可回退)。→ Task 4+5+7
4. ask 模式绝不自动写库;只有首条 auto 和用户采纳才写。→ Task 6(只 emit 不写)
5. 搜索/LLM 失败 → 对话照常直答,不阻断、不报错。→ 各 try/except
6. 后端测试全绿;前端 tsc + lint 通过。→ Step 1+2
7. (Phase C)画布填充后生成设计 Brief:产物含各章节、有引用追溯、可编辑/版本/导出;无空话。→ Task 8

- [ ] **Step 4: 提交收尾(如有额外修复)**

仅在前面步骤有额外修复时:
```bash
git add -A && git commit -m "test: 收尾修复 + 全量自检通过"
```

---

## 自检笔记(plan 作者)

- **spec 覆盖**:7 条验收标准 → Task 2/3(1)、Task 6/7(2)、Task 4/5/7(3)、Task 6(4)、各 try/except(5)、收尾(6)、Task 8(7)。全覆盖。
- **无占位符**:Task 1 的 `accept_fill_proposal` 是"签名先行、Task 4 填体"的刻意分阶段(不是 TBD),已注明;其余步骤均含完整代码。
- **类型一致**:Proposal 形状(boards→nodes→points/citations/pending_questions + summary)在 Task 1/2/3/4/5/6/7 前后端一致;`accept_fill_proposal` / `acceptCanvasFill` / `/fill-accept` / `CanvasFillAcceptIn` 名称对齐。
- **DRY**:Brief 复用 proposal_section block + proposal_generation skill;auto 派生复用 fill_canvas 结果;反编造约束复用文案(拷贝,不重构 fill_canvas)。
- **风险**:Task 6/8 都改 `conversation_service.py`,但插入点不同(Task 2 在 auto-fill、Task 6 在 conversational、Task 8 在 auto-fill 末尾),顺序执行无冲突;Task 8 复用 Task 2 的 `proposal` 变量需确认作用域可见(plan 已注明 fallback)。
