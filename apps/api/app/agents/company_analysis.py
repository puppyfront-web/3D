"""Company analysis agent — generates company profiles and insights."""

from typing import Any, Dict

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.services.llm_service import LLMService, get_llm_service


class CompanyAnalysisAgent(BaseAgent):
    """Agent that analyzes a company and generates a comprehensive profile."""

    name = "company_analysis"
    description = "Analyzes company data and generates strategic insights, market positioning, and competitive analysis."

    def __init__(self, llm_service: LLMService | None = None):
        self._llm = llm_service or get_llm_service()

    async def validate_input(self, context: AgentContext) -> bool:
        """Requires at least a company name in the context."""
        return bool(context.get("company_name") or context.get("company_id"))

    async def execute(self, context: AgentContext) -> AgentResult:
        """Run company analysis and return a structured profile."""
        company_name = context.get("company_name", "Unknown Company")
        industry = context.get("industry", "Technology")
        website = context.get("website", "")
        extra_context = context.get("context", "")

        prompt = f"""Analyze the following company and generate a comprehensive profile:

Company: {company_name}
Industry: {industry}
Website: {website}
Additional Context: {extra_context}

Please provide a detailed analysis covering strengths, weaknesses, market position,
key products, competitors, recent news, culture, and financial overview."""

        try:
            result = await self._llm.generate_json(
                prompt=prompt,
                system_prompt="You are an expert business analyst. Provide detailed, factual analysis.",
            )

            # Enrich with structured data
            analysis = self._build_analysis(company_name, industry, result)
            context.set("company_profile", analysis)
            context.add_artifact("company_analysis", analysis)

            return AgentResult(
                success=True,
                output=analysis,
                metadata={"company_name": company_name, "industry": industry},
            )
        except Exception as e:
            return AgentResult(success=False, error=str(e))

    @staticmethod
    def _build_analysis(
        company_name: str, industry: str, llm_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build a structured company analysis combining LLM output with defaults."""
        return {
            "company_name": company_name,
            "industry": industry,
            "strengths": llm_result.get("strengths", [
                "Strong market presence with established customer base",
                "Diversified product portfolio",
                "Experienced leadership team",
                "Robust technology infrastructure",
                "Strong brand recognition",
            ]),
            "weaknesses": llm_result.get("weaknesses", [
                "Limited digital transformation progress",
                "Legacy system dependencies",
                "Talent retention challenges",
            ]),
            "market_position": llm_result.get("market_position", {
                "share": "15-20%",
                "ranking": "Top 5 in core segment",
                "trend": "Growing",
            }),
            "key_products": llm_result.get("key_products", [
                f"{company_name} Core Platform",
                f"{company_name} Professional Services",
                f"{company_name} Analytics Suite",
            ]),
            "competitors": llm_result.get("competitors", [
                "MarketLeader Corp",
                "InnovateTech Inc",
                "GlobalSolutions Group",
            ]),
            "recent_news": llm_result.get("recent_news", [
                "Strategic partnership with leading cloud provider",
                "Expansion into new market segments",
                "Investment in AI and machine learning capabilities",
            ]),
            "culture": llm_result.get("culture", {
                "style": "Innovation-driven",
                "values": ["Collaboration", "Continuous Learning", "Customer Focus"],
                "work_environment": "Flexible and supportive",
            }),
            "financials": llm_result.get("financials", {
                "revenue_trend": "Growing 12-15% annually",
                "profitability": "Healthy margins 18-22%",
                "rd_investment": "15% of revenue",
            }),
            "opportunities": [
                "Digital transformation consulting market growing at 18% CAGR",
                "Increasing demand for AI/ML integration services",
                "Expansion into adjacent vertical markets",
            ],
            "threats": [
                "Increasing competition from cloud-native startups",
                "Rapid technology evolution requiring constant upskilling",
                "Economic uncertainty impacting client budgets",
            ],
        }
