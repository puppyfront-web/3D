"""Visual Prompt Generation Skill — generates visual strategy and prompts."""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.core.prompts import GLOBAL_CAPABILITY_CONSTRAINT
from app.skills.base import BaseSkill, SkillContext, SkillManifest, SkillResult

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个视觉创意专家，服务领域包括：

**幕墙视觉**: 3D展示幕墙、裸眼3D、LED媒体立面 — 侧重正面大视角、远距离观看效果、像素化表现
**展厅视觉**: 企业展厅空间、展陈效果、互动装置外观、沉浸式空间 — 侧重室内空间感、人视角、灯光氛围、展品细节
**文旅视觉**: 夜游灯光效果、光影秀场景、景区亮化、沉浸式体验空间 — 侧重户外场景、夜景灯光、大尺度景观
**多媒体视觉**: 互动装置设计、数字沙盘、AR叠加效果、体感交互界面 — 侧重装置特写、交互界面、技术细节

请根据企业提供的信息和视觉风格偏好，生成：
1. 视觉策略（概念、元素、色彩、构图、氛围）
2. 正向 Prompt（用于图片生成的英文提示词）
3. 负向 Prompt（排除的元素）
4. 构图建议
5. 材质方案（如果提供了设计规范）
6. 灯光方案（如果提供了设计规范）

根据项目类型自动选择视觉生成策略：
- curtain_wall: 侧重正面大视角、远距离观看效果、像素化表现
- exhibition: 侧重室内空间感、人视角、灯光氛围、展品细节
- culture_tourism: 侧重户外场景、夜景灯光、大尺度景观
- multimedia: 侧重装置特写、交互界面、技术细节

如果提供了企业六看和技术架构信息，请将这些分析成果融入视觉策略：
- 从企业六看中提取品牌叙事和核心视觉元素
- 从技术架构中提取视觉比喻和表达方式
- 从设计规范中获取材质和灯光参数

严格规则：
- Prompt 必须是英文
- 禁止编造屏幕参数
- 缺失信息标注"需进一步确认"
- 生成 JSON 格式输出""" + GLOBAL_CAPABILITY_CONSTRAINT


class VisualPromptSkill(BaseSkill):
    """Generates visual strategy and positive/negative prompts."""

    manifest = SkillManifest(
        skill_id="visual_prompt",
        name="视觉方案生成",
        description="生成视觉策略、图像描述和构图建议",
        category="visual",
        input_schema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "项目ID（可选）"},
                "style_preferences": {"type": "string", "description": "风格偏好描述"},
                "context_text": {"type": "string", "description": "需求上下文文本（对话场景）"},
                "visual_style_id": {"type": "string"},
            },
            "required": [],
        },
        output_schema={
            "type": "object",
            "properties": {
                "visual_strategy": {"type": "object"},
                "positive_prompt": {"type": "string"},
                "negative_prompt": {"type": "string"},
            },
        },
        required_services=["llm.generate_json"],
        permissions=["read_knowledge", "write_project_output"],
        visibility="internal",
        version="1.2.0",
    )

    async def execute(self, input_data: Dict[str, Any], context: SkillContext) -> SkillResult:
        project_id = input_data.get("project_id")
        context_text = input_data.get("context_text", input_data.get("user_message", ""))
        style_preferences = input_data.get("style_preferences", "科技感、专业、高冲击力")

        if context.llm_service is None:
            return SkillResult(success=False, error="LLM service not available")

        # --- Mode 1: DB-backed ---
        if project_id and context.db:
            return await self._execute_db_mode(input_data, context)

        # --- Mode 2: Conversation mode ---
        visual_context_pack = input_data.get("visual_context_pack")
        return await self._execute_chat_mode(context_text, style_preferences, context, visual_context_pack=visual_context_pack)

    async def _execute_chat_mode(
        self,
        context_text: str,
        style_preferences: str,
        context: SkillContext,
        *,
        visual_context_pack: str | None = None,
    ) -> SkillResult:
        """Generate visual prompt from conversation context."""
        prompt = f"""为以下需求生成视觉设计方案：

需求描述：{context_text}
风格偏好：{style_preferences}

请生成包含以下字段的 JSON：
- visual_strategy: {{ concept, elements, color_palette, composition, mood, brand_narrative }}
- positive_prompt: 英文正向提示词（用于图片生成）
- negative_prompt: 英文负向提示词
- composition_advice: 构图建议
- material_scheme: 材质方案（如有相关信息）
- lighting_scheme: 灯光方案（如有相关信息）
- missing_info: 需进一步确认的信息"""

        # Inject visual context pack (template, styles, brand info)
        if visual_context_pack:
            prompt += (
                f"\n\n---\n\n以下是由系统自动加载的视觉参考资料，请充分融入设计方案：\n\n"
                f"{visual_context_pack}\n\n"
                "重要：请在 positive_prompt 和 visual_strategy 中体现上述风格指导和品牌信息。"
            )

        result = await context.llm_service.generate_json(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
        )

        missing_info = result.get("missing_info", [])
        return SkillResult(
            success=True,
            output={
                "visual_strategy": result.get("visual_strategy", {}),
                "positive_prompt": result.get("positive_prompt", ""),
                "negative_prompt": result.get("negative_prompt", ""),
                "composition_advice": result.get("composition_advice", ""),
                "full_result": result,
            },
            missing_info=missing_info,
        )

    async def _execute_db_mode(
        self,
        input_data: Dict[str, Any],
        context: SkillContext,
    ) -> SkillResult:
        """Generate visual prompt with full DB context."""
        project_id = input_data["project_id"]
        style_preferences = input_data.get("style_preferences", "科技感、专业、高冲击力")
        visual_style_id = input_data.get("visual_style_id")

        from sqlalchemy import select
        from app.models.project import Project, Company
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

        # Load company profile via company_profile_load Tool
        enterprise_context = ""
        if company:
            try:
                cp_tool = registry.get("company_profile_load")
                if cp_tool:
                    cp_result = await cp_tool.execute({"company_id": str(company.id)}, tool_ctx)
                    if cp_result.success and cp_result.data.get("profile"):
                        profile = cp_result.data["profile"]
                        if profile.get("six_views"):
                            enterprise_context += self._render_six_views_for_visual(profile["six_views"])
                        if profile.get("technology_arch"):
                            enterprise_context += self._render_tech_for_visual(profile["technology_arch"])
            except Exception as e:
                logger.warning("Company profile load failed: %s", e)

        # Load visual style via visual_style_match Tool (by ID or list)
        style_info = ""
        material_and_lighting = ""
        if visual_style_id:
            try:
                vs_tool = registry.get("visual_style_match")
                if vs_tool:
                    vs_result = await vs_tool.execute({"limit": 10}, tool_ctx)
                    if vs_result.success and vs_result.data.get("styles"):
                        # Find the matching style by ID
                        matched = next(
                            (s for s in vs_result.data["styles"] if s["id"] == visual_style_id),
                            None,
                        )
                        if matched:
                            style_info = (
                                f"视觉风格: {matched.get('name', '')}\n"
                                f"主色: {matched.get('primary_color', '')}\n"
                                f"辅色: {matched.get('secondary_color', '')}\n"
                                f"强调色: {matched.get('accent_color', '')}\n"
                                f"字体: {matched.get('font_primary', '')}\n"
                                f"布局: {matched.get('layout', '')}\n"
                                f"品牌指南: {matched.get('brand_guidelines', '')}"
                            )
                            if matched.get("material_spec"):
                                material_and_lighting += self._render_material_spec(matched["material_spec"])
                            if matched.get("lighting_spec"):
                                material_and_lighting += self._render_lighting_spec(matched["lighting_spec"])
            except Exception as e:
                logger.warning("Visual style load failed: %s", e)

        # Load prompt template via prompt_template_load Tool
        db_template = None
        try:
            pt_tool = registry.get("prompt_template_load")
            if pt_tool:
                pt_result = await pt_tool.execute({"category": "visual"}, tool_ctx)
                if pt_result.success:
                    db_template = pt_result.data.get("template_text")
        except Exception as e:
            logger.warning("Prompt template load failed: %s", e)

        prompt = self._assemble_prompt(
            default_prompt=self._default_prompt(),
            db_template=db_template,
            variables={
                "project_type": industry,
                "industry": industry,
                "style_preferences": style_preferences,
                "target_audience": f"{company_name}的目标客户",
            },
        )

        # Append runtime context (not template variables — dynamic data)
        if style_info:
            prompt += f"\n\n品牌视觉规范：\n{style_info}"
        if enterprise_context:
            prompt += f"\n\n企业六看分析：\n{enterprise_context}"
        if material_and_lighting:
            prompt += f"\n\n设计规范：\n{material_and_lighting}"

        result = await context.llm_service.generate_json(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
        )

        # Save generation output
        from app.models.generation import GenerationTask, GenerationOutput

        task = GenerationTask(
            project_id=project.id,
            type="visual_prompt",
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
            content_type="application/json",
            content=json.dumps(result, ensure_ascii=False, indent=2),
            used_cases=[],
            used_documents=[],
            used_chunks=[],
            used_sop_version="1.0",
        )
        context.db.add(output)
        await context.db.flush()

        project.status = "visual_design"
        await context.db.flush()

        missing_info = result.get("missing_info", [])
        return SkillResult(
            success=True,
            output={
                "task_id": str(task.id),
                "output_id": str(output.id),
                "visual_strategy": result.get("visual_strategy", {}),
                "positive_prompt": result.get("positive_prompt", ""),
                "negative_prompt": result.get("negative_prompt", ""),
                "composition_advice": result.get("composition_advice", ""),
                "full_result": result,
            },
            missing_info=missing_info,
        )

    @staticmethod
    def _render_six_views_for_visual(six_views: dict) -> str:
        """Extract visual-relevant info from Six Views."""
        lines = []
        sv = six_views if isinstance(six_views, dict) else {}
        # Extract brand narrative from backward_history and forward_planning
        backward = sv.get("backward_history", {})
        if isinstance(backward, dict) and backward.get("core_philosophy"):
            lines.append(f"品牌理念: {backward['core_philosophy']}")
        forward = sv.get("forward_planning", {})
        if isinstance(forward, dict) and forward.get("strategy"):
            lines.append(f"战略方向: {forward['strategy']}")
        # Extract visual preferences from downward_niche
        niche = sv.get("downward_niche", {})
        if isinstance(niche, dict) and niche.get("core_advantage"):
            lines.append(f"核心优势: {niche['core_advantage']}")
        return "\n".join(lines)

    @staticmethod
    def _render_tech_for_visual(tech_arch: dict) -> str:
        """Extract visual-relevant info from Technology Architecture."""
        lines = []
        arch = tech_arch if isinstance(tech_arch, dict) else {}
        visual_metaphor = arch.get("visual_metaphor", "")
        if visual_metaphor:
            lines.append(f"整体视觉比喻: {visual_metaphor}")
        for layer in arch.get("layers", []):
            metaphor = layer.get("metaphor", "")
            name = layer.get("name", "")
            if metaphor:
                lines.append(f"  {name} → 视觉表达: {metaphor}")
        return "\n".join(lines)

    @staticmethod
    def _render_material_spec(material_spec: dict) -> str:
        """Render material spec for prompt."""
        lines = ["\n材质规范:"]
        ms = material_spec if isinstance(material_spec, dict) else {}
        style = ms.get("style", "")
        if style:
            lines.append(f"  风格: {style}")
        for cat in ms.get("categories", []):
            name = cat.get("name", "")
            desc = cat.get("description", "")
            coverage = cat.get("coverage", "")
            lines.append(f"  {name}: {desc} (占比 {coverage})")
        return "\n".join(lines)

    @staticmethod
    def _render_lighting_spec(lighting_spec: dict) -> str:
        """Render lighting spec for prompt."""
        lines = ["\n灯光规范:"]
        ls = lighting_spec if isinstance(lighting_spec, dict) else {}
        atmosphere = ls.get("overall_atmosphere", "")
        if atmosphere:
            lines.append(f"  整体氛围: {atmosphere}")
        ct = ls.get("color_temperature", {})
        if isinstance(ct, dict) and ct.get("range"):
            lines.append(f"  色温: {ct['range']} ({ct.get('description', '')})")
        for layer in ls.get("lighting_layers", []):
            lt = layer.get("type", "")
            desc = layer.get("description", "")
            lines.append(f"  {lt}: {desc}")
        fixture = ls.get("fixture_style", "")
        if fixture:
            lines.append(f"  灯具风格: {fixture}")
        return "\n".join(lines)

    @staticmethod
    def _default_prompt() -> str:
        return """为以下项目生成视觉设计方案：

项目类型：{project_type}
行业：{industry}
风格偏好：{style_preferences}
目标受众：{target_audience}

请生成包含以下字段的 JSON：
- visual_strategy: {concept, elements, color_palette, composition, mood, brand_narrative}
- positive_prompt: 英文正向提示词
- negative_prompt: 英文负向提示词
- composition_advice: 构图建议
- material_scheme: 材质方案
- lighting_scheme: 灯光方案
- missing_info: 需进一步确认的信息"""
