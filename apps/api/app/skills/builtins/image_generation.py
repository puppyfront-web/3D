"""Image Generation Skill — calls image generation service."""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.skills.base import BaseSkill, SkillContext, SkillManifest, SkillResult

logger = logging.getLogger(__name__)


class ImageGenerationSkill(BaseSkill):
    """Generates images from prompts using the image generation service."""

    manifest = SkillManifest(
        skill_id="image_generation",
        name="图片生成",
        description="根据 Prompt 调用图片生成服务",
        category="visual",
        input_schema={
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "negative_prompt": {"type": "string"},
                "width": {"type": "integer"},
                "height": {"type": "integer"},
                "project_id": {"type": "string"},
                "style": {"type": "string"},
            },
            "required": ["prompt"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "image_url": {"type": "string"},
                "metadata": {"type": "object"},
            },
        },
        required_services=["image.generate"],
        permissions=["write_project_output"],
        visibility="internal",
        version="1.0.0",
    )

    async def execute(self, input_data: Dict[str, Any], context: SkillContext) -> SkillResult:
        prompt = input_data["prompt"]
        negative_prompt = input_data.get("negative_prompt", "")
        width = input_data.get("width", 1024)
        height = input_data.get("height", 576)
        style = input_data.get("style")

        if context.image_service is None:
            return SkillResult(success=False, error="Image generation service not available")

        try:
            image_url = await context.image_service.generate_image_url(
                prompt=prompt,
                width=width,
                height=height,
                style=style,
            )

            # Save generation output if DB available
            output_id = None
            task_id = None
            if context.db is not None and context.project_id:
                from app.models.generation import GenerationTask, GenerationOutput

                task = GenerationTask(
                    project_id=uuid.UUID(context.project_id),
                    type="image_generation",
                    status="completed",
                    prompt_used=prompt,
                    model_used=getattr(context.image_service, "_model", "unknown"),
                    started_at=datetime.now(timezone.utc),
                    completed_at=datetime.now(timezone.utc),
                )
                context.db.add(task)
                await context.db.flush()

                output = GenerationOutput(
                    task_id=task.id,
                    content_type="image/url",
                    content=json.dumps({
                        "url": image_url,
                        "prompt": prompt,
                        "negative_prompt": negative_prompt,
                        "width": width,
                        "height": height,
                        "style": style,
                    }),
                    used_cases=[],
                    used_documents=[],
                    used_chunks=[],
                    used_sop_version="1.0",
                )
                context.db.add(output)
                await context.db.flush()
                task_id = str(task.id)
                output_id = str(output.id)

            return SkillResult(
                success=True,
                output={
                    "image_url": image_url,
                    "task_id": task_id,
                    "output_id": output_id,
                    "metadata": {
                        "prompt": prompt,
                        "negative_prompt": negative_prompt,
                        "width": width,
                        "height": height,
                    },
                },
            )

        except Exception as e:
            logger.exception("Image generation failed")
            return SkillResult(success=False, error=str(e))
