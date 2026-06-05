"""Case Retrieval Skill — searches case library based on query."""

import logging
import uuid
from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillContext, SkillManifest, SkillResult

logger = logging.getLogger(__name__)


class CaseRetrievalSkill(BaseSkill):
    """Retrieves matching cases from the knowledge base."""

    manifest = SkillManifest(
        skill_id="case_retrieval",
        name="案例检索",
        description="基于项目需求检索匹配的案例库",
        category="retrieval",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "industry": {"type": "string"},
                "scene": {"type": "string"},
                "top_k": {"type": "integer"},
                "project_id": {"type": "string"},
            },
            "required": ["query"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "cases": {"type": "array"},
            },
        },
        required_services=["knowledge.retrieve"],
        permissions=["read_knowledge"],
        visibility="internal",
        version="1.0.0",
    )

    async def execute(self, input_data: Dict[str, Any], context: SkillContext) -> SkillResult:
        query = input_data["query"]
        industry = input_data.get("industry")
        top_k = input_data.get("top_k", 5)
        project_id = input_data.get("project_id") or context.project_id

        if context.db is None:
            return SkillResult(success=False, error="Database session required")

        # 1. Retrieve document chunks via RAG
        used_chunks: List[str] = []
        used_documents: List[str] = []
        chunk_results = []

        try:
            from app.rag.retriever import HybridRetriever
            retriever = HybridRetriever(embedding_service=context.embedding_service)
            chunks = await retriever.search(
                query=query,
                top_k=top_k,
                project_id=uuid.UUID(project_id) if project_id else None,
                db=context.db,
            )
            chunk_results = [c.to_dict() for c in chunks]
            used_chunks = [c.chunk_id for c in chunks]
            used_documents = list({c.document_id for c in chunks})
        except Exception as e:
            logger.warning("RAG chunk retrieval failed: %s", e)

        # 2. Search cases table
        from sqlalchemy import select
        from app.models.case import Case

        case_query = select(Case).where(Case.is_published == True)
        if industry:
            case_query = case_query.where(Case.industry == industry)
        case_query = case_query.order_by(Case.quality_score.desc()).limit(top_k)

        result = await context.db.execute(case_query)
        cases = result.scalars().all()

        case_list = []
        used_case_ids = []
        for c in cases:
            case_list.append({
                "id": str(c.id),
                "title": c.title,
                "client_name": c.client_name,
                "industry": c.industry,
                "challenge": c.challenge,
                "solution": c.solution,
                "results": c.results,
                "quality_score": c.quality_score,
            })
            used_case_ids.append(str(c.id))

        return SkillResult(
            success=True,
            output={
                "cases": case_list,
                "chunks": chunk_results,
                "total_cases": len(case_list),
                "total_chunks": len(chunk_results),
            },
            used_cases=used_case_ids,
            used_documents=used_documents,
            used_chunks=used_chunks,
        )
