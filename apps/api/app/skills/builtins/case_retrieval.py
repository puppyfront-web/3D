"""Case Retrieval Skill — searches case library based on query."""

import logging
from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillContext, SkillManifest, SkillResult
from app.tools.base import ToolContext
from app.tools.registry import ToolRegistry

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
        required_services=["knowledge.retrieve", "case_search"],
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

        tool_ctx = self._tool_context(context)
        registry = ToolRegistry.get_instance()

        # 1. Retrieve document chunks via knowledge_search Tool
        used_chunks: List[str] = []
        used_documents: List[str] = []
        chunk_results = []

        try:
            ks_tool = registry.get("knowledge_search")
            if ks_tool:
                ks_result = await ks_tool.execute(
                    {"query": query, "top_k": top_k, "project_id": project_id},
                    tool_ctx,
                )
                if ks_result.success and ks_result.data.get("chunks"):
                    chunk_results = ks_result.data["chunks"]
                    used_chunks = [c["chunk_id"] for c in chunk_results if c.get("chunk_id")]
                    used_documents = list({c["document_id"] for c in chunk_results if c.get("document_id")})
        except Exception as e:
            logger.warning("RAG chunk retrieval failed: %s", e)

        # 2. Search cases via case_search Tool
        cs_tool = registry.get("case_search")
        if not cs_tool:
            return SkillResult(success=False, error="case_search tool not available")

        cs_result = await cs_tool.execute(
            {"industry": industry, "limit": top_k},
            tool_ctx,
        )

        case_list = cs_result.data.get("cases", []) if cs_result.success else []
        used_case_ids = [c["id"] for c in case_list if c.get("id")]

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
