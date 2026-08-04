"""Abstract LLM service interface and MockLLMService implementation."""

from abc import ABC, abstractmethod
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMService(ABC):
    """Abstract base class for LLM interactions."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """Generate a text completion from a prompt."""

    @abstractmethod
    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
    ) -> Dict[str, Any]:
        """Generate a JSON-structured completion."""

    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """Async generator yielding completion chunks."""

    @abstractmethod
    async def generate_with_history(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000,
    ) -> str:
        """Generate with full multi-turn message history."""

    @abstractmethod
    async def generate_with_history_stream(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """Stream with full multi-turn message history."""


class MockLLMService(LLMService):
    """Mock LLM service that returns realistic placeholder text."""

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """Return a mock text completion based on prompt keywords."""
        # Canvas orchestrator / any caller that pins the contract with
        # 「请严格返回 JSON」 expects a parseable JSON object. Detect the node
        # keys the prompt enumerates and emit a {node_key: [...]} stub so the
        # fill_canvas extract/planning passes produce non-empty `planning`
        # content under MockLLM (otherwise the whole canvas falls back to
        # pending_review and the auto-fill E2E becomes a no-op). Match
        # case-insensitively — prompts use 「JSON」 (uppercase).
        if "请严格返回 json" in prompt.lower():
            return self._mock_node_json(prompt)

        prompt_lower = prompt.lower()

        if "company" in prompt_lower and "analysis" in prompt_lower:
            return self._mock_company_analysis(prompt)
        elif "proposal" in prompt_lower or "需求理解" in prompt:
            return self._mock_proposal(prompt)
        elif "visual" in prompt_lower or "design" in prompt_lower:
            return self._mock_visual_prompt(prompt)
        elif "summary" in prompt_lower:
            return self._mock_summary(prompt)
        else:
            return self._mock_generic(prompt)

    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
    ) -> Dict[str, Any]:
        """Return a mock JSON completion — context-aware based on system_prompt."""
        if system_prompt and "意图推理引擎" in system_prompt:
            # ReAct intent reasoning response
            return self._mock_react_intent(prompt)
        if system_prompt and "意图识别" in system_prompt:
            # Single-shot intent classification response
            return self._mock_intent_classify(prompt)
        return {
            "analysis": "Mock analysis result",
            "confidence": 0.85,
            "key_points": [
                "Identified key market trends",
                "Assessed competitive landscape",
                "Evaluated technical requirements",
            ],
            "recommendations": [
                "Proceed with phased implementation",
                "Allocate dedicated resources for change management",
                "Establish clear success metrics",
            ],
            "metadata": {
                "model": "mock-v1",
                "tokens_used": 450,
            },
        }

    @staticmethod
    def _mock_react_intent(prompt: str) -> Dict[str, Any]:
        """Mock ReAct intent reasoning — classify based on prompt keywords."""
        # Detect intent from the user message in the prompt.
        # Order matters: more specific matches (visual_concept) checked before
        # broader matches (sop_pipeline via "方案") to avoid misrouting.
        if any(kw in prompt for kw in ["概念图", "效果图", "渲染图", "视觉概念"]):
            intent, skill_id = "visual_concept", None
        elif any(kw in prompt for kw in ["图片", "生成图片", "生成一张", "出图", "生图"]):
            intent, skill_id = "run_skill", "image_generation"
        elif any(kw in prompt for kw in ["设计一套", "做一套", "完整方案", "全流程", "端到端", "从零"]):
            intent, skill_id = "sop_pipeline", None
        elif any(kw in prompt for kw in ["方案"]):
            # Broad "方案" match only after more specific patterns failed
            intent, skill_id = "sop_pipeline", None
        elif any(kw in prompt for kw in ["企业解析", "企业分析", "分析企业", "企业画像"]):
            intent, skill_id = "run_skill", "company_analysis"
        elif any(kw in prompt for kw in ["策划案", "生成策划", "策划方案"]):
            intent, skill_id = "run_skill", "proposal_generation"
        elif any(kw in prompt for kw in ["视觉prompt", "视觉策略", "生成视觉"]):
            intent, skill_id = "run_skill", "visual_prompt"
        elif any(kw in prompt for kw in ["案例", "检索", "查找案例"]):
            intent, skill_id = "run_skill", "case_retrieval"
        elif any(kw in prompt for kw in ["导出", "下载"]):
            intent, skill_id = "run_skill", "export"
        else:
            intent, skill_id = "conversational", None

        return {
            "thought": f"Mock reasoning: detected intent as {intent}",
            "action": "classify_intent",
            "action_input": {"intent": intent, "skill_id": skill_id},
            "observation": f"User message maps to {intent}",
            "is_final": True,
            "result": {
                "intent": intent,
                "skill_id": skill_id,
                "confidence": 0.85,
                "missing_info": [],
                "input_data": {"user_message": prompt[:100]},
                "reply_hint": "",
            },
        }

    @staticmethod
    def _mock_intent_classify(prompt: str) -> Dict[str, Any]:
        """Mock single-shot intent classification."""
        result = MockLLMService._mock_react_intent(prompt)
        return result.get("result", {
            "intent": "conversational",
            "confidence": 0.5,
        })

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """Yield mock completion chunks."""
        text = await self.generate(prompt, system_prompt, temperature)
        words = text.split(" ")
        for i, word in enumerate(words):
            chunk = word if i == 0 else f" {word}"
            yield chunk

    async def generate_with_history(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000,
    ) -> str:
        """Generate with multi-turn history — use last user message for mock."""
        last_user = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user = msg.get("content", "")
                break
        return await self.generate(last_user, system_prompt, temperature, max_tokens)

    async def generate_with_history_stream(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """Stream with multi-turn history — use last user message for mock."""
        last_user = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user = msg.get("content", "")
                break
        async for chunk in self.generate_stream(last_user, system_prompt, temperature):
            yield chunk

    # -- Mock content generators --

    @staticmethod
    def _mock_company_analysis(prompt: str) -> str:
        return """Based on our comprehensive analysis:

**Company Strengths:**
- Strong market presence with established brand recognition
- Diversified product portfolio reducing single-market dependency
- Experienced leadership team with proven track record
- Robust technology infrastructure supporting current operations

**Areas for Improvement:**
- Limited digital transformation progress compared to industry leaders
- Legacy system dependencies increasing maintenance overhead
- Talent retention challenges in competitive technical roles

**Market Position:**
The company holds a solid mid-market position with approximately 15-20% market share in their core segments. Brand perception is positive, with particular strength in quality and reliability metrics.

**Strategic Recommendations:**
1. Accelerate cloud migration to reduce infrastructure costs by 30-40%
2. Invest in AI/ML capabilities to enhance product differentiation
3. Develop strategic partnerships to expand into adjacent markets
4. Implement comprehensive talent development and retention programs"""

    @staticmethod
    def _mock_proposal(prompt: str) -> str:
        # PRESALE_DELIVERY_SPEC §6.3 structured Brief: when the prompt asks for
        # the canonical 10-section proposal (检测「需求理解」章节名), return a
        # numbered-headers markdown so _parse_sections_meta produces real
        # sections_meta — without this the auto-fill Brief has empty
        # sections_meta and the章节审核 / 导出门控 E2E cannot exercise the
        # require_human_review path (Task 4 export gate tests would skip).
        if "需求理解" in prompt:
            return """# 售前方案（Mock）

## 1. 需求理解
（Mock）综合六看框架，客户希望基于裸眼3D幕墙实现品牌发布。

## 2. 企业解析摘要
（Mock）企业为核心行业玩家，技术与品牌力具备落地基础。

## 3. 项目背景
（Mock）宏观政策、中观行业、微观定位三层递进。

## 4. 项目目标
（Mock）至少 3 条可衡量目标（待客户确认具体指标）。

## 5. 创意主题
（Mock）2-3 个方向，结合品牌基因与差异化。

## 6. 方案亮点
（Mock）差异化卖点 + 视觉冲击。

## 7. 视觉方向
（Mock）色彩、风格、动效参考。

## 8. 参考案例
（Mock）引用案例库中的真实案例。

## 9. 实施建议
（Mock）预算与工期需人工确认：预算区间待客户反馈，工期约 6-8 周。

## 10. 风险与待确认事项
（Mock）报价、工期、屏幕参数需进一步确认。"""

        return """# Project Proposal

## Executive Summary
This proposal presents a comprehensive solution designed to address the client's strategic objectives through modern technology implementation and proven methodologies.

## Proposed Approach
Our approach combines industry best practices with innovative technologies:
- Phase 1: Discovery and requirements analysis
- Phase 2: Architecture design and planning
- Phase 3: Iterative development with continuous feedback
- Phase 4: Deployment, testing, and optimization

## Expected Outcomes
- 40% improvement in operational efficiency
- 99.9% system availability
- 50% reduction in manual processes
- Enhanced data-driven decision making capabilities

## Investment
Total project investment: $700K - $1.2M over 6-8 months

## Next Steps
We recommend scheduling a detailed discovery session to finalize scope and priorities."""

    @staticmethod
    def _mock_node_json(prompt: str) -> str:
        """Stub for canvas-orchestrator extract/planning passes.

        Those prompts ask the model to return ``{"<node_key>": [...]}`` for
        every node enumerated in the prompt. We extract the node_key list from
        the embedded JSON spec (``[{"node_key": "...", "title": "..."}]``) and
        emit one mock bullet per node so the orchestrator's planning pass has
        real content to write — without that, the auto-fill pipeline produces
        an all-empty canvas and the E2E assertions in
        ``test_presale_main_flow`` cannot exercise the visible-blocks path.

        Returns a JSON string (no code fences) matching the prompt contract.
        """
        import json as _json
        import re as _re

        # Find the node-spec list — the prompt embeds it as JSON. Take the
        # longest bracketed segment we can parse as a list of dicts.
        candidates = _re.findall(r"\[.*?\]", prompt, flags=_re.DOTALL)
        node_keys: list[str] = []
        for seg in sorted(candidates, key=len, reverse=True):
            try:
                parsed = _json.loads(seg)
            except _json.JSONDecodeError:
                continue
            if isinstance(parsed, list) and all(isinstance(x, dict) for x in parsed):
                node_keys = [
                    str(x.get("node_key") or x.get("title") or "")
                    for x in parsed
                    if isinstance(x, dict)
                ]
                node_keys = [k for k in node_keys if k]
                if node_keys:
                    break

        if not node_keys:
            # Fallback: a single generic key so callers still see non-empty
            # JSON rather than a parse error.
            return '{"company_profile": ["（Mock）企业简介要点"]}'

        # Distinguish extract vs planning by a marker in the prompt — planning
        # prompts contain 「撰写文案」/「售前文案」, extract prompts contain
        # 「抽取」/「客观事实」. Copy reads slightly differently but the shape
        # is identical, which is all the orchestrator parses.
        is_planning = any(
            kw in prompt for kw in ("撰写文案", "售前文案", "策划专家")
        )
        label = "售前文案" if is_planning else "客观事实"
        payload = {k: [f"（Mock {label}）{k} 示例要点"] for k in node_keys}
        return _json.dumps(payload, ensure_ascii=False)

    @staticmethod
    def _mock_visual_prompt(prompt: str) -> str:
        return """Visual Design Prompt:

**Color Palette:**
- Primary: #1a73e8 (Professional Blue)
- Secondary: #4285f4 (Sky Blue)
- Accent: #34a853 (Success Green)
- Background: #ffffff (Clean White)
- Text: #202124 (Near Black)

**Typography:**
- Headings: Inter Bold (700/800 weight)
- Body: Inter Regular (400 weight)
- Captions: Inter Light (300 weight)

**Layout Principles:**
- 12-column grid system with generous whitespace
- Card-based content organization
- Consistent 8px spacing scale
- Maximum content width: 1200px

**Key Visual Elements:**
- Subtle gradients and geometric shapes
- Professional photography with blue undertones
- Data visualizations with consistent chart styling
- Outlined icon set with 2px stroke weight"""

    @staticmethod
    def _mock_summary(prompt: str) -> str:
        return "Based on the provided context, this is a comprehensive summary of the key findings and recommendations. The analysis covers strategic alignment, technical feasibility, market positioning, and implementation approach."

    @staticmethod
    def _mock_generic(prompt: str) -> str:
        return f"""Based on the provided input, here is our analysis and recommendations:

1. **Key Finding:** The request involves multiple interconnected factors that require a holistic approach
2. **Analysis:** Our assessment indicates strong potential for positive outcomes with proper execution
3. **Recommendation:** We recommend a phased approach with clear milestones and success criteria
4. **Timeline:** Estimated completion within the proposed timeframe
5. **Risk Assessment:** Low to moderate risk with proper mitigation strategies in place"""


async def get_llm_service(db=None) -> LLMService:
    """Factory function to create the appropriate LLM service.

    Reads config from the database when a session is supplied (priority), else
    from .env. Only ``openai`` / ``custom`` providers are supported — every
    other value (including the legacy ``mock``) RAISES instead of silently
    falling back to MockLLMService. A silent mock fallback served fabricated
    content in production and hid misconfiguration; failing loudly forces the
    operator to configure a real provider in the admin settings UI.

    MockLLMService is kept as a class for tests to inject explicitly via
    monkeypatch; production code must never reach it through this factory.
    """
    if db is not None:
        from app.services.settings_service import SettingsService
        cfg = await SettingsService.get_raw_many(db, [
            "llm_provider", "llm_api_key", "llm_base_url", "llm_model",
        ])
        provider = cfg["llm_provider"]
        api_key = cfg["llm_api_key"]
        base_url = cfg["llm_base_url"]
        model = cfg["llm_model"]
    else:
        provider = settings.llm_provider
        api_key = settings.llm_api_key
        base_url = settings.llm_base_url
        model = settings.llm_model

    if provider in ("openai", "custom"):
        if not api_key:
            raise RuntimeError(
                "LLM provider is set to 'openai'/'custom' but llm_api_key is empty. "
                "Configure it in Admin → 系统设置 before invoking AI features."
            )
        # Hard-fail if the OpenAI package is missing rather than silently
        # downgrading — a missing dependency must surface, not serve fake output.
        from app.services.llm.openai_provider import OpenAILLMService
        return OpenAILLMService(
            api_key=api_key,
            base_url=base_url or None,
            model=model,
        )

    # No mock fallback: an unconfigured/unsupported provider fails loudly.
    raise RuntimeError(
        f"LLM provider '{provider or '(empty)'}' is not configured. "
        "Set llm_provider to 'openai' or 'custom' and provide llm_api_key in "
        "Admin → 系统设置. Mock mode was removed — a missing provider now "
        "fails instead of serving fabricated content."
    )
