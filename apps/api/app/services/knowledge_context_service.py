"""KB-first context acquisition for conversational Q&A.

Single entry point for internal knowledge retrieval (documents, cases, talking
points) used by ConversationService before optional web search.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.embedding_service import get_embedding_service
from app.services.settings_service import SettingsService
from app.tools.base import ToolContext
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


def _parse_project_id(project_id: Optional[str]) -> Optional[uuid.UUID]:
    if not project_id:
        return None
    try:
        return uuid.UUID(project_id) if isinstance(project_id, str) else project_id
    except (ValueError, TypeError, AttributeError):
        return None


def _chunk_to_citation(item: Dict[str, Any], index: int) -> Dict[str, Any]:
    source = item.get("source") or "chunk"
    title = item.get("title") or ("案例" if source == "case" else "内部文档")
    page = item.get("page_number")
    section = item.get("section_title")
    loc = []
    if section:
        loc.append(str(section))
    if page is not None:
        loc.append(f"p.{page}")
    cid = item.get("chunk_id")
    return {
        "index": index,
        "source_type": source,
        "title": title,
        "document_id": item.get("document_id") or None,
        "chunk_id": cid if source == "chunk" else None,
        "case_id": cid if source == "case" else None,
        "location": " · ".join(loc) if loc else None,
        "snippet": (item.get("content") or "")[:240],
        "score": item.get("score"),
    }


def build_context_preview_text(hits: List[Any], top_k: int = 8) -> str:
    """Format hits the same way as QA context pack (M2 Lab preview)."""
    lines: List[str] = [
        "【企业内部知识库命中】（回答时必须优先依据以下内容，并在正文标注引用序号如 [1]）"
    ]
    if not hits:
        lines.append(
            "（未命中内部资料 — 请基于已有对话上下文作答；若无依据须明确说明「资料中未找到」，禁止编造。）"
        )
        return "\n\n" + "\n".join(lines) + "\n"

    for i, h in enumerate(hits[:top_k], start=1):
        if hasattr(h, "to_dict"):
            item = h.to_dict()
        elif isinstance(h, dict):
            item = h
        else:
            continue
        snippet = (item.get("content") or "").strip().replace("\n", " ")[:300]
        title = item.get("title") or "文档片段"
        provider_tag = f" [{item.get('provider')}]" if item.get("provider") not in (None, "local") else ""
        lines.append(f"[{i}] {title}{provider_tag}：{snippet}")
    return "\n\n" + "\n".join(lines) + "\n"


async def is_web_search_enabled(db: AsyncSession) -> bool:
    raw = await SettingsService.get_safe(db, "web_search_enabled", "true")
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


async def acquire_kb_context(
    db: AsyncSession,
    query: str,
    *,
    project_id: Optional[str] = None,
    top_k: int = 8,
    include_talking_points: bool = True,
    conversation_id: Optional[uuid.UUID] = None,
) -> Tuple[List[Dict[str, Any]], str, Dict[str, Any]]:
    """Retrieve internal knowledge for a user question.

    Returns:
        citations: normalised list for UI + message metadata
        prompt_block: text block to append to system prompt
        meta: counts and retrieval path summary
    """
    empty_meta: Dict[str, Any] = {
        "chunk_count": 0,
        "case_count": 0,
        "talking_point_count": 0,
        "path": "kb",
    }
    if not query or not query.strip():
        return [], "", empty_meta

    q = query.strip()
    proj_uuid = _parse_project_id(project_id)
    citations: List[Dict[str, Any]] = []
    lines: List[str] = ["【企业内部知识库命中】（回答时必须优先依据以下内容，并在正文标注引用序号如 [1]）"]
    retrieval_log_id: Optional[str] = None

    try:
        embedding_service = await get_embedding_service(db)
    except Exception:
        logger.exception("acquire_kb_context: embedding service unavailable")
        embedding_service = None

    ctx = ToolContext(db=db, embedding_service=embedding_service)

    try:
        from app.rag.retrieval_orchestrator import retrieval_orchestrator

        traced = await retrieval_orchestrator.search(
            db,
            q,
            top_k=top_k,
            project_id=proj_uuid,
            triggered_by="knowledge_qa",
            conversation_id=conversation_id,
        )
        hits = traced.hits
        retrieval_log_id = str(traced.log_id) if traced.log_id else None
        preview = build_context_preview_text(hits, top_k=top_k)
        for i, h in enumerate(hits[:top_k], start=1):
            item = h.to_dict()
            citations.append(_chunk_to_citation(item, i))
        lines = preview.strip().split("\n")
    except Exception:
        logger.exception("acquire_kb_context: retrieval orchestrator failed")

    tool_registry = ToolRegistry.get_instance()

    tp_count = 0
    if include_talking_points:
        tp_tool = tool_registry.get("talking_points_search")
        if tp_tool is not None:
            try:
                tp_result = await tp_tool.execute(
                    {"keyword": q, "limit": 3},
                    ctx,
                )
                if tp_result.success and tp_result.data:
                    tps = tp_result.data.get("talking_points") or []
                    base = len(citations)
                    for j, tp in enumerate(tps[:3], start=1):
                        idx = base + j
                        citations.append(
                            {
                                "index": idx,
                                "source_type": "talking_point",
                                "title": tp.get("title") or "话术",
                                "scenario": tp.get("scenario"),
                                "snippet": (tp.get("content") or "")[:240],
                                "score": None,
                            }
                        )
                        lines.append(
                            f"[{idx}] 话术·{tp.get('title') or '条目'}："
                            f"{(tp.get('content') or '')[:200]}"
                        )
                    tp_count = len(tps[:3])
            except Exception:
                logger.exception("acquire_kb_context: talking_points_search failed")

    chunk_count = sum(1 for c in citations if c.get("source_type") in ("chunk", "case"))
    case_count = sum(1 for c in citations if c.get("source_type") == "case")
    meta = {
        "chunk_count": chunk_count,
        "case_count": case_count,
        "talking_point_count": tp_count,
        "total": len(citations),
        "path": "kb",
        "retrieval_log_id": retrieval_log_id,
    }

    if citations and retrieval_log_id:
        try:
            from app.services.retrieval_trace_service import patch_retrieval_log_context

            await patch_retrieval_log_context(
                db,
                uuid.UUID(retrieval_log_id),
                selected_context={"citations": citations},
                project_id=proj_uuid,
                conversation_id=conversation_id,
            )
        except Exception:
            logger.exception("acquire_kb_context: patch retrieval log failed")

    if not citations:
        return [], build_context_preview_text([], top_k=top_k), meta

    return citations, "\n\n" + "\n".join(lines) + "\n", meta
