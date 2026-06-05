"""Company Analysis Skill — generates company profile from enterprise info."""

import json
import logging
from typing import Any, Dict

from app.skills.base import BaseSkill, SkillContext, SkillManifest, SkillResult

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个企业分析专家。请根据提供的企业信息和相关资料，生成一份结构化的企业画像分析报告。

要求：
1. 必须基于提供的资料进行分析，禁止编造任何信息
2. 缺失的关键信息必须在 missing_info 中标注"需进一步确认"
3. 分析必须包含行业场景、品牌定位、目标客户、推荐视觉方向
4. 所有分析结论必须可以追溯到输入资料"""

OUTPUT_SCHEMA = """{
  "industry_analysis": "行业场景分析",
  "brand_positioning": "品牌定位",
  "product_service_features": ["产品/服务特点"],
  "target_audience": "目标客户分析",
  "communication_goals": "传播目标",
  "visual_preferences": ["推荐视觉方向"],
  "forbidden_expressions": ["禁用表达"],
  "missing_info": ["需进一步确认的信息"]
}"""


class CompanyAnalysisSkill(BaseSkill):
    """Analyzes a company and generates a structured profile."""

    manifest = SkillManifest(
        skill_id="company_analysis",
        name="企业解析",
        description="分析企业行业、品牌、受众、视觉偏好，生成企业画像",
        category="analysis",
        input_schema={
            "type": "object",
            "properties": {
                "company_id": {"type": "string"},
                "additional_context": {"type": "string"},
            },
            "required": ["company_id"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "company_profile": {"type": "object"},
                "missing_info": {"type": "array"},
            },
        },
        required_services=["llm.generate_json", "knowledge.retrieve"],
        permissions=["read_knowledge", "write_project_output"],
        visibility="internal",
        version="1.0.0",
    )

    async def execute(self, input_data: Dict[str, Any], context: SkillContext) -> SkillResult:
        company_id = input_data["company_id"]
        additional_context = input_data.get("additional_context", "")

        if context.db is None:
            return SkillResult(success=False, error="Database session required")

        # 1. Load company from DB
        from sqlalchemy import select
        from app.models.project import Company

        import uuid
        result = await context.db.execute(
            select(Company).where(Company.id == uuid.UUID(company_id))
        )
        company = result.scalar_one_or_none()
        if not company:
            return SkillResult(success=False, error=f"Company not found: {company_id}")

        # 2. Retrieve related documents if project context available
        used_documents = []
        used_chunks = []
        retrieved_context = ""
        if context.project_id:
            try:
                from app.rag.retriever import HybridRetriever
                retriever = HybridRetriever(embedding_service=context.embedding_service)
                chunks = await retriever.search(
                    query=f"{company.name} {company.industry or ''}",
                    top_k=5,
                    project_id=uuid.UUID(context.project_id),
                    db=context.db,
                )
                retrieved_context = "\n".join([f"- {c.content}" for c in chunks])
                used_chunks = [c.chunk_id for c in chunks]
                used_documents = list({c.document_id for c in chunks})
            except Exception as e:
                logger.warning("RAG retrieval failed during company analysis: %s", e)

        # 3. Load prompt template from DB
        template_text = await self._load_prompt_template(context, "analysis")

        # 4. Build prompt
        prompt = template_text or self._default_prompt()
        prompt = prompt.replace("{company_name}", company.name)
        prompt = prompt.replace("{industry}", company.industry or "未知行业")
        prompt = prompt.replace("{context}", retrieved_context or additional_context or "无额外上下文")

        # 5. Call LLM
        if context.llm_service is None:
            return SkillResult(success=False, error="LLM service not available")

        analysis = await context.llm_service.generate_json(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
        )

        # 6. Save company profile
        from app.models.company_profile import CompanyProfile
        existing = await context.db.execute(
            select(CompanyProfile).where(CompanyProfile.company_id == company.id)
        )
        profile = existing.scalar_one_or_none()

        missing_info = analysis.get("missing_info", [])
        profile_data = {
            "strengths": json.dumps(analysis.get("strengths", []), ensure_ascii=False),
            "weaknesses": json.dumps(analysis.get("weaknesses", []), ensure_ascii=False),
            "market_position": analysis.get("industry_analysis", ""),
            "key_products": json.dumps(analysis.get("product_service_features", []), ensure_ascii=False),
            "competitors": json.dumps(analysis.get("competitors", []), ensure_ascii=False),
            "recent_news": json.dumps(analysis.get("recent_news", []), ensure_ascii=False),
            "culture": analysis.get("culture", ""),
            "financials": json.dumps(analysis.get("financials", {}), ensure_ascii=False),
        }

        if profile:
            for key, value in profile_data.items():
                setattr(profile, key, value)
        else:
            profile = CompanyProfile(
                company_id=company.id,
                **profile_data,
            )
            context.db.add(profile)
        await context.db.flush()

        return SkillResult(
            success=True,
            output={
                "company_profile": {**profile_data, "missing_info": missing_info},
                "analysis": analysis,
            },
            used_documents=used_documents,
            used_chunks=used_chunks,
            missing_info=missing_info,
        )

    @staticmethod
    def _default_prompt() -> str:
        return """分析以下企业并生成结构化画像：

企业名称：{company_name}
行业：{industry}
相关资料：
{context}

请生成包含以下字段的分析：
- industry_analysis: 行业场景分析
- brand_positioning: 品牌定位
- strengths: 企业优势列表
- weaknesses: 企业劣势列表
- product_service_features: 产品/服务特点
- target_audience: 目标客户分析
- communication_goals: 传播目标
- visual_preferences: 推荐视觉方向列表
- forbidden_expressions: 禁用表达列表
- competitors: 竞争对手列表
- culture: 企业文化描述
- financials: 财务概况
- recent_news: 近期动态列表
- missing_info: 需进一步确认的信息列表

格式为 JSON。"""

    async def _load_prompt_template(self, context: SkillContext, category: str) -> str | None:
        """Load a prompt template from the database by category."""
        if context.db is None:
            return None
        from sqlalchemy import select
        from app.models.template import PromptTemplate
        result = await context.db.execute(
            select(PromptTemplate).where(PromptTemplate.category == category).limit(1)
        )
        template = result.scalar_one_or_none()
        return template.template_text if template else None
