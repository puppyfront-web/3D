"""Proposal Generation Skill — generates structured proposal with enterprise context."""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillContext, SkillManifest, SkillResult

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个专业的策划案撰写专家。请根据提供的企业画像、项目需求和参考案例，生成一份结构化的策划方案。

严格规则：
1. 只能使用 Context Pack 中提供的案例和文档，禁止编造任何案例
2. 报价、工期、屏幕参数等必须标注"需进一步确认"，禁止编造具体数字
3. 缺失的关键信息必须在 missing_info 中列出
4. 引用的案例必须标注来源
5. 不要承诺最终的投屏效果

策划案应包含以下章节，内容需体现企业六看和技术架构的分析成果：
1. 需求理解 — 基于企业六看综合分析
2. 企业解析摘要 — 提炼六看核心发现 + 技术架构概览
3. 项目背景 — 宏观政策→中观行业→微观定位（三级递进）
4. 项目目标
5. 创意主题（提供 2-3 个方向）
6. 方案亮点
7. 视觉方向 — 结合技术架构的视觉表达
8. 参考案例 — 必须来自案例库
9. 实施建议
10. 风险与待确认事项"""


class ProposalGenerationSkill(BaseSkill):
    """Generates a structured proposal using RAG and company profile."""

    manifest = SkillManifest(
        skill_id="proposal_generation",
        name="策划案生成",
        description="根据企业画像、项目需求和案例库生成策划案初稿",
        category="proposal",
        input_schema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "项目ID（可选，项目工作台场景）"},
                "requirement_text": {"type": "string", "description": "需求描述文本（对话场景）"},
                "template_id": {"type": "string"},
                "sop_workflow_id": {"type": "string"},
            },
            "required": [],
        },
        output_schema={
            "type": "object",
            "properties": {
                "proposal_sections": {"type": "array"},
                "citations": {"type": "array"},
                "missing_info": {"type": "array"},
            },
        },
        required_services=["llm.generate", "knowledge.context_pack", "export.docx"],
        permissions=["read_knowledge", "write_project_output"],
        visibility="internal",
        version="1.2.0",
    )

    async def execute(self, input_data: Dict[str, Any], context: SkillContext) -> SkillResult:
        project_id = input_data.get("project_id")
        requirement_text = input_data.get("requirement_text", input_data.get("user_message", ""))

        if context.llm_service is None:
            return SkillResult(success=False, error="LLM service not available")

        # --- Mode 1: DB-backed (project_id provided) ---
        if project_id and context.db:
            return await self._execute_db_mode(input_data, context)

        # --- Mode 2: Conversation mode ---
        return await self._execute_chat_mode(requirement_text, context)

    async def _execute_chat_mode(
        self,
        requirement_text: str,
        context: SkillContext,
    ) -> SkillResult:
        """Generate proposal from conversation context, no DB dependency."""
        if not requirement_text:
            return SkillResult(
                success=False,
                error="请描述您的需求，例如项目背景、目标、预算范围等。",
                missing_info=["项目背景", "目标", "预算范围"],
            )

        prompt = f"""为以下需求生成一份专业策划方案：

需求描述：
{requirement_text}

请生成包含以下章节的策划案（使用 Markdown 格式）：

## 1. 需求理解
从企业六看的角度综合分析客户需求（向后看历史、向前看规划、向左看竞争、向右看行业、向上看政策、向下看生态位）。
如果信息不足，请标注"需进一步确认"。

## 2. 企业解析摘要
提炼核心发现，如果涉及技术型企业，给出技术架构概览（数据层、控制层、执行层）。

## 3. 项目背景
从三个层级分析：
- **宏观·国家政策**：与项目相关的政策导向
- **中观·行业/城市**：行业趋势或地方实践
- **微观·项目定位**：具体项目定位

## 4. 项目目标
明确项目要达成的目标。

## 5. 创意主题
提供 2-3 个创意方向。

## 6. 方案亮点
列出方案的核心亮点。

## 7. 视觉方向
建议视觉风格、色调、构图方向。

## 8. 实施建议
时间线、资源需求。

## 9. 风险与待确认事项
列出所有需要确认的信息。

注意：
- 报价、工期等具体数字请标注"需进一步确认"
- 缺失信息在末尾列出
- 不要编造案例"""

        proposal_content = await context.llm_service.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.7,
            max_tokens=4000,
        )

        return SkillResult(
            success=True,
            output={
                "content_type": "text/markdown",
                "content": proposal_content,
                "missing_info": ["请核实策划案中的报价和工期信息"],
            },
            missing_info=["请核实策划案中的报价和工期信息"],
        )

    async def _execute_db_mode(
        self,
        input_data: Dict[str, Any],
        context: SkillContext,
    ) -> SkillResult:
        """Generate proposal with full DB context (project, company, cases)."""
        project_id = input_data["project_id"]
        template_id = input_data.get("template_id")
        sop_workflow_id = input_data.get("sop_workflow_id")

        from sqlalchemy import select
        from app.models.project import Project, Company
        from app.models.company_profile import CompanyProfile

        project = await context.db.get(Project, uuid.UUID(project_id))
        if not project:
            return SkillResult(success=False, error=f"Project not found: {project_id}")

        company = await context.db.get(Company, project.company_id)
        company_name = company.name if company else "未知企业"
        industry = company.industry if company else "未知行业"

        # Load company profile with enriched structured data
        profile_result = await context.db.execute(
            select(CompanyProfile).where(CompanyProfile.company_id == project.company_id)
        )
        profile = profile_result.scalar_one_or_none()

        # Build enterprise context from structured profile data
        enterprise_context = ""
        if profile:
            # Render Six Views
            six_views = profile.six_views
            if six_views:
                enterprise_context += self._render_six_views(six_views)

            # Render Technology Architecture
            tech_arch = profile.technology_arch
            if tech_arch:
                enterprise_context += self._render_technology_arch(tech_arch)

            # Render Project Background
            proj_bg = profile.project_background
            if proj_bg:
                enterprise_context += self._render_project_background(proj_bg)

            # Fallback to flat fields if structured data is empty
            if not enterprise_context:
                if profile.strengths:
                    enterprise_context += f"\n企业优势: {profile.strengths}\n"
                if profile.weaknesses:
                    enterprise_context += f"企业劣势: {profile.weaknesses}\n"
                if profile.market_position:
                    enterprise_context += f"市场定位: {profile.market_position}\n"

        # Retrieve cases
        used_cases: List[str] = []
        used_documents: List[str] = []
        used_chunks: List[str] = []
        cases_text = ""

        try:
            from app.rag.retriever import HybridRetriever
            retriever = HybridRetriever(embedding_service=context.embedding_service)
            chunks = await retriever.search(
                query=f"{company_name} {industry} 策划方案",
                top_k=8,
                project_id=project.id,
                db=context.db,
            )
            used_chunks = [c.chunk_id for c in chunks]
            used_documents = list({c.document_id for c in chunks})
        except Exception as e:
            logger.warning("RAG retrieval failed: %s", e)

        from app.models.case import Case
        cases_result = await context.db.execute(
            select(Case)
            .where(Case.is_published == True)
            .order_by(Case.quality_score.desc())
            .limit(3)
        )
        cases = cases_result.scalars().all()
        for c in cases:
            cases_text += f"\n### {c.title}\n客户: {c.client_name}\n挑战: {c.challenge}\n方案: {c.solution}\n成果: {c.results}\n"
            used_cases.append(str(c.id))

        # Load SOP steps if provided
        sop_steps_text = ""
        if sop_workflow_id:
            from app.models.workflow import SOPWorkflow
            sop = await context.db.get(SOPWorkflow, uuid.UUID(sop_workflow_id))
            if sop and sop.steps:
                sop_steps_text = json.dumps(sop.steps, ensure_ascii=False, indent=2)

        # Load prompt template and assemble with framework
        db_template = await self._load_prompt_template(context, "generation")

        prompt = self._assemble_prompt(
            default_prompt=self._default_prompt(),
            db_template=db_template,
            variables={
                "project_name": project.name,
                "client_name": company_name,
                "requirements": project.description or "无详细需求",
                "case_studies": cases_text or "暂无参考案例",
                "company_profile": enterprise_context or "暂无企业画像",
            },
        )

        proposal_content = await context.llm_service.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.7,
            max_tokens=4000,
        )

        # Save generation output
        from app.models.generation import GenerationTask, GenerationOutput

        task = GenerationTask(
            project_id=project.id,
            type="proposal",
            status="completed",
            prompt_used=prompt[:500],
            model_used=getattr(context.llm_service, "_model", "unknown"),
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        context.db.add(task)
        await context.db.flush()

        output = GenerationOutput(
            task_id=task.id,
            content_type="text/markdown",
            content=proposal_content,
            used_cases=used_cases,
            used_documents=used_documents,
            used_chunks=used_chunks,
            used_sop_version="1.0",
        )
        context.db.add(output)
        await context.db.flush()

        project.status = "proposal_draft"
        await context.db.flush()

        return SkillResult(
            success=True,
            output={
                "task_id": str(task.id),
                "output_id": str(output.id),
                "content_type": "text/markdown",
                "content": proposal_content,
                "used_cases": used_cases,
                "used_documents": used_documents,
                "used_chunks": used_chunks,
            },
            used_cases=used_cases,
            used_documents=used_documents,
            used_chunks=used_chunks,
            missing_info=["请核实策划案中的报价和工期信息"],
        )

    @staticmethod
    def _render_six_views(six_views: dict) -> str:
        """Render Six Views into structured text for prompt."""
        lines = ["\n=== 企业六看 ==="]
        dim_map = {
            "backward_history": ("向后看·发展历史", ["founding", "origin", "core_philosophy"]),
            "forward_planning": ("向前看·发展规划", ["strategy", "product_roadmap", "market_expansion"]),
            "left_competitors": ("向左看·竞争对手", ["benchmark_companies", "differentiation"]),
            "right_industry": ("向右看·行业情况", ["trends", "market_landscape"]),
            "upward_policy": ("向上看·政策背景", ["national_policy", "local_policy"]),
            "downward_niche": ("向下看·生态位", ["core_advantage", "irreplaceability"]),
        }
        dim = six_views if isinstance(six_views, dict) else {}
        for key, (label, fields) in dim_map.items():
            data = dim.get(key)
            if not data:
                continue
            if isinstance(data, dict):
                parts = [f"  {f}: {data.get(f, '')}" for f in fields if data.get(f)]
                if parts:
                    lines.append(f"- {label}:")
                    lines.extend(parts)
            elif isinstance(data, list):
                lines.append(f"- {label}: {', '.join(str(x) for x in data)}")
            elif isinstance(data, str):
                lines.append(f"- {label}: {data}")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _render_technology_arch(tech_arch: dict) -> str:
        """Render Technology Architecture into structured text."""
        lines = ["\n=== 技术一张图 ==="]
        arch = tech_arch if isinstance(tech_arch, dict) else {}
        layers = arch.get("layers", [])
        for layer in layers:
            name = layer.get("name", "")
            level = layer.get("level", "")
            desc = layer.get("description", "")
            metaphor = layer.get("metaphor", "")
            level_label = {"top": "顶层", "middle": "中层", "bottom": "底层"}.get(level, level)
            lines.append(f"- [{level_label}] {name}（{metaphor}）: {desc}")
        summary = arch.get("core_technology_summary", "")
        if summary:
            lines.append(f"  核心技术总结: {summary}")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _render_project_background(proj_bg: dict) -> str:
        """Render Project Background into structured text."""
        lines = ["\n=== 项目背景 ==="]
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
                lines.append(f"- {label}: {title}")
                if content:
                    lines.append(f"  {content}")
            elif isinstance(data, str):
                lines.append(f"- {label}: {data}")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _default_prompt() -> str:
        return """为以下项目生成专业策划方案：

项目：{project_name}
客户：{client_name}
需求：{requirements}

参考案例：
{case_studies}

企业画像：
{company_profile}

请生成包含以下章节的策划案（Markdown 格式）：
1. 需求理解 — 基于企业六看综合分析
2. 企业解析摘要 — 六看核心发现 + 技术架构概览
3. 项目背景 — 宏观政策→中观行业→微观定位
4. 项目目标
5. 创意主题（2-3 个方向）
6. 方案亮点
7. 视觉方向
8. 参考案例引用（必须来自上述案例）
9. 实施建议
10. 风险与待确认事项"""
