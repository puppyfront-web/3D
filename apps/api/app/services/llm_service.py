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
        prompt_lower = prompt.lower()

        if "company" in prompt_lower and "analysis" in prompt_lower:
            return self._mock_company_analysis(prompt)
        elif "proposal" in prompt_lower:
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

    If db session is provided, reads config from database (priority) then .env fallback.
    If no db session, falls back to .env only (backward compatible).
    """
    if db is not None:
        from app.services.settings_service import SettingsService
        cfg = await SettingsService.get_raw_many(db, [
            "llm_provider", "llm_api_key", "llm_base_url", "llm_model",
        ])
        provider = cfg["llm_provider"]
    else:
        provider = settings.llm_provider

    if provider in ("openai", "custom"):
        try:
            from app.services.llm.openai_provider import OpenAILLMService
        except ImportError as exc:
            logger.warning("OpenAI LLM provider unavailable, falling back to mock: %s", exc)
            return MockLLMService()

        if db is not None:
            api_key = cfg["llm_api_key"]
            base_url = cfg["llm_base_url"]
            model = cfg["llm_model"]
        else:
            api_key = settings.llm_api_key
            base_url = settings.llm_base_url
            model = settings.llm_model

        return OpenAILLMService(
            api_key=api_key,
            base_url=base_url or None,
            model=model,
        )
    return MockLLMService()
