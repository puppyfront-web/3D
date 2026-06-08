"""Company Analysis Skill — generates company profile with Six Views, Tech Arch, and Background."""

import json
import logging
import uuid
from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillContext, SkillManifest, SkillResult

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个企业分析专家，擅长从多维度深度理解企业。

请根据提供的企业信息和相关资料，生成一份**结构化企业画像**，包含四大模块：

## 模块一：企业六看
从 6 个方向分析企业，每个方向需给出具体分析内容：

1. **向后看·发展历史**：企业创始背景、起源故事、核心基因与文化底蕴
2. **向前看·发展规划**：战略方向、产品路线图、市场拓展计划
3. **向左看·竞争对手**：主要竞争对手/对标企业、差异化定位
4. **向右看·行业情况**：行业趋势、市场格局、技术发展方向
5. **向上看·政策背景**：国家层面相关政策、地方产业支持
6. **向下看·生态位**：企业在产业链中的核心位置、不可替代性

## 模块二：技术一张图
分析企业核心技术能力，用分层架构表达：
- **数据管理层**（顶层）：AI、数据平台、智能解决方案等
- **控制层**（中层）：核心技术中枢、系统控制能力
- **执行层**（底层）：硬件、传感器、基础设施等
每层配一个拟人化比喻（如「神经网络」「指挥大脑」「执行之手」）

## 模块三：项目背景
从三个层级分析项目所处的宏观到微观背景：
- **宏观·国家政策**：与项目相关的国家层面政策导向
- **中观·城市/行业**：城市产业实践或行业发展趋势
- **微观·项目定位**：具体项目在此背景下的定位和目标

## 模块四：常规分析
企业优势、劣势、核心产品、目标客户、推荐视觉方向等

严格规则：
1. 必须基于提供的资料分析，禁止编造任何信息
2. 缺失信息必须标注"需进一步确认"
3. 六看各维度如果信息不足，标注缺失而非编造
4. 技术架构如果信息不足，给出高层概览并标注"需进一步确认"
5. 所有结论可追溯到输入资料"""

OUTPUT_SCHEMA = """{
  "six_views": {
    "backward_history": { "founding": "创始背景", "origin": "起源", "core_philosophy": "核心理念" },
    "forward_planning": { "strategy": "战略方向", "product_roadmap": "产品路线", "market_expansion": "市场拓展" },
    "left_competitors": { "benchmark_companies": ["对标企业"], "differentiation": "差异化定位" },
    "right_industry": { "trends": "行业趋势", "market_landscape": "市场格局" },
    "upward_policy": { "national_policy": "国家政策", "local_policy": "地方政策" },
    "downward_niche": { "core_advantage": "核心优势", "irreplaceability": "不可替代性" }
  },
  "technology_arch": {
    "layers": [
      { "name": "层级名", "level": "top/middle/bottom", "description": "描述", "metaphor": "比喻" }
    ],
    "core_technology_summary": "核心技术总结",
    "visual_metaphor": "整体比喻"
  },
  "project_background": {
    "national_policy": { "title": "标题", "content": "内容" },
    "city_or_industry": { "title": "标题", "content": "内容" },
    "project_positioning": { "title": "标题", "content": "内容" }
  },
  "strengths": ["企业优势"],
  "weaknesses": ["企业劣势"],
  "product_service_features": ["产品/服务特点"],
  "target_audience": "目标客户分析",
  "communication_goals": "传播目标",
  "visual_preferences": ["推荐视觉方向"],
  "forbidden_expressions": ["禁用表达"],
  "missing_info": ["需进一步确认的信息"]
}"""


class CompanyAnalysisSkill(BaseSkill):
    """Analyzes a company and generates a structured profile with Six Views, Tech Arch, Background."""

    manifest = SkillManifest(
        skill_id="company_analysis",
        name="企业解析",
        description="分析企业六看、技术架构、项目背景，生成结构化企业画像",
        category="analysis",
        input_schema={
            "type": "object",
            "properties": {
                "company_id": {"type": "string", "description": "数据库企业ID（可选）"},
                "company_info": {"type": "string", "description": "企业信息文本（对话中提供）"},
                "additional_context": {"type": "string"},
            },
            "required": [],
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
        version="1.2.0",
    )

    async def execute(self, input_data: Dict[str, Any], context: SkillContext) -> SkillResult:
        company_id = input_data.get("company_id")
        company_info = input_data.get("company_info", input_data.get("user_message", ""))
        additional_context = input_data.get("additional_context", "")

        if context.llm_service is None:
            return SkillResult(success=False, error="LLM service not available")

        # --- Mode 1: DB-backed (company_id provided) ---
        if company_id and context.db:
            return await self._execute_db_mode(company_id, additional_context, context)

        # --- Mode 2: Conversation mode (no company_id, use text input) ---
        return await self._execute_chat_mode(company_info, additional_context, context)

    async def _execute_chat_mode(
        self,
        company_info: str,
        additional_context: str,
        context: SkillContext,
    ) -> SkillResult:
        """Run analysis purely from user-provided text, no DB dependency."""
        context_parts = []
        if company_info:
            context_parts.append(f"企业信息：\n{company_info}")
        if additional_context:
            context_parts.append(f"补充信息：\n{additional_context}")

        if not context_parts:
            return SkillResult(
                success=False,
                error="请提供企业相关信息，例如企业名称、行业、产品、目标客户等。",
                missing_info=["企业名称", "行业", "主要产品/服务"],
            )

        prompt = "根据以下信息对企业进行深度分析：\n\n" + "\n\n".join(context_parts) + f"""

请严格按照以下 JSON 结构输出分析结果：

{OUTPUT_SCHEMA}

关键要求：
1. six_views 六看分析必须覆盖 6 个方向，每个方向至少给出 2-3 个要点
2. technology_arch 技术架构至少给出 3 层，每层配一个拟人化比喻
3. project_background 项目背景给出宏观→中观→微观 3 个层级
4. 缺失信息用"需进一步确认"标注，不要编造"""

        analysis = await context.llm_service.generate_json(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
        )

        missing_info = analysis.get("missing_info", [])

        return SkillResult(
            success=True,
            output={
                "analysis": analysis,
                "six_views": analysis.get("six_views"),
                "technology_arch": analysis.get("technology_arch"),
                "project_background": analysis.get("project_background"),
                "missing_info": missing_info,
            },
            missing_info=missing_info,
        )

    async def _execute_db_mode(
        self,
        company_id: str,
        additional_context: str,
        context: SkillContext,
    ) -> SkillResult:
        """Run analysis with DB-backed company data."""
        from sqlalchemy import select
        from app.models.project import Company

        result = await context.db.execute(
            select(Company).where(Company.id == uuid.UUID(company_id))
        )
        company = result.scalar_one_or_none()
        if not company:
            return SkillResult(success=False, error=f"Company not found: {company_id}")

        # Retrieve related documents if project context available
        used_documents: List[str] = []
        used_chunks: List[str] = []
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

        # Load prompt template from DB and assemble with framework
        db_template = await self._load_prompt_template(context, "analysis")

        prompt = self._assemble_prompt(
            default_prompt=self._default_prompt(),
            db_template=db_template,
            variables={
                "company_name": company.name,
                "industry": company.industry or "未知行业",
                "context": retrieved_context or additional_context or "无额外上下文",
            },
        )

        analysis = await context.llm_service.generate_json(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
        )

        # Save company profile with enriched structured data
        from app.models.company_profile import CompanyProfile
        existing = await context.db.execute(
            select(CompanyProfile).where(CompanyProfile.company_id == company.id)
        )
        profile = existing.scalar_one_or_none()

        missing_info = analysis.get("missing_info", [])
        profile_data = {
            "strengths": json.dumps(analysis.get("strengths", []), ensure_ascii=False),
            "weaknesses": json.dumps(analysis.get("weaknesses", []), ensure_ascii=False),
            "market_position": analysis.get("right_industry", {}).get("market_landscape", "")
            if isinstance(analysis.get("right_industry"), dict)
            else "",
            "key_products": json.dumps(analysis.get("product_service_features", []), ensure_ascii=False),
            "competitors": json.dumps(analysis.get("left_competitors", {}).get("benchmark_companies", []), ensure_ascii=False)
            if isinstance(analysis.get("left_competitors"), dict)
            else "",
            "recent_news": json.dumps(analysis.get("recent_news", []), ensure_ascii=False),
            "culture": analysis.get("backward_history", {}).get("core_philosophy", "")
            if isinstance(analysis.get("backward_history"), dict)
            else "",
            "financials": json.dumps(analysis.get("financials", {}), ensure_ascii=False),
            # New structured JSON fields
            "six_views": analysis.get("six_views"),
            "technology_arch": analysis.get("technology_arch"),
            "project_background": analysis.get("project_background"),
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
                "six_views": analysis.get("six_views"),
                "technology_arch": analysis.get("technology_arch"),
                "project_background": analysis.get("project_background"),
            },
            used_documents=used_documents,
            used_chunks=used_chunks,
            missing_info=missing_info,
        )

    @staticmethod
    def _default_prompt() -> str:
        return f"""分析以下企业并生成结构化画像（包含企业六看、技术一张图、项目背景）：

企业名称：{{company_name}}
行业：{{industry}}
相关资料：
{{context}}

请严格按照以下 JSON 结构输出：

{OUTPUT_SCHEMA}

关键要求：
1. six_views 六看分析必须覆盖 6 个方向，每个方向至少给出 2-3 个要点
2. technology_arch 技术架构至少给出 3 层，每层配一个拟人化比喻
3. project_background 项目背景给出宏观→中观→微观 3 个层级
4. 缺失信息用"需进一步确认"标注，不要编造
5. 格式为 JSON"""
