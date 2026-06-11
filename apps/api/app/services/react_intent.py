"""ReAct Intent Reasoning — multi-turn Thought-Action-Observation for intent classification.

This is the PRIMARY intent detection mechanism. The keyword fast-path in intent_service.py
only handles truly unambiguous cases; everything else comes here for reasoning.

Design:
  Turn 1: detect_domain — understand which business area (幕墙/展厅/文旅/多媒体)
  Turn 2: classify_intent — determine the specific intent (pipeline/skill/visual_concept/etc.)
  Turn 3 (if needed): extract_parameters or ask_user
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.services.intent_service import IntentResult

logger = logging.getLogger(__name__)

_REACT_SYSTEM_PROMPT = """你是花生ONE 展厅+文旅 AI 专家系统的意图推理引擎。
你需要通过多轮推理（Thought-Action-Observation）准确理解用户意图。

## 业务领域
你服务的领域包括：
- curtain_wall: 3D展示幕墙 / 裸眼3D / LED媒体立面 / 数字视觉
- exhibition: 展厅设计 / 企业展厅 / 博物馆 / 规划馆 / 科技馆 / 党建馆
- culture_tourism: 文旅项目 / 文旅夜游 / 沉浸式体验 / 光影秀 / 景区夜游
- multimedia: 多媒体展项 / 互动装置 / 数字沙盘 / AR/VR体验

## 可用 Action（每轮选择一个）
- "detect_domain": 先判断业务领域，为后续分类提供上下文
- "classify_intent": 基于已知信息直接分类意图
- "ask_user": 信息不足时，生成追问文本
- "extract_parameters": 从用户消息中提取结构化参数

## 可路由意图
- "run_skill": 用户明确要求执行某个**单一**专业能力（如"帮我做企业解析"、"生成策划案"）
- "sop_pipeline": 用户要求**完整的端到端方案流程**（多步骤串联：企业解析→策划案→视觉→导出）
- "visual_concept": 用户要求**生成概念图/效果图/渲染图**（进入视觉概念图的交互式生成流程）
- "conversational": 闲聊、追问、解释、修改建议
- "clarify": 信息不足，需要追问
- "action": 确认、编辑、审批

## 可用 skill_id
- company_analysis: 企业/展商/景区解析
- proposal_generation: 策划案生成
- visual_prompt: 视觉 Prompt 生成
- image_generation: 图片生成
- case_retrieval: 案例检索
- export: 方案导出

## 核心判断规则（必须严格遵守）

### sop_pipeline vs run_skill 判断
- 用户要求"设计一套XX方案"、"做一套完整方案"、"从头做方案"、"帮我做一个XX的方案" → sop_pipeline
  这表示用户想要**完整流程**，包含企业解析+策划案+视觉生成多个步骤。
- 用户单独提到"帮我做企业解析"、"生成策划案"、"写个视觉Prompt" → run_skill + 对应 skill_id
  这表示用户只要**某一个能力**。

关键区分点：用户是否在暗示"从头到尾做一套"还是"只要某一个环节"。
- "设计一套展厅方案" → 明确是端到端 → sop_pipeline
- "帮我分析一下这个企业" → 只要企业解析 → run_skill: company_analysis
- "写个策划案" → 只要策划 → run_skill: proposal_generation
- "帮我做一个展厅方案" → 端到端 → sop_pipeline
- "生成展厅效果图" → 概念图 → visual_concept

### visual_concept 判断
- 用户提到"效果图"、"概念图"、"渲染图"、"生图"、"出图"、"视觉方案"、"出概念图" → visual_concept
- 但如果用户说"导出效果图"，这可能是 export → 需要结合上下文判断

### domain 与 intent 的关系
- 即使消息提到"展厅"、"文旅"等关键词，也不代表一定是 sop_pipeline
- 必须结合动词和语境判断：用户是要"整套方案"还是"某个能力"

## 推理规则
1. 第一轮先用 detect_domain 判断业务领域
2. 第二轮基于领域信息用 classify_intent 判断意图
3. 只有 confidence >= 0.7 才设 is_final=true
4. confidence < 0.7 且 turn < max_turns 时，用 ask_user
5. 不要过度推理——如果首轮就能高置信度判断，直接 is_final=true

## 输出格式（每轮必须返回 JSON）
{
  "thought": "分析当前状态和已有信息",
  "action": "action_name",
  "action_input": {},
  "observation": "观察到的信息",
  "is_final": true/false,
  "result": {
    "intent": "...",
    "skill_id": "... 或 null",
    "confidence": 0.0-1.0,
    "missing_info": [],
    "input_data": {},
    "reply_hint": ""
  }
}

只返回 JSON，不要其他内容。"""


@dataclass
class ReActIntentState:
    """Tracks ReAct reasoning state across turns."""

    turn: int = 0
    max_turns: int = 3
    thoughts: List[str] = field(default_factory=list)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    observations: List[str] = field(default_factory=list)

    # Intermediate reasoning results
    detected_domain: Optional[str] = None
    detected_intent: Optional[str] = None
    confidence: float = 0.0

    def to_prompt_context(self) -> str:
        """Build a context string showing previous reasoning steps."""
        if not self.thoughts:
            return ""
        parts = []
        for i, (thought, action, obs) in enumerate(
            zip(self.thoughts, self.actions, self.observations)
        ):
            parts.append(f"Round {i + 1}:")
            parts.append(f"  Thought: {thought}")
            parts.append(f"  Action: {action}")
            parts.append(f"  Observation: {obs}")
        return "\n".join(parts)


async def react_classify(
    message: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    project_context: Optional[Dict[str, Any]] = None,
    llm_service=None,
) -> IntentResult:
    """Run ReAct reasoning loop to classify user intent.

    Falls back to conversational intent if any error occurs.
    """
    state = ReActIntentState()

    for turn in range(state.max_turns):
        state.turn = turn + 1

        # Build prompt for this turn
        prompt = _build_turn_prompt(message, state, conversation_history, project_context)

        try:
            result = await llm_service.generate_json(
                prompt=prompt,
                system_prompt=_REACT_SYSTEM_PROMPT,
                temperature=0.1,
            )
        except Exception:
            logger.exception("ReAct turn %d LLM call failed", state.turn)
            break

        # Parse the response
        thought = result.get("thought", "")
        action = result.get("action", "")
        action_input = result.get("action_input", {})
        observation = result.get("observation", "")
        is_final = result.get("is_final", False)

        state.thoughts.append(thought)
        state.actions.append({"action": action, "input": action_input})
        state.observations.append(observation)

        # Extract intermediate results
        if action == "detect_domain" and action_input.get("domain"):
            state.detected_domain = action_input["domain"]
        if result.get("result"):
            r = result["result"]
            if r.get("confidence", 0) > state.confidence:
                state.detected_intent = r.get("intent")
                state.confidence = r.get("confidence", 0)

        logger.info(
            "ReAct turn %d: thought=%s, action=%s, domain=%s, final=%s",
            state.turn,
            thought[:80],
            action,
            state.detected_domain,
            is_final,
        )

        if is_final:
            return _extract_intent_result(result, state)

    # If we exhausted turns without is_final, use the best result we have
    if state.detected_intent and state.confidence >= 0.5:
        return IntentResult(
            intent=state.detected_intent,
            confidence=state.confidence,
            reply_hint="",
        )

    # Complete fallback — treat as conversational
    return IntentResult(
        intent="conversational",
        confidence=0.3,
        reply_hint="",
    )


def _build_turn_prompt(
    message: str,
    state: ReActIntentState,
    conversation_history: Optional[List[Dict[str, str]]],
    project_context: Optional[Dict[str, Any]],
) -> str:
    """Build the prompt for a single ReAct turn."""
    parts = [f"用户消息：{message}"]

    if state.turn > 1:
        parts.append(f"\n已检测到的业务领域：{state.detected_domain or '未知'}")
        context = state.to_prompt_context()
        if context:
            parts.append(f"\n前几轮推理过程：\n{context}")
        parts.append("\n请基于以上推理继续分析。")
    else:
        # First turn hint — encourage domain detection first
        parts.append("\n请先判断业务领域（detect_domain），再分类意图。如果消息意图非常明确，也可以直接分类（classify_intent）。")

    if conversation_history:
        recent = conversation_history[-6:]
        history_text = "\n".join(
            f"  {m['role']}: {m['content'][:200]}" for m in recent
        )
        parts.append(f"\n最近对话历史：\n{history_text}")

    if project_context:
        parts.append(
            f"\n项目上下文：{json.dumps(project_context, ensure_ascii=False)[:500]}"
        )

    return "\n".join(parts)


def _extract_intent_result(result: Dict[str, Any], state: ReActIntentState) -> IntentResult:
    """Extract the final IntentResult from a ReAct response."""
    r = result.get("result", {})

    intent = r.get("intent", "conversational")
    confidence = float(r.get("confidence", 0.5))

    # Enrich input_data with detected domain if available
    input_data = r.get("input_data", {})
    if state.detected_domain and "domain" not in input_data:
        input_data["domain"] = state.detected_domain

    return IntentResult(
        intent=intent,
        skill_id=r.get("skill_id"),
        confidence=confidence,
        missing_info=r.get("missing_info", []),
        input_data=input_data,
        reply_hint=r.get("reply_hint", ""),
    )
