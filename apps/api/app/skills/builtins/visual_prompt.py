"""Visual Prompt Generation Skill — generates visual strategy and prompts."""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillContext, SkillManifest, SkillResult

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个视觉创意专家，专注于3D展示幕墙、裸眼3D、LED媒体立面的视觉设计。

请根据企业提供的信息和视觉风格偏好，生成：
1. 视觉策略（概念、元素、色彩、构图、氛围）
2. 正向 Prompt（用于图片生成的英文提示词）
3. 负向 Prompt（排除的元素）
4. 构图建议

严格规则：
- Prompt 必须是英文
- 禁止编造屏幕参数
- 缺失信息标注"需进一步确认"
- 生成 JSON 格式输出"""


class VisualPromptSkill(BaseSkill):
    """Generates visual strategy and positive/negative prompts."""

    manifest = SkillManifest(
        skill_id="visual_prompt",
        name="视觉 Prompt 生成",
        description="生成视觉策略、正向/负向 Prompt 和构图建议",
        category="visual",
        input_schema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "style_preferences": {"type": "string"},
                "visual_style_id": {"type": "string"},
            },
            "required": ["project_id"],
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
        version="1.0.0",
    )

    async def execute(self, input_data: Dict[str, Any], context: SkillContext) -> SkillResult:
        project_id = input_data["project_id"]
        style_preferences = input_data.get("style_preferences", "科技感、专业、高冲击力")
        visual_style_id = input_data.get("visual_style_id")

        if context.db is None:
            return SkillResult(success=False, error="Database session required")

        from sqlalchemy import select
        from app.models.project import Project, Company

        project = await context.db.get(Project, uuid.UUID(project_id))
        if not project:
            return SkillResult(success=False, error=f"Project not found: {project_id}")

        company = await context.db.get(Company, project.company_id)
        company_name = company.name if company else "未知企业"
        industry = company.industry if company else "未知行业"

        # Load visual style if provided
        style_info = ""
        if visual_style_id:
            from app.models.visual import VisualStyle
            style = await context.db.get(VisualStyle, uuid.UUID(visual_style_id))
            if style:
                style_info = f"视觉风格: {style.name}\n主色: {style.primary_color}\n辅色: {style.secondary_color}\n强调色: {style.accent_color}\n字体: {style.font_primary}\n布局: {style.layout}\n品牌指南: {style.brand_guidelines}"

        # Load prompt template
        from app.models.template import PromptTemplate
        template_result = await context.db.execute(
            select(PromptTemplate)
            .where(PromptTemplate.category == "visual")
            .limit(1)
        )
        prompt_template = template_result.scalar_one_or_none()
        template_text = prompt_template.template_text if prompt_template else self._default_prompt()

        prompt = template_text
        prompt = prompt.replace("{project_type}", industry)
        prompt = prompt.replace("{industry}", industry)
        prompt = prompt.replace("{style_preferences}", style_preferences)
        prompt = prompt.replace("{target_audience}", f"{company_name}的目标客户")
        if style_info:
            prompt += f"\n\n品牌视觉规范：\n{style_info}"

        # Generate visual prompt via LLM
        if context.llm_service is None:
            return SkillResult(success=False, error="LLM service not available")

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
    def _default_prompt() -> str:
        return """为以下项目生成视觉设计方案：

项目类型：{project_type}
行业：{industry}
风格偏好：{style_preferences}
目标受众：{target_audience}

请生成包含以下字段的 JSON：
- visual_strategy: {concept, elements, color_palette, composition, mood}
- positive_prompt: 英文正向提示词
- negative_prompt: 英文负向提示词
- composition_advice: 构图建议
- missing_info: 需进一步确认的信息"""
