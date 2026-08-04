"""Image Generate Tool — thin adapter over app.services.image_service.

Mirrors web_search.py's design contract:
  - Never raises. Failures surface as status="degraded"/"failed" so callers
    (e.g. visual_prompt / image_generation skill) can keep running.
  - Returns a structured payload so the result can flow straight into an
    Artifact or be marked "未核实" / placeholder by the calling skill.
  - Provider/key/quality all come from runtime DB settings
    (image_provider / image_api_key / image_base_url / image_model / image_quality),
    configured via the admin settings UI — not from the LLM, not from .env at
    tool-call time.

This tool intentionally does NOT persist GenerationTask/GenerationOutput.
Persistence stays the responsibility of the ImageGenerationSkill, keeping the
tool layer a stateless data-access adapter just like the other tools.
"""

import logging
from typing import Any, Dict

from app.tools.base import BaseTool, ToolContext, ToolManifest, ToolResult

logger = logging.getLogger(__name__)


class ImageGenerateTool(BaseTool):
    """Generate an image from a prompt via the configured provider."""

    manifest = ToolManifest(
        tool_id="image_generate",
        name="图片生成",
        description=(
            "调用图片生成服务（OpenAI/SiliconFlow/Zhipu/自定义），返回图片 URL。"
            "Provider 与 API Key 由管理后台 image_* 配置决定。"
            "失败不阻断流程：mock provider 返回占位图，其它失败返回降级标记。"
        ),
        category="generator",
        input_schema={
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "图片生成 Prompt 文本"},
                "negative_prompt": {"type": "string", "description": "负向 Prompt"},
                "width": {"type": "integer", "description": "图片宽度", "default": 1024},
                "height": {"type": "integer", "description": "图片高度", "default": 768},
                "style": {"type": "string", "description": "视觉风格（仅部分 provider 生效）"},
            },
            "required": ["prompt"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["ok", "degraded", "failed"]},
                "image_url": {"type": "string"},
                "provider": {"type": "string"},
                "degraded_reason": {"type": "string"},
                "prompt": {"type": "string"},
                "width": {"type": "integer"},
                "height": {"type": "integer"},
            },
        },
    )

    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        prompt = params.get("prompt", "")
        if not prompt or not str(prompt).strip():
            return ToolResult(success=False, error="prompt is required")

        width = int(params.get("width", 1024) or 1024)
        height = int(params.get("height", 768) or 768)
        style = params.get("style")
        negative_prompt = params.get("negative_prompt")

        if context.db is None:
            # No DB session → cannot read runtime settings → degrade safely.
            return ToolResult(
                success=True,
                data={
                    "status": "failed",
                    "image_url": "",
                    "provider": "none",
                    "degraded_reason": "no_db_session",
                    "prompt": prompt,
                    "width": width,
                    "height": height,
                },
            )

        try:
            from app.services.settings_service import SettingsService

            cfg = await SettingsService.get_raw_many(
                context.db, ["image_provider", "image_api_key"]
            )
            provider_name = (cfg.get("image_provider") or "mock").lower()
            api_key = cfg.get("image_api_key") or ""

            # Real providers all need an API key. If none is configured we
            # degrade instead of letting the provider raise on auth.
            if provider_name not in ("mock", "") and not api_key:
                return ToolResult(
                    success=True,
                    data={
                        "status": "failed",
                        "image_url": "",
                        "provider": provider_name,
                        "degraded_reason": "no_api_key",
                        "prompt": prompt,
                        "width": width,
                        "height": height,
                    },
                )

            from app.services.image_service import get_image_service

            service = await get_image_service(context.db)
            # If the factory fell back to MockImageGenerationService (e.g.
            # provider="mock" or unknown), surface that as "degraded" so the
            # caller knows the URL is a placeholder, not a real generation.
            is_mock = service.__class__.__name__ == "MockImageGenerationService"

            image_url = await service.generate_image_url(
                prompt=prompt,
                width=width,
                height=height,
                style=style,
                negative_prompt=negative_prompt,
            )

            status = "degraded" if is_mock else "ok"
            reason = "mock_provider" if is_mock else ""

            return ToolResult(
                success=True,
                data={
                    "status": status,
                    "image_url": image_url or "",
                    "provider": "mock" if is_mock else provider_name,
                    "degraded_reason": reason,
                    "prompt": prompt,
                    "width": width,
                    "height": height,
                },
            )
        except Exception as e:
            # Last-resort guard: image generation can fail for many reasons
            # (provider down, rate limit, content filter, timeout). We must
            # not break the calling skill — degrade instead.
            logger.exception("ImageGenerateTool unexpected error: %s", e)
            return ToolResult(
                success=True,
                data={
                    "status": "failed",
                    "image_url": "",
                    "provider": "none",
                    "degraded_reason": f"provider_error: {type(e).__name__}",
                    "prompt": prompt,
                    "width": width,
                    "height": height,
                },
            )
