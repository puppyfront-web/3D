"""Intent detection service — classifies user messages and routes to skills.

Design principle: ReAct-first intent detection.
- Only a tiny set of UNAMBIGUOUS keywords are kept as a zero-cost fast-path
- All nuanced intent detection (pipeline vs skill, domain classification, etc.)
  is handled by the ReAct reasoning engine via react_intent.py
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.services.llm_service import get_llm_service

logger = logging.getLogger(__name__)

# How long a cached LLM service stays valid before we re-read model config
# from the DB (admin UI). Keeps long-lived singletons in sync with frontend
# config changes without rebuilding the provider on every call.
_SERVICE_TTL_SECONDS = 30.0

# ── Unambiguous fast-path keywords ─────────────────────────────
# Only include keywords where there is ZERO ambiguity about the intent.
# If a keyword could reasonably match multiple intents, do NOT put it here —
# let ReAct handle it instead.

_UNAMBIGUOUS_KEYWORDS: Dict[str, Dict[str, List[str]]] = {
    # intent → { skill_id | None → [keywords] }
    "run_skill": {
        "export": [
            "导出word", "导出pdf", "导出文档", "export document",
        ],
        "case_retrieval": [
            "查找案例", "搜索案例", "案例检索", "find case", "search case",
        ],
    },
}

# Commands that are clearly conversational / action — no LLM needed
# Shared between _fast_path and classify_pipeline_action
_CONFIRM_WORDS = ["确认", "继续", "下一步", "没问题", "可以", "好的", "通过", "ok", "OK"]
_RESTART_WORDS = ["重新开始", "从头来", "重来", "重置"]


@dataclass
class IntentResult:
    """Result of intent detection."""

    intent: str  # run_skill | sop_pipeline | visual_concept | conversational | clarify | action
    skill_id: Optional[str] = None
    confidence: float = 0.0
    missing_info: List[str] = field(default_factory=list)
    input_data: Dict[str, Any] = field(default_factory=dict)
    reply_hint: str = ""


class IntentDetector:
    """Detects user intent and routes to appropriate skill or conversation mode.

    Priority:
    1. Unambiguous keyword fast-path (zero-cost, only trivial cases)
    2. ReAct reasoning engine (multi-turn Thought-Action-Observation)
    3. Single-shot LLM fallback (if ReAct fails)
    """

    def __init__(self) -> None:
        self._llm = None
        self._llm_cached_at: float = 0.0

    async def detect(
        self,
        message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        project_context: Optional[Dict[str, Any]] = None,
        db=None,
    ) -> IntentResult:
        """Analyze a user message and determine the intent."""
        # 1. Fast path: only the most unambiguous keyword matches
        fast_result = self._fast_path(message)
        if fast_result is not None:
            return fast_result

        # 2. ReAct reasoning (primary path for all non-trivial detection)
        # Rebuild the LLM service if it was never built or the cached one is
        # older than the TTL, so admin-UI model-config changes take effect live.
        if self._llm is None or (time.monotonic() - self._llm_cached_at) > _SERVICE_TTL_SECONDS:
            self._llm = await get_llm_service(db)
            self._llm_cached_at = time.monotonic()
        try:
            from app.services.react_intent import react_classify
            return await react_classify(
                message, conversation_history, project_context,
                llm_service=self._llm,
            )
        except Exception:
            logger.exception("ReAct intent detection failed, falling back to single-shot")
            try:
                return await self._llm_classify(message, conversation_history, project_context)
            except Exception:
                logger.exception("Single-shot LLM intent detection also failed")
                return IntentResult(
                    intent="conversational",
                    confidence=0.3,
                    reply_hint="抱歉，我暂时无法理解您的意图，请换一种方式描述。",
                )

    def _fast_path(self, message: str) -> Optional[IntentResult]:
        """Zero-ambiguity keyword fast-path.

        Only handles cases where the intent is 100% clear from a single keyword.
        Returns None if the message needs ReAct reasoning.
        """
        # Check unambiguous skill keywords
        for intent, skill_map in _UNAMBIGUOUS_KEYWORDS.items():
            for skill_id, keywords in skill_map.items():
                for kw in keywords:
                    if kw in message:
                        return IntentResult(
                            intent=intent,
                            skill_id=skill_id,
                            confidence=0.9,
                            input_data={"user_message": message},
                        )

        # Short confirm/restart actions (only for very short messages)
        msg = message.strip()
        if len(msg) <= 10:
            for w in _RESTART_WORDS:
                if w in msg:
                    return IntentResult(intent="action", confidence=0.9, input_data={"action": "restart"})
            for w in _CONFIRM_WORDS:
                if w in msg:
                    return IntentResult(intent="action", confidence=0.9, input_data={"action": "confirm"})

        # Everything else → ReAct
        return None

    @staticmethod
    def classify_pipeline_action(message: str) -> str:
        """Classify user action when pipeline is paused.

        Returns: "confirm" | "modify" | "restart"
        """
        msg = message.strip()
        modify_hints = ["改", "调", "换", "变", "更", "觉得", "希望", "想要", "再", "一点", "一些", "不过"]

        for w in _RESTART_WORDS:
            if w in msg:
                return "restart"

        for w in modify_hints:
            if w in msg:
                return "modify"

        if len(msg) <= 20:
            for w in _CONFIRM_WORDS:
                if w in msg:
                    return "confirm"

        return "modify"

    async def _llm_classify(
        self,
        message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        project_context: Optional[Dict[str, Any]] = None,
    ) -> IntentResult:
        """Single-shot LLM fallback (only used when ReAct fails)."""
        context_parts = [f"用户消息：{message}"]

        if conversation_history:
            recent = conversation_history[-6:]
            history_text = "\n".join(
                f"  {m['role']}: {m['content'][:200]}" for m in recent
            )
            context_parts.append(f"最近对话历史：\n{history_text}")

        if project_context:
            context_parts.append(
                f"项目上下文：{json.dumps(project_context, ensure_ascii=False)[:500]}"
            )

        system_prompt = """你是花生ONE 展厅+文旅 AI 专家系统的意图识别模块。
根据用户消息判断意图，返回 JSON。

服务领域：
- 3D展示幕墙 / 裸眼3D / LED媒体立面
- 展厅设计与展陈规划
- 文旅项目策划（夜游、沉浸式、光影秀）
- 多媒体展项设计（互动装置、数字沙盘、AR/VR）

可选意图：
- "run_skill": 用户明确要求执行某个专业能力
- "sop_pipeline": 用户要求完整的端到端方案流程（包含企业解析+策划案+视觉生成等步骤）
- "visual_concept": 用户要求生成概念图、效果图
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

判断规则：
- "设计一套XX方案"、"做一套完整方案"、"从头做方案" → sop_pipeline
- 单独要求某个能力（如"帮我做企业解析"、"生成策划案"） → run_skill + 对应 skill_id
- 要求生成图片/效果图/概念图 → visual_concept
- 不确定时选择 conversational

返回格式：
{
  "intent": "run_skill | sop_pipeline | visual_concept | conversational | clarify | action",
  "skill_id": "skill_id 或 null",
  "confidence": 0.0-1.0,
  "missing_info": ["缺失信息列表"],
  "input_data": {"提取的参数"},
  "reply_hint": "简短回复提示（conversational 模式下用）"
}

只返回 JSON，不要其他内容。"""

        prompt = "\n".join(context_parts)
        result = await self._llm.generate_json(
            prompt=prompt,
            system_prompt=system_prompt,
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
