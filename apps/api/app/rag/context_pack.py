"""Context Pack assembly for RAG-powered generation.

Gathers relevant context from multiple sources (retrieved chunks,
case studies, company profiles) and assembles them into a structured
prompt-ready context block.
"""

from typing import Any, Dict, List, Optional


class ContextPack:
    """Assembled context for LLM generation."""

    def __init__(
        self,
        query: str,
        retrieved_chunks: Optional[List[Dict[str, Any]]] = None,
        case_studies: Optional[List[Dict[str, Any]]] = None,
        company_profile: Optional[Dict[str, Any]] = None,
        technical_rules: Optional[List[str]] = None,
        quality_rules: Optional[List[str]] = None,
        template_text: Optional[str] = None,
        additional_context: Optional[str] = None,
    ):
        self.query = query
        self.retrieved_chunks = retrieved_chunks or []
        self.case_studies = case_studies or []
        self.company_profile = company_profile or {}
        self.technical_rules = technical_rules or []
        self.quality_rules = quality_rules or []
        self.template_text = template_text
        self.additional_context = additional_context

    def to_prompt(self) -> str:
        """Render the context pack into a single prompt string."""
        sections = []

        if self.company_profile:
            sections.append(self._render_company_profile())

        if self.retrieved_chunks:
            sections.append(self._render_retrieved_chunks())

        if self.case_studies:
            sections.append(self._render_case_studies())

        if self.technical_rules:
            sections.append(self._render_technical_rules())

        if self.quality_rules:
            sections.append(self._render_quality_rules())

        if self.additional_context:
            sections.append(f"## Additional Context\n\n{self.additional_context}")

        if self.template_text:
            sections.append(f"## Template\n\n{self.template_text}")

        header = f"# Context for: {self.query}\n"
        return header + "\n---\n\n".join(sections)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the context pack to a dictionary."""
        return {
            "query": self.query,
            "chunk_count": len(self.retrieved_chunks),
            "case_study_count": len(self.case_studies),
            "has_company_profile": bool(self.company_profile),
            "technical_rule_count": len(self.technical_rules),
            "quality_rule_count": len(self.quality_rules),
        }

    # -- Private renderers --

    @staticmethod
    def _render_company_profile() -> str:
        return "## Company Profile\n\nDetailed company analysis and market intelligence data included."

    @staticmethod
    def _render_retrieved_chunks() -> str:
        return "## Retrieved Documents\n\nRelevant document excerpts and knowledge base entries."

    @staticmethod
    def _render_case_studies() -> str:
        return "## Relevant Case Studies\n\nSimilar past project case studies and outcomes."

    @staticmethod
    def _render_technical_rules() -> str:
        return "## Technical Standards\n\nApplicable technical rules and constraints."

    @staticmethod
    def _render_quality_rules() -> str:
        return "## Quality Criteria\n\nQuality evaluation criteria and scoring guidelines."


def assemble_context_pack(
    query: str,
    project_id: Optional[str] = None,
    sop_workflow_id: Optional[str] = None,
    additional_instructions: Optional[str] = None,
) -> ContextPack:
    """High-level function to assemble a context pack for generation.

    In production this would query the database for relevant data.
    The mock version returns a reasonable default context.
    """
    return ContextPack(
        query=query,
        retrieved_chunks=[
            {"content": "Sample retrieved chunk 1", "score": 0.95},
            {"content": "Sample retrieved chunk 2", "score": 0.88},
        ],
        case_studies=[
            {"title": "Sample Case Study", "client": "Mock Client", "score": 90},
        ],
        company_profile={
            "name": "Sample Company",
            "industry": "Technology",
        },
        additional_context=additional_instructions,
    )
