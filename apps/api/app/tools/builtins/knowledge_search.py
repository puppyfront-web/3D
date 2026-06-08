"""Knowledge Search Tool — RAG semantic + keyword hybrid retrieval."""

from typing import Any, Dict

from app.tools.base import BaseTool, ToolContext, ToolManifest, ToolResult


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

        # Use the existing HybridRetriever
        from app.rag.retriever import HybridRetriever

        retriever = HybridRetriever(embedding_service=context.embedding_service)
        results = await retriever.search(
            query=query,
            top_k=top_k,
            project_id=project_id,
        )

        chunks = [
            {
                "chunk_id": str(r.get("chunk_id", "")),
                "content": r.get("content", ""),
                "score": r.get("score", 0),
                "document_id": str(r.get("document_id", "")),
                "section_title": r.get("section_title"),
                "page_number": r.get("page_number"),
            }
            for r in results
        ]

        return ToolResult(success=True, data={"chunks": chunks, "total": len(chunks)})

    async def _keyword_search(
        self, query: str, top_k: int, project_id: str | None, context: ToolContext
    ) -> ToolResult:
        """Fallback keyword-only search when embedding service is unavailable."""
        from sqlalchemy import select

        from app.models.document import DocumentChunk

        stmt = select(DocumentChunk).where(
            DocumentChunk.content.ilike(f"%{query}%")
        )
        if project_id:
            stmt = stmt.where(DocumentChunk.document_id.in_(
                select(DocumentChunk.document_id).limit(100)
            ))
        stmt = stmt.limit(top_k)

        result = await context.db.execute(stmt)
        chunks = result.scalars().all()

        chunk_list = [
            {
                "chunk_id": str(c.id),
                "content": c.content,
                "score": 0.5,  # keyword match, arbitrary score
                "document_id": str(c.document_id),
                "section_title": c.section_title,
                "page_number": c.page_number,
            }
            for c in chunks
        ]

        return ToolResult(success=True, data={"chunks": chunk_list, "total": len(chunk_list)})
