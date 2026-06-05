"""Proposal generation agent."""

from typing import Any, Dict, List, Optional

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.services.llm_service import LLMService, get_llm_service


class ProposalAgent(BaseAgent):
    """Agent that generates professional project proposals."""

    name = "proposal"
    description = "Generates comprehensive project proposals using company analysis, case studies, and retrieved context."

    def __init__(self, llm_service: Optional[LLMService] = None):
        self._llm = llm_service or get_llm_service()

    async def validate_input(self, context: AgentContext) -> bool:
        """Requires a project name and some company information."""
        return bool(context.get("project_name") or context.get("project_id"))

    async def execute(self, context: AgentContext) -> AgentResult:
        """Generate a proposal using context from prior agent steps."""
        project_name = context.get("project_name", "Untitled Project")
        client_name = context.get("company_name", "Client")
        industry = context.get("industry", "Technology")
        company_profile = context.get("company_profile", {})
        case_studies = context.get("case_studies", [])
        requirements = context.get("requirements", "Standard project requirements")
        budget = context.get("budget", "TBD")
        timeline = context.get("timeline", "6-8 months")

        prompt = self._build_prompt(
            project_name, client_name, industry, company_profile,
            case_studies, requirements, budget, timeline,
        )

        try:
            proposal = await self._llm.generate(
                prompt=prompt,
                system_prompt="You are an expert proposal writer. Generate comprehensive, professional proposals.",
                max_tokens=4000,
            )

            result_data = {
                "content": proposal,
                "content_type": "text/markdown",
                "metadata": {
                    "project_name": project_name,
                    "client_name": client_name,
                    "used_cases": [cs.get("id", "") for cs in case_studies if isinstance(cs, dict)],
                    "used_documents": context.get("used_documents", []),
                    "used_chunks": context.get("used_chunks", []),
                    "used_sop_version": context.get("used_sop_version", "1.2"),
                },
            }

            context.set("proposal", result_data)
            context.add_artifact("proposal", proposal)

            return AgentResult(
                success=True,
                output=result_data,
                metadata=result_data["metadata"],
            )
        except Exception as e:
            return AgentResult(success=False, error=str(e))

    @staticmethod
    def _build_prompt(
        project_name: str,
        client_name: str,
        industry: str,
        company_profile: Dict[str, Any],
        case_studies: List[Dict[str, Any]],
        requirements: str,
        budget: str,
        timeline: str,
    ) -> str:
        """Construct the proposal generation prompt."""
        company_section = ""
        if company_profile:
            strengths = company_profile.get("strengths", [])
            company_section = f"""
Company Analysis Summary:
- Industry: {industry}
- Key Strengths: {', '.join(strengths[:3]) if isinstance(strengths, list) else strengths}
"""

        cases_section = ""
        if case_studies:
            for cs in case_studies[:3]:
                if isinstance(cs, dict):
                    cases_section += f"""
- {cs.get('title', 'Case Study')}: {cs.get('results', 'Successful outcome')}
"""
                else:
                    cases_section += f"\n- {cs}"

        return f"""Generate a comprehensive professional proposal for:

Project: {project_name}
Client: {client_name}
Industry: {industry}
Requirements: {requirements}
Budget Range: {budget}
Timeline: {timeline}
{company_section}
Relevant Case Studies:{cases_section}

Please include: Executive Summary, Understanding of Requirements, Proposed Solution,
Implementation Approach, Timeline with Milestones, Team Structure, Budget Breakdown,
Risk Assessment, and Success Metrics. Format in Markdown."""
