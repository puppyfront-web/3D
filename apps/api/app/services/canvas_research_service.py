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
from app.services.canvas_service import canvas_service
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
    """版本化写回:新建 ProjectVersion 快照 → 按 node_key 合并节点 → 追加 NodeSource。

    body: {"boards":[{"board_key","nodes":[{"node_key","points","citations"}]}],
           "change_summary"?: str}
    合并语义(与 adopt_node_draft 一致):保留 ui_suggestion/extracted,覆盖 planning/pending,
    status=filled;每条 citation(type=web_search 或缺省)写一行 NodeSource(web_search)。

    create_version 会把当前画布的 groups/nodes/edges 深拷贝到新版本(canvas_service
    ._clone_canvas_into_version 把 content 原样复制),所以合并读到的 old.content 已包含
    旧版本上既有的 ui_suggestion/extracted,无需跨版本回查。
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

    # 建 (board_key -> {node_key -> node}) 查表
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
