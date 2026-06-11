"""Knowledge Search Tool — RAG semantic + keyword hybrid retrieval."""

import re
import uuid
from typing import Any, Dict, List, Optional

from app.tools.base import BaseTool, ToolContext, ToolManifest, ToolResult

# CJK (common + extension A) runs vs ASCII alphanumeric runs. CJK text has no
# word spacing, so str.split() returns the whole query as one token and ILIKE
# matches nothing useful — split CJK into per-character search units instead.
_TOKEN_RE = re.compile(r"[一-鿿\s]+|[A-Za-z0-9]+")


def _tokenize_query(query: str, max_tokens: int = 8) -> List[str]:
    """Split a query into ILIKE keyword tokens.

    CJK characters are emitted one-per-token (each is a meaningful search unit);
    ASCII alphanumeric runs are kept as whole words. Tokens shorter than 2 chars
    are dropped (single ASCII letters match too broadly; single CJK chars are
    kept because each carries meaning).
    """
    if not query:
        return []
    tokens: List[str] = []
    for m in _TOKEN_RE.finditer(query):
        s = m.group(0).strip()
        if not s:
            continue
        if s[0].isascii():
            if len(s) > 1:
                tokens.append(s)
        else:
            tokens.extend(list(s))
        if len(tokens) >= max_tokens:
            break
    return tokens[:max_tokens]


def _escape_like(s: str) -> str:
    """Escape ILIKE wildcards so user input is matched literally."""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _parse_project_id(project_id: Optional[str]) -> Optional[uuid.UUID]:
    """Parse a project_id, returning None on malformed input instead of raising.

    A bad project_id (e.g. a non-UUID string slipped into the tool call) should
    degrade to an unfiltered search, not a 500.
    """
    if not project_id:
        return None
    try:
        return uuid.UUID(project_id)
    except (ValueError, TypeError, AttributeError):
        return None


class KnowledgeSearchTool(BaseTool):
    """Search the knowledge base using hybrid retrieval (vector + keyword).

    Wraps the existing HybridRetriever from app.rag.retriever.
    This is the ONLY tool that uses embedding_service for semantic search.
    All other tools query structured data via SQL.
    """

    manifest = ToolManifest(
        tool_id="knowledge_search",
        name="知识库检索",
        description="RAG 混合检索（向量 + 关键词），用于检索文档 chunk 和参考资料",
        category="retrieval",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "检索查询文本"},
                "top_k": {"type": "integer", "description": "返回数量", "default": 10},
                "project_id": {"type": "string", "description": "限定项目范围"},
            },
            "required": ["query"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "chunks": {"type": "array"},
                "total": {"type": "integer"},
            },
        },
    )

    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        query = params.get("query", "")
        if not query:
            return ToolResult(success=False, error="query is required")

        top_k = params.get("top_k", 10)
        project_id = params.get("project_id")

        # If no embedding service, fall back to keyword-only search
        if context.embedding_service is None:
            return await self._keyword_search(query, top_k, project_id, context)

        # Use the existing HybridRetriever against the real database.
        from app.rag.retriever import HybridRetriever

        retriever = HybridRetriever(embedding_service=context.embedding_service)
        project_uuid = _parse_project_id(project_id)
        results = await retriever.search(
            query=query,
            top_k=top_k,
            project_id=project_uuid,
            db=context.db,
        )

        chunks = [
            {
                "chunk_id": r.chunk_id,
                "content": r.content,
                "score": r.score,
                "document_id": r.document_id,
                "section_title": None,
                "page_number": r.page_number,
                "source": r.source,
                "title": r.title,
            }
            for r in results
        ]

        return ToolResult(success=True, data={"chunks": chunks, "total": len(chunks)})

    async def _keyword_search(
        self, query: str, top_k: int, project_id: str | None, context: ToolContext
    ) -> ToolResult:
        """Fallback keyword-only search when embedding service is unavailable."""
        from sqlalchemy import or_, select

        from app.models.document import Document, DocumentChunk

        keywords = _tokenize_query(query)
        if not keywords:
            return ToolResult(success=True, data={"chunks": [], "total": 0})

        stmt = select(DocumentChunk).where(
            or_(*(
                DocumentChunk.content.ilike(f"%{_escape_like(kw)}%", escape="\\")
                for kw in keywords
            ))
        )
        project_uuid = _parse_project_id(project_id)
        if project_uuid:
            stmt = stmt.join(Document).where(Document.project_id == project_uuid)
        stmt = stmt.limit(top_k)

        result = await context.db.execute(stmt)
        chunks = result.scalars().all()

        chunk_list = [
            {
                "chunk_id": str(c.id),
                "content": c.content,
                "score": 0.5,  # keyword match, arbitrary score
                "document_id": str(c.document_id),
                "section_title": None,
                "page_number": c.page_number,
            }
            for c in chunks
        ]

        return ToolResult(success=True, data={"chunks": chunk_list, "total": len(chunk_list)})
