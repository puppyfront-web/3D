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

策划案采用10章标准结构，每章内容必须体现对应六看维度的分析成果：

1. 需求理解 — 综合六看全部6个维度（向后看/向前看/向左看/向右看/向上看/向下看），缺一标注「待确认」
   数据来源: six_views 全部维度
2. 企业解析摘要 — 提炼六看核心发现 + 技术架构概览
   数据来源: six_views.backward_history（向后看·品牌故事）+ six_views.downward_niche（向下看·不可替代性）
3. 项目背景 — 三级递进：宏观政策→中观行业→微观定位
   数据来源: six_views.upward_policy（向上看·政策）+ six_views.right_industry（向右看·行业趋势）
4. 项目目标 — 必须包含量化指标（至少3条可衡量目标）
   数据来源: six_views.forward_planning（向前看·发展规划）
5. 创意主题 — 提供2-3个方向，结合品牌基因和差异化
   数据来源: six_views.backward_history（品牌基因）+ six_views.downward_niche（差异化价值）
6. 方案亮点 — 核心功能与价值主张
   数据来源: six_views.left_competitors（向左看·竞品对比）+ six_views.downward_niche（核心优势）
7. 视觉方向 — 结合技术架构的视觉表达策略
   数据来源: technology_architecture + 品牌视觉基因
8. 参考案例 — 必须来自案例库，标注来源 ⚠️ 禁止编造
   数据来源: RAG检索结果
9. 实施建议 — 时间线 + 资源配置 + 运营机制
   数据来源: SOP工作流步骤 + 项目需求
10. 风险与待确认事项 — 风控4维度 + 预算 ⚠️ 需人工审核
    数据来源: quality_rules + 待确认信息汇总

行业特定章节指引（根据项目类型动态插入）：

**展厅项目**: 在"方案亮点"后增加：
- 展陈规划（展区布局、参观动线、展项清单）
- 多媒体展项设计（互动装置、数字内容、技术选型）
- 空间体验设计（灯光氛围、音效设计、场景切换）

**文旅项目**: 在"方案亮点"后增加：
- 文旅资源解读（自然/人文资源梳理）
- 夜游动线设计（游览路线、节点规划、时间节奏）
- 灯光与数字内容（灯光秀、投影、沉浸式体验）
- 运营机制（票务、安全、客流管理）

**幕墙项目**: 使用原始10章结构（不额外增加章节）"""


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
            result = await self._execute_db_mode(input_data, context)
            # Fallback: if DB mode returns empty content, use chat mode with
            # the company_profile data passed from pipeline stage_outputs.
            if result.success and not result.output.get("content"):
                logger.warning("DB mode returned empty proposal content, falling back to chat mode")
                company_profile = input_data.get("company_profile")
                context_pack = input_data.get("context_pack")
                used_cases = input_data.get("used_cases", result.used_cases)
                used_documents = input_data.get("used_documents", result.used_documents)
                used_chunks = input_data.get("used_chunks", result.used_chunks)
                chat_result = await self._execute_chat_mode(
                    requirement_text, company_profile, context,
                    context_pack=context_pack,
                    used_cases=used_cases,
                    used_documents=used_documents,
                    used_chunks=used_chunks,
                )
                if chat_result.success and chat_result.output.get("content"):
                    # Carry over DB references from the failed DB mode
                    chat_result.output["task_id"] = result.output.get("task_id")
                    chat_result.output["output_id"] = result.output.get("output_id")
                    return chat_result
            return result

        # --- Mode 2: Conversation mode ---
        company_profile = input_data.get("company_profile")
        context_pack = input_data.get("context_pack")
        used_cases = input_data.get("used_cases", [])
        used_documents = input_data.get("used_documents", [])
        used_chunks = input_data.get("used_chunks", [])
        return await self._execute_chat_mode(
            requirement_text, company_profile, context,
            context_pack=context_pack,
            used_cases=used_cases,
            used_documents=used_documents,
            used_chunks=used_chunks,
        )

    async def _execute_chat_mode(
        self,
        requirement_text: str,
        company_profile: Any,
        context: SkillContext,
        *,
        context_pack: str | None = None,
        used_cases: list | None = None,
        used_documents: list | None = None,
        used_chunks: list | None = None,
    ) -> SkillResult:
        """Generate proposal from conversation context, no DB dependency."""
        if not requirement_text:
            return SkillResult(
                success=False,
                error="请描述您的需求，例如项目背景、目标、预算范围等。",
                missing_info=["项目背景", "目标", "预算范围"],
            )

        # Build prompt with company profile context
        if company_profile:
            # Extract structured sections from company analysis output
            six_views = company_profile.get("six_views") or (company_profile.get("analysis", {}).get("six_views"))
            tech_arch = company_profile.get("technology_arch") or (company_profile.get("analysis", {}).get("technology_arch"))
            proj_bg = company_profile.get("project_background") or (company_profile.get("analysis", {}).get("project_background"))
            general = company_profile.get("analysis", {})

            context_parts = [
                "以下是已完成的企业画像分析，请直接引用其中的数据，不要再标注为'缺失'或'需补充'：\n"
            ]

            if six_views:
                context_parts.append(f"### 企业六看分析\n{json.dumps(six_views, ensure_ascii=False, indent=2)}\n")
            if tech_arch:
                context_parts.append(f"### 技术架构\n{json.dumps(tech_arch, ensure_ascii=False, indent=2)}\n")
            if proj_bg:
                context_parts.append(f"### 项目背景\n{json.dumps(proj_bg, ensure_ascii=False, indent=2)}\n")
            if general:
                # Include remaining analysis fields (brand, products, etc.)
                remaining = {k: v for k, v in general.items() if k not in ("six_views", "technology_arch", "project_background")}
                if remaining:
                    context_parts.append(f"### 综合分析\n{json.dumps(remaining, ensure_ascii=False, indent=2)}\n")

            context_block = "\n".join(context_parts)
            user_prompt = (
                f"{context_block}\n"
                f"---\n\n项目需求：{requirement_text}\n\n"
                "重要：以上六看分析、技术架构、项目背景已经由企业解析模块生成，"
                "请在策划案中直接引用这些已有数据，不要重复标注为'需进一步确认'。"
                "只有真正缺失的信息（如具体报价、工期、屏幕参数）才标注'需进一步确认'。"
            )
        else:
            user_prompt = requirement_text

        # Inject Context Pack (RAG chunks, cases, SOP, prompt template) if available
        if context_pack:
            user_prompt += (
                f"\n\n---\n\n以下是由系统自动检索的 Context Pack，请充分引用：\n\n{context_pack}\n\n"
                "重要：请在策划案中引用上述知识库片段和案例，特别是：\n"
                "- 第8章「参考案例」必须使用上方提供的案例库数据，标注来源\n"
                "- 第9章「实施建议」参考 SOP 步骤\n"
                "- 引用知识库内容时标注来源文档\n"
            )

        prompt = f"""为以下需求生成一份专业策划方案：

{user_prompt}

请按10章标准结构生成策划案（Markdown 格式），每章体现对应分析维度：

## 1. 需求理解
综合六看分析（向后看历史、向前看规划、向左看竞争、向右看行业、向上看政策、向下看生态位）。
如果信息不足，请标注"需进一步确认"。

## 2. 企业解析摘要
提炼核心发现，如果涉及技术型企业，给出技术架构概览。

## 3. 项目背景
三级递进：
- **宏观·国家政策**：与项目相关的政策导向
- **中观·行业/城市**：行业趋势或地方实践
- **微观·项目定位**：具体项目定位

## 4. 项目目标
必须包含量化指标（至少3条可衡量目标）。

## 5. 创意主题
提供 2-3 个创意方向，结合品牌基因和差异化价值。

## 6. 方案亮点
核心功能与价值主张。

## 7. 视觉方向
建议视觉风格、色调、构图方向。

## 8. 参考案例
⚠️ 如果无真实案例数据，标注"需进一步补充案例"，不要编造。

## 9. 实施建议
时间线（分阶段）、资源配置。

## 10. 风险与待确认事项
⚠️ 覆盖技术、预算、时间三个风险维度。所有报价和工期标注"需进一步确认"。
列出所有需要确认的信息。

注意：
- 缺失信息在末尾列出
- 不要编造案例"""

        proposal_content = await context.llm_service.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.7,
            max_tokens=4000,
        )

        result_output: Dict[str, Any] = {
            "content_type": "text/markdown",
            "content": proposal_content,
            "missing_info": ["请核实策划案中的报价和工期信息"],
        }

        result_kwargs: Dict[str, Any] = {
            "success": True,
            "output": result_output,
            "missing_info": ["请核实策划案中的报价和工期信息"],
        }

        # Include usage tracking if context pack was injected
        if used_cases:
            result_output["used_cases"] = used_cases
            result_kwargs["used_cases"] = used_cases
        if used_documents:
            result_output["used_documents"] = used_documents
            result_kwargs["used_documents"] = used_documents
        if used_chunks:
            result_output["used_chunks"] = used_chunks
            result_kwargs["used_chunks"] = used_chunks

        return SkillResult(**result_kwargs)

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
        from app.tools.registry import ToolRegistry
        from app.tools.base import ToolContext

        tool_ctx = ToolContext(db=context.db, embedding_service=context.embedding_service)
        registry = ToolRegistry.get_instance()

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
            six_views = profile.six_views
            if six_views:
                enterprise_context += self._render_six_views(six_views)
            tech_arch = profile.technology_arch
            if tech_arch:
                enterprise_context += self._render_technology_arch(tech_arch)
            proj_bg = profile.project_background
            if proj_bg:
                enterprise_context += self._render_project_background(proj_bg)
            if not enterprise_context:
                if profile.strengths:
                    enterprise_context += f"\n企业优势: {profile.strengths}\n"
                if profile.weaknesses:
                    enterprise_context += f"企业劣势: {profile.weaknesses}\n"
                if profile.market_position:
                    enterprise_context += f"市场定位: {profile.market_position}\n"

        # Retrieve cases via case_search Tool
        used_cases: List[str] = []
        used_documents: List[str] = []
        used_chunks: List[str] = []
        cases_text = ""

        # RAG chunks via knowledge_search Tool
        try:
            ks_tool = registry.get("knowledge_search")
            if ks_tool:
                ks_result = await ks_tool.execute(
                    {"query": f"{company_name} {industry} 策划方案", "top_k": 8, "project_id": str(project.id)},
                    tool_ctx,
                )
                if ks_result.success and ks_result.data.get("chunks"):
                    ks_chunks = ks_result.data["chunks"]
                    used_chunks = [c["chunk_id"] for c in ks_chunks if c.get("chunk_id")]
                    used_documents = list({c["document_id"] for c in ks_chunks if c.get("document_id")})
        except Exception as e:
            logger.warning("RAG retrieval failed: %s", e)

        # Cases via case_search Tool
        try:
            cs_tool = registry.get("case_search")
            if cs_tool:
                cs_result = await cs_tool.execute({"industry": industry, "limit": 3}, tool_ctx)
                if cs_result.success and cs_result.data.get("cases"):
                    for c in cs_result.data["cases"]:
                        cases_text += f"\n### {c.get('title', '')}\n客户: {c.get('client_name', '')}\n挑战: {c.get('challenge', '')}\n方案: {c.get('solution', '')}\n成果: {c.get('results', '')}\n"
                        used_cases.append(c.get("id", ""))
        except Exception as e:
            logger.warning("Case search failed: %s", e)

        # Load SOP steps via sop_load Tool
        sop_steps_text = ""
        if sop_workflow_id:
            try:
                sop_tool = registry.get("sop_load")
                if sop_tool:
                    sop_result = await sop_tool.execute({"sop_id": sop_workflow_id}, tool_ctx)
                    if sop_result.success and sop_result.data.get("sop"):
                        sop_data = sop_result.data["sop"]
                        if sop_data.get("steps"):
                            sop_steps_text = json.dumps(sop_data["steps"], ensure_ascii=False, indent=2)
            except Exception as e:
                logger.warning("SOP load failed: %s", e)

        # Load prompt template via prompt_template_load Tool
        db_template = None
        try:
            pt_tool = registry.get("prompt_template_load")
            if pt_tool:
                pt_result = await pt_tool.execute({"category": "generation", "template_id": template_id}, tool_ctx)
                if pt_result.success:
                    db_template = pt_result.data.get("template_text")
        except Exception as e:
            logger.warning("Prompt template load failed: %s", e)

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
            max_tokens=6000,
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
            sections_meta=self._parse_sections_meta(proposal_content),
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
    def _parse_sections_meta(markdown_content: str) -> list:
        """Parse markdown into section metadata for human-in-the-loop review.

        Splits on ## N. pattern, creates one entry per section with draft status.
        """
        import re

        sections = []
        # Match patterns like: ## 1. Title or ## 1  Title
        pattern = r"^##\s*\d+[\.\s]+(.+)$"
        lines = markdown_content.split("\n")

        for line in lines:
            match = re.match(pattern, line.strip())
            if match:
                title = match.group(1).strip()
                order = len(sections) + 1
                sections.append({
                    "id": str(uuid.uuid4()),
                    "title": title,
                    "order": order,
                    "status": "draft",
                    "reviewed_by": None,
                    "reviewed_at": None,
                })

        return sections

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

请按10章标准结构生成策划案（Markdown 格式），每章必须体现对应六看维度的分析成果：

## 1. 需求理解
综合六看全部6个维度分析客户需求（向后看历史、向前看规划、向左看竞争、向右看行业、向上看政策、向下看生态位）。
缺一标注「需进一步确认」。

## 2. 企业解析摘要
提炼六看核心发现（向后看·品牌故事 + 向下看·不可替代性），如果涉及技术型企业，给出技术架构概览。

## 3. 项目背景
三级递进分析：
- **宏观·国家政策**：引用向上看维度的政策导向
- **中观·行业/城市**：引用向右看维度的行业趋势
- **微观·项目定位**：具体项目定位和目标

## 4. 项目目标
必须包含量化指标（至少3条可衡量目标），参考向前看维度的发展规划。

## 5. 创意主题
提供2-3个创意方向，结合品牌基因（向后看）和差异化价值（向下看）。

## 6. 方案亮点
核心功能与价值主张，体现与竞品的差异化（向左看）和核心优势（向下看）。

## 7. 视觉方向
建议视觉风格、色调、构图方向，结合技术架构的视觉表达。

## 8. 参考案例
⚠️ 必须来自上述案例库，标注来源。禁止编造任何案例。

## 9. 实施建议
时间线（分阶段）、资源配置、运营机制建议。

## 10. 风险与待确认事项
⚠️ 需人工审核。覆盖技术风险、预算风险、时间风险。所有报价、工期标注「需进一步确认」。
列出所有需要确认的信息。"""
