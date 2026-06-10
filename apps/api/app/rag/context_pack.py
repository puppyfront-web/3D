"""Context Pack assembly for RAG-powered generation.

Gathers relevant context from multiple sources (retrieved chunks,
case studies, company profiles, SOP steps, technical rules) and
assembles them into a structured prompt-ready context block.
"""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class ContextPack:
    """Assembled context for LLM generation."""

    def __init__(
        self,
        query: str,
        retrieved_chunks: Optional[List[Dict[str, Any]]] = None,
        case_studies: Optional[List[Dict[str, Any]]] = None,
        company_profile: Optional[Dict[str, Any]] = None,
        sop_steps: Optional[List[Dict[str, Any]]] = None,
        technical_rules: Optional[List[Dict[str, Any]]] = None,
        quality_rules: Optional[List[Dict[str, Any]]] = None,
        template_text: Optional[str] = None,
        missing_info: Optional[List[str]] = None,
        additional_context: Optional[str] = None,
    ):
        self.query = query
        self.retrieved_chunks = retrieved_chunks or []
        self.case_studies = case_studies or []
        self.company_profile = company_profile or {}
        self.sop_steps = sop_steps or []
        self.technical_rules = technical_rules or []
        self.quality_rules = quality_rules or []
        self.template_text = template_text
        self.missing_info = missing_info or []
        self.additional_context = additional_context

    def to_prompt(self) -> str:
        """Render the context pack into a single prompt string."""
        sections = []

        if self.company_profile:
            sections.append(self._render_company_profile(self.company_profile))
            # Render enriched structured data if present
            if self.company_profile.get("six_views"):
                sections.append(self._render_six_views(self.company_profile["six_views"]))
            if self.company_profile.get("technology_arch"):
                sections.append(self._render_technology_arch(self.company_profile["technology_arch"]))
            if self.company_profile.get("project_background"):
                sections.append(self._render_project_background(self.company_profile["project_background"]))

        if self.retrieved_chunks:
            sections.append(self._render_retrieved_chunks(self.retrieved_chunks))

        if self.case_studies:
            sections.append(self._render_case_studies(self.case_studies))

        if self.sop_steps:
            sections.append(self._render_sop_steps(self.sop_steps))

        if self.technical_rules:
            sections.append(self._render_technical_rules(self.technical_rules))

        if self.quality_rules:
            sections.append(self._render_quality_rules(self.quality_rules))

        if self.missing_info:
            sections.append(self._render_missing_info(self.missing_info))

        if self.additional_context:
            sections.append(f"## 补充说明\n\n{self.additional_context}")

        if self.template_text:
            sections.append(f"## 模板\n\n{self.template_text}")

        header = f"# 检索上下文：{self.query}\n\n"
        header += f"- 文档片段: {len(self.retrieved_chunks)} 条\n"
        header += f"- 参考案例: {len(self.case_studies)} 个\n"
        header += f"- 技术规则: {len(self.technical_rules)} 条\n"
        header += f"- SOP 步骤: {len(self.sop_steps)} 步\n"
        header += f"- 待确认项: {len(self.missing_info)} 项\n\n"

        return header + "\n---\n\n".join(sections)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the context pack to a dictionary."""
        return {
            "query": self.query,
            "chunk_count": len(self.retrieved_chunks),
            "case_study_count": len(self.case_studies),
            "has_company_profile": bool(self.company_profile),
            "technical_rule_count": len(self.technical_rules),
            "quality_rule_count": len(self.quality_rules),
            "sop_step_count": len(self.sop_steps),
            "missing_info": self.missing_info,
        }

    # -- Private renderers --

    @staticmethod
    def _render_company_profile(profile: Dict[str, Any]) -> str:
        lines = ["## 企业画像", ""]
        if profile.get("name"):
            lines.append(f"**企业名称**: {profile['name']}")
        if profile.get("industry"):
            lines.append(f"**行业**: {profile['industry']}")
        if profile.get("strengths"):
            strengths = profile["strengths"]
            if isinstance(strengths, str):
                try:
                    strengths = json.loads(strengths)
                except (json.JSONDecodeError, TypeError):
                    pass
            if isinstance(strengths, list):
                lines.append(f"**优势**: {', '.join(str(s) for s in strengths)}")
            else:
                lines.append(f"**优势**: {strengths}")
        if profile.get("weaknesses"):
            weaknesses = profile["weaknesses"]
            if isinstance(weaknesses, str):
                try:
                    weaknesses = json.loads(weaknesses)
                except (json.JSONDecodeError, TypeError):
                    pass
            if isinstance(weaknesses, list):
                lines.append(f"**劣势**: {', '.join(str(w) for w in weaknesses)}")
            else:
                lines.append(f"**劣势**: {weaknesses}")
        if profile.get("market_position"):
            lines.append(f"**市场定位**: {profile['market_position']}")
        if profile.get("key_products"):
            products = profile["key_products"]
            if isinstance(products, str):
                try:
                    products = json.loads(products)
                except (json.JSONDecodeError, TypeError):
                    pass
            if isinstance(products, list):
                lines.append(f"**核心产品**: {', '.join(str(p) for p in products)}")
            else:
                lines.append(f"**核心产品**: {products}")
        return "\n".join(lines)

    @staticmethod
    def _render_retrieved_chunks(chunks: List[Dict[str, Any]]) -> str:
        lines = ["## 检索到的文档片段", ""]
        for i, chunk in enumerate(chunks, 1):
            source = chunk.get("document_id", "未知来源")
            page = chunk.get("page_number", "")
            score = chunk.get("score", 0)
            content = chunk.get("content", "")
            page_info = f" (第{page}页)" if page else ""
            lines.append(f"### 片段 {i} [来源: {source[:8]}{page_info}, 相关度: {score}]")
            lines.append(f"```\n{content}\n```")
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _render_case_studies(cases: List[Dict[str, Any]]) -> str:
        lines = ["## 参考案例", ""]
        for i, case in enumerate(cases, 1):
            title = case.get("title", "未命名案例")
            client = case.get("client_name", "")
            lines.append(f"### 案例 {i}: {title}")
            if client:
                lines.append(f"**客户**: {client}")
            if case.get("challenge"):
                lines.append(f"**挑战**: {case['challenge']}")
            if case.get("solution"):
                lines.append(f"**方案**: {case['solution']}")
            if case.get("results"):
                lines.append(f"**成果**: {case['results']}")
            if case.get("quality_score"):
                lines.append(f"**质量评分**: {case['quality_score']}")
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _render_sop_steps(steps: List[Dict[str, Any]]) -> str:
        lines = ["## SOP 流程步骤", ""]
        for step in steps:
            order = step.get("order", "?")
            name = step.get("name", "未命名步骤")
            desc = step.get("description", "")
            lines.append(f"{order}. **{name}**: {desc}")
        return "\n".join(lines)

    @staticmethod
    def _render_technical_rules(rules: List[Dict[str, Any]]) -> str:
        lines = ["## 技术规则", ""]
        for rule in rules:
            name = rule.get("name", "")
            text = rule.get("rule_text", "")
            severity = rule.get("severity", "")
            severity_tag = f" [{severity}]" if severity else ""
            lines.append(f"- **{name}**{severity_tag}: {text}")
        return "\n".join(lines)

    @staticmethod
    def _render_quality_rules(rules: List[Dict[str, Any]]) -> str:
        lines = ["## 质量标准", ""]
        for rule in rules:
            name = rule.get("name", "")
            text = rule.get("rule_text", "")
            lines.append(f"- **{name}**: {text}")
        return "\n".join(lines)

    @staticmethod
    def _render_missing_info(items: List[str]) -> str:
        lines = ["## ⚠️ 待确认信息", ""]
        for item in items:
            lines.append(f"- {item}")
        lines.append("")
        lines.append("**注意**: 以上信息缺失，生成内容中涉及的部分将标注「需进一步确认」。")
        return "\n".join(lines)

    @staticmethod
    def _render_six_views(six_views: Any) -> str:
        """Render Enterprise Six Views into structured text."""
        lines = ["## 企业六看", ""]
        sv = six_views if isinstance(six_views, dict) else {}
        dim_map = {
            "backward_history": ("向后看·发展历史", ["founding", "origin", "core_philosophy"]),
            "forward_planning": ("向前看·发展规划", ["strategy", "product_roadmap", "market_expansion"]),
            "left_competitors": ("向左看·竞争对手", None),
            "right_industry": ("向右看·行业情况", ["trends", "market_landscape"]),
            "upward_policy": ("向上看·政策背景", ["national_policy", "local_policy"]),
            "downward_niche": ("向下看·生态位", ["core_advantage", "irreplaceability"]),
        }
        for key, (label, fields) in dim_map.items():
            data = sv.get(key)
            if not data:
                continue
            if isinstance(data, dict) and fields:
                parts = [f"  - {f}: {data.get(f, '')}" for f in fields if data.get(f)]
                if parts:
                    lines.append(f"**{label}**:")
                    lines.extend(parts)
            elif isinstance(data, dict):
                parts = [f"  - {k}: {v}" for k, v in data.items() if v]
                if parts:
                    lines.append(f"**{label}**:")
                    lines.extend(parts)
            elif isinstance(data, list):
                lines.append(f"**{label}**: {', '.join(str(x) for x in data)}")
            elif isinstance(data, str):
                lines.append(f"**{label}**: {data}")
        return "\n".join(lines)

    @staticmethod
    def _render_technology_arch(tech_arch: Any) -> str:
        """Render Technology Architecture into structured text."""
        lines = ["## 技术一张图", ""]
        arch = tech_arch if isinstance(tech_arch, dict) else {}
        layers = arch.get("layers", [])
        for layer in layers:
            name = layer.get("name", "")
            level = layer.get("level", "")
            desc = layer.get("description", "")
            metaphor = layer.get("metaphor", "")
            level_label = {"top": "顶层", "middle": "中层", "bottom": "底层"}.get(level, level)
            metaphor_tag = f"（{metaphor}）" if metaphor else ""
            lines.append(f"- **[{level_label}] {name}**{metaphor_tag}: {desc}")
        summary = arch.get("core_technology_summary", "")
        if summary:
            lines.append(f"\n核心技术总结: {summary}")
        return "\n".join(lines)

    @staticmethod
    def _render_project_background(proj_bg: Any) -> str:
        """Render Project Background three-level hierarchy."""
        lines = ["## 项目背景", ""]
        bg = proj_bg if isinstance(proj_bg, dict) else {}
        labels = {
            "national_policy": "宏观·国家政策",
            "city_or_industry": "中观·城市/行业",
            "project_positioning": "微观·项目定位",
        }
        for key, label in labels.items():
            data = bg.get(key)
            if not data:
                continue
            if isinstance(data, dict):
                title = data.get("title", "")
                content = data.get("content", "")
                lines.append(f"**{label}**: {title}")
                if content:
                    lines.append(f"  {content}")
            elif isinstance(data, str):
                lines.append(f"**{label}**: {data}")
        return "\n".join(lines)


async def assemble_context_pack(
    query: str,
    project_id: str,
    db: AsyncSession,
    sop_workflow_id: Optional[str] = None,
    template_id: Optional[str] = None,
    additional_instructions: Optional[str] = None,
) -> ContextPack:
    """Assemble a context pack with real data from the database.

    Gathers company profile, retrieved chunks, cases, SOP steps,
    technical rules, and prompt templates into a structured context.

    Uses the Tool layer for all data access instead of direct model queries.
    """
    from app.models.project import Project, Company
    from app.tools.registry import ToolRegistry
    from app.tools.base import ToolContext

    pid = uuid.UUID(project_id)

    # 1. Load project (core entity — direct DB)
    project = await db.get(Project, pid)
    if not project:
        return ContextPack(query=query, missing_info=["项目不存在"])

    # 2. Load company (core entity — direct DB)
    company = await db.get(Company, project.company_id)
    company_profile = {}
    if company:
        company_profile["name"] = company.name
        company_profile["industry"] = company.industry

    # Prepare Tool context
    registry = ToolRegistry.get_instance()
    tool_ctx = ToolContext(db=db)

    # 3. Load company profile via Tool
    if company:
        try:
            cp_tool = registry.get("company_profile_load")
            if cp_tool:
                cp_result = await cp_tool.execute({"company_id": str(company.id)}, tool_ctx)
                if cp_result.success and cp_result.data.get("profile"):
                    p = cp_result.data["profile"]
                    company_profile.update({
                        "strengths": p.get("strengths"),
                        "weaknesses": p.get("weaknesses"),
                        "market_position": p.get("market_position"),
                        "key_products": p.get("key_products"),
                        "six_views": p.get("six_views"),
                        "technology_arch": p.get("technology_arch"),
                        "project_background": p.get("project_background"),
                    })
        except Exception as e:
            logger.warning("Company profile Tool failed: %s", e)

    # 4. RAG retrieval via knowledge_search Tool
    retrieved_chunks = []
    try:
        from app.services.embedding_service import get_embedding_service
        tool_ctx.embedding_service = await get_embedding_service(db=db)
        ks_tool = registry.get("knowledge_search")
        if ks_tool:
            ks_result = await ks_tool.execute(
                {"query": query, "top_k": 10, "project_id": project_id},
                tool_ctx,
            )
            if ks_result.success and ks_result.data.get("chunks"):
                retrieved_chunks = ks_result.data["chunks"]
    except Exception as e:
        logger.warning("RAG retrieval failed during context pack assembly: %s", e)

    # 5. Load matched cases via case_search Tool
    case_studies = []
    try:
        cs_tool = registry.get("case_search")
        if cs_tool:
            cs_params = {"limit": 3}
            if company and company.industry:
                cs_params["industry"] = company.industry
            cs_result = await cs_tool.execute(cs_params, tool_ctx)
            if cs_result.success:
                case_studies = cs_result.data.get("cases", [])
    except Exception as e:
        logger.warning("Case search Tool failed: %s", e)

    # 6. Load SOP steps via sop_load Tool
    sop_steps = []
    if sop_workflow_id:
        try:
            sop_tool = registry.get("sop_load")
            if sop_tool:
                sop_result = await sop_tool.execute({"sop_id": sop_workflow_id}, tool_ctx)
                if sop_result.success and sop_result.data.get("sop"):
                    sop_steps = sop_result.data["sop"].get("steps", [])
        except Exception as e:
            logger.warning("SOP load Tool failed: %s", e)

    # 7. Load technical rules via tech_rule_query Tool
    technical_rules = []
    try:
        tr_tool = registry.get("tech_rule_query")
        if tr_tool:
            tr_result = await tr_tool.execute({"limit": 10}, tool_ctx)
            if tr_result.success:
                technical_rules = tr_result.data.get("rules", [])
    except Exception as e:
        logger.warning("Tech rule query Tool failed: %s", e)

    # 8. Load quality rules via quality_rule_query Tool
    quality_rules = []
    try:
        qr_tool = registry.get("quality_rule_query")
        if qr_tool:
            qr_result = await qr_tool.execute({"limit": 5}, tool_ctx)
            if qr_result.success:
                quality_rules = qr_result.data.get("rules", [])
    except Exception as e:
        logger.warning("Quality rule query Tool failed: %s", e)

    # 9. Load prompt template via prompt_template_load Tool
    template_text = None
    try:
        pt_tool = registry.get("prompt_template_load")
        if pt_tool:
            pt_params = {}
            if template_id:
                pt_params["template_id"] = template_id
            else:
                pt_params["category"] = "generation"
            pt_result = await pt_tool.execute(pt_params, tool_ctx)
            if pt_result.success:
                template_text = pt_result.data.get("template_text")
    except Exception as e:
        logger.warning("Prompt template load Tool failed: %s", e)

    # 10. Collect missing info
    missing_info = []
    if not company_profile.get("strengths"):
        missing_info.append("企业优势信息缺失，需进一步确认")
    if not case_studies:
        missing_info.append("未找到匹配的行业案例，建议补充案例库")
    if not project.description:
        missing_info.append("项目详细需求缺失，需进一步确认")

    return ContextPack(
        query=query,
        retrieved_chunks=retrieved_chunks,
        case_studies=case_studies,
        company_profile=company_profile,
        sop_steps=sop_steps,
        technical_rules=technical_rules,
        quality_rules=quality_rules,
        template_text=template_text,
        missing_info=missing_info,
        additional_context=additional_instructions,
    )
