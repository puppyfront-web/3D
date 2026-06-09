"""Intent detection service — classifies user messages and routes to skills."""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.services.llm_service import get_llm_service

logger = logging.getLogger(__name__)

# Skill keyword mapping for fast-path detection (no LLM needed)
_SKILL_KEYWORDS: Dict[str, List[str]] = {
    "company_analysis": [
        "企业解析", "企业分析", "分析企业", "公司分析", "公司解析",
        "企业画像", "品牌分析", "行业分析",
        "analyze company", "company analysis",
    ],
    "proposal_generation": [
        "策划案", "生成策划", "策划方案", "方案生成", "撰写方案",
        "写方案", "生成方案", "方案策划",
        "generate proposal", "proposal", "create proposal",
    ],
    "visual_prompt": [
        "视觉", "视觉方案", "生成视觉", "视觉策略", "视觉效果",
        "prompt", "生成prompt", "视觉prompt",
        "visual", "generate visual", "visual design",
    ],
    "image_generation": [
        "生图", "生成图片", "出图", "图片生成", "效果图",
        "generate image", "create image", "render",
    ],
    "case_retrieval": [
        "查找案例", "搜索案例", "找案例", "案例检索", "类似案例",
        "find case", "search case", "similar case",
    ],
    "export": [
        "导出", "下载", "导出word", "导出pdf", "导出文档",
        "export", "download", "export document",
    ],
}

# 视觉概念图意图关键词（独立于 run_skill 路由）
_VISUAL_CONCEPT_KEYWORDS: Dict[str, List[str]] = {
    "high": [
        "生成概念图", "出概念图", "视觉概念", "概念设计",
        "生成效果图", "出效果图", "视觉方案",
    ],
    "medium": [
        "裸眼3D", "LED幕墙", "媒体立面", "数字视觉",
        "视觉创意", "概念图", "创意图",
    ],
}

_PIPELINE_KEYWORDS_HIGH = [
    "设计一套3D幕墙方案", "做一套完整方案", "从零开始做方案",
    "端到端方案", "全流程", "从头到尾做", "帮我设计方案",
    "完整方案", "全套方案",
]

_PIPELINE_KEYWORDS_MEDIUM = [
    "3D幕墙方案", "LED方案设计", "裸眼3D方案", "数字展示方案",
    "媒体立面方案", "策划全套",
]

_SYSTEM_PROMPT = """你是 3D 展示幕墙 AI 专家系统的意图识别模块。
根据用户消息判断意图，返回 JSON。

可选意图：
- "run_skill": 用户明确要求执行某个专业能力
- "conversational": 闲聊、追问、解释、修改建议
- "clarify": 信息不足，需要追问
- "action": 确认、编辑、审批、提交表单

可用的 skill_id：
- company_analysis: 企业解析
- proposal_generation: 策划案生成
- visual_prompt: 视觉 Prompt 生成
- image_generation: 图片生成
- case_retrieval: 案例检索
- export: 方案导出

返回格式：
{
  "intent": "run_skill | conversational | clarify | action",
  "skill_id": "skill_id 或 null",
  "confidence": 0.0-1.0,
  "missing_info": ["缺失信息列表"],
  "input_data": {"提取的参数"},
  "reply_hint": "简短回复提示（conversational 模式下用）"
}

只返回 JSON，不要其他内容。"""


@dataclass
class IntentResult:
    """Result of intent detection."""

    intent: str  # run_skill | visual_concept | conversational | clarify | action
    skill_id: Optional[str] = None
    confidence: float = 0.0
    missing_info: List[str] = field(default_factory=list)
    input_data: Dict[str, Any] = field(default_factory=dict)
    reply_hint: str = ""


class IntentDetector:
    """Detects user intent and routes to appropriate skill or conversation mode."""

    def __init__(self) -> None:
        self._llm = None

    async def detect(
        self,
        message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        project_context: Optional[Dict[str, Any]] = None,
        db=None,
    ) -> IntentResult:
        """Analyze a user message and determine the intent.

        Uses fast keyword matching first, falls back to LLM classification.
        """
        # Fast path: keyword matching
        keyword_result = self._keyword_match(message)
        if keyword_result and keyword_result.confidence >= 0.7:
            return keyword_result

        # Slow path: LLM classification
        if self._llm is None:
            self._llm = await get_llm_service(db)
        try:
            return await self._llm_classify(message, conversation_history, project_context)
        except Exception:
            logger.exception("LLM intent detection failed, using fallback")
            # Fallback to conversational
            return IntentResult(
                intent="conversational",
                confidence=0.3,
                reply_hint="抱歉，我暂时无法理解您的意图，请换一种方式描述。",
            )

    def _keyword_match(self, message: str) -> Optional[IntentResult]:
        """快速路径：关键词匹配。"""
        # 先检查视觉概念图关键词
        for level, keywords in _VISUAL_CONCEPT_KEYWORDS.items():
            for kw in keywords:
                if kw in message:
                    confidence = 0.9 if level == "high" else 0.75
                    return IntentResult(
                        intent="visual_concept",
                        confidence=confidence,
                        input_data={"user_message": message},
                    )
        if any(verb in message for verb in ("生成", "画", "绘制", "出")) and any(
            noun in message for noun in ("图片", "图像", "照片", "插画")
        ):
            return IntentResult(
                intent="run_skill",
                skill_id="image_generation",
                confidence=0.7,
                input_data={
                    "user_message": message,
                    "prompt": self._extract_image_prompt(message),
                },
            )
        # Check for SOP pipeline intent
        for kw in _PIPELINE_KEYWORDS_HIGH:
            if kw in message:
                return IntentResult(
                    intent="sop_pipeline",
                    confidence=0.85,
                    input_data={"user_message": message},
                )
        for kw in _PIPELINE_KEYWORDS_MEDIUM:
            if kw in message:
                return IntentResult(
                    intent="sop_pipeline",
                    confidence=0.7,
                    input_data={"user_message": message},
                )
        # 再检查 Skill 关键词
        for skill_id, keywords in _SKILL_KEYWORDS.items():
            for kw in keywords:
                if kw in message:
                    input_data = {"user_message": message}
                    if skill_id == "image_generation":
                        input_data["prompt"] = self._extract_image_prompt(message)
                    return IntentResult(
                        intent="run_skill",
                        skill_id=skill_id,
                        confidence=0.7,
                        input_data=input_data,
                    )
        return None

    @staticmethod
    def classify_pipeline_action(message: str) -> str:
        """Classify user action when pipeline is paused.

        Returns: "confirm" | "modify" | "restart"
        """
        msg = message.strip()
        confirm_words = ["确认", "继续", "下一步", "没问题", "可以", "好的", "通过", "ok", "OK"]
        restart_words = ["重新开始", "从头来", "重来", "重置"]

        for w in restart_words:
            if w in msg:
                return "restart"

        # If message is short and matches a confirm word, treat as confirm
        if len(msg) <= 20:
            for w in confirm_words:
                if w in msg:
                    return "confirm"

        # Otherwise treat as modify feedback
        return "modify"

    @staticmethod
    def _extract_image_prompt(message: str) -> str:
        """Derive an image prompt from a direct image generation request."""
        prompt = message.strip()
        for marker in ("生成图片", "图片生成", "生成一张", "生成一个", "生成", "生图", "出图", "效果图", "图片", "图像"):
            prompt = prompt.replace(marker, " ")
        prompt = " ".join(prompt.split())
        return prompt or message.strip()

    async def _llm_classify(
        self,
        message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        project_context: Optional[Dict[str, Any]] = None,
    ) -> IntentResult:
        """Use LLM to classify user intent."""
        # Build context-aware prompt
        context_parts = [f"用户消息：{message}"]

        if conversation_history:
            recent = conversation_history[-6:]  # Last 3 turns
            history_text = "\n".join(
                f"  {m['role']}: {m['content'][:200]}" for m in recent
            )
            context_parts.append(f"最近对话历史：\n{history_text}")

        if project_context:
            context_parts.append(
                f"项目上下文：{json.dumps(project_context, ensure_ascii=False)[:500]}"
            )

        prompt = "\n".join(context_parts)

        result = await self._llm.generate_json(
            prompt=prompt,
            system_prompt=_SYSTEM_PROMPT,
            temperature=0.1,
        )

        return IntentResult(
            intent=result.get("intent", "conversational"),
            skill_id=result.get("skill_id"),
            confidence=float(result.get("confidence", 0.5)),
            missing_info=result.get("missing_info", []),
            input_data=result.get("input_data", {}),
            reply_hint=result.get("reply_hint", ""),
        )
