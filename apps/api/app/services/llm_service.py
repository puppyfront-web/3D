"""Abstract LLM service interface and MockLLMService implementation."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.core.config import settings


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
    ):
        """Async generator yielding completion chunks."""


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
        """Return a mock JSON completion."""
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

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ):
        """Yield mock completion chunks."""
        text = await self.generate(prompt, system_prompt, temperature)
        words = text.split(" ")
        for i, word in enumerate(words):
            chunk = word if i == 0 else f" {word}"
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


def get_llm_service() -> LLMService:
    """Factory function to create the appropriate LLM service."""
    if settings.llm_provider == "mock":
        return MockLLMService()

    # Future: return OpenAILLMService(settings) etc.
    return MockLLMService()
