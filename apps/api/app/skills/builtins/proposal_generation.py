"""Proposal Generation Skill — generates structured proposal from context."""

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
5. 不要承诺最终的投屏效果"""


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
                "project_id": {"type": "string"},
                "template_id": {"type": "string"},
                "sop_workflow_id": {"type": "string"},
            },
            "required": ["project_id"],
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
        version="1.0.0",
    )

    async def execute(self, input_data: Dict[str, Any], context: SkillContext) -> SkillResult:
        project_id = input_data["project_id"]
        template_id = input_data.get("template_id")
        sop_workflow_id = input_data.get("sop_workflow_id")

        if context.db is None:
            return SkillResult(success=False, error="Database session required")

        # 1. Load project and company
        from sqlalchemy import select
        from app.models.project import Project, Company
        from app.models.company_profile import CompanyProfile

        project = await context.db.get(Project, uuid.UUID(project_id))
        if not project:
            return SkillResult(success=False, error=f"Project not found: {project_id}")

        company = await context.db.get(Company, project.company_id)
        company_name = company.name if company else "未知企业"
        industry = company.industry if company else "未知行业"

        # 2. Load company profile
        profile_result = await context.db.execute(
            select(CompanyProfile).where(CompanyProfile.company_id == project.company_id)
        )
        profile = profile_result.scalar_one_or_none()
        profile_text = ""
        if profile:
            profile_text = f"企业优势: {profile.strengths}\n企业劣势: {profile.weaknesses}\n市场定位: {profile.market_position}"

        # 3. Retrieve cases via case_retrieval skill
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

        # Get cases
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

        # 4. Load SOP steps if provided
        sop_steps_text = ""
        if sop_workflow_id:
            from app.models.workflow import SOPWorkflow
            sop = await context.db.get(SOPWorkflow, uuid.UUID(sop_workflow_id))
            if sop and sop.steps:
                sop_steps_text = json.dumps(sop.steps, ensure_ascii=False, indent=2)

        # 5. Load prompt template
        from app.models.template import PromptTemplate
        template_result = await context.db.execute(
            select(PromptTemplate)
            .where(PromptTemplate.category == "generation")
            .limit(1)
        )
        prompt_template = template_result.scalar_one_or_none()
        template_text = prompt_template.template_text if prompt_template else self._default_prompt()

        # 6. Build prompt
        prompt = template_text
        prompt = prompt.replace("{project_name}", project.name)
        prompt = prompt.replace("{client_name}", company_name)
        prompt = prompt.replace("{requirements}", project.description or "无详细需求")
        prompt = prompt.replace("{case_studies}", cases_text or "暂无参考案例")
        prompt = prompt.replace("{company_profile}", profile_text or "暂无企业画像")

        # 7. Generate proposal via LLM
        if context.llm_service is None:
            return SkillResult(success=False, error="LLM service not available")

        proposal_content = await context.llm_service.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.7,
            max_tokens=4000,
        )

        # 8. Save generation output
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

        # 9. Update project status
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
    def _default_prompt() -> str:
        return """为以下项目生成专业策划方案：

项目：{project_name}
客户：{client_name}
需求：{requirements}

参考案例：
{case_studies}

企业画像：
{company_profile}

请生成包含以下章节的策划案：
1. 需求理解
2. 企业解析摘要
3. 项目目标
4. 创意主题
5. 方案亮点
6. 视觉方向
7. 参考案例引用
8. 实施建议
9. 风险与待确认事项"""
