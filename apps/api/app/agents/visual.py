"""Visual creative agent — generates design prompts and visual recommendations."""

from typing import Any, Dict, Optional

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.services.llm_service import LLMService, get_llm_service


class VisualAgent(BaseAgent):
    """Agent that generates visual design prompts and style recommendations."""

    name = "visual"
    description = "Generates visual design prompts, color palettes, typography, and layout recommendations for proposals."

    def __init__(self, llm_service: Optional[LLMService] = None):
        self._llm = llm_service or get_llm_service()

    async def validate_input(self, context: AgentContext) -> bool:
        """Requires a project reference."""
        return bool(context.get("project_name") or context.get("project_id"))

    async def execute(self, context: AgentContext) -> AgentResult:
        """Generate visual design recommendations for a proposal."""
        project_name = context.get("project_name", "Project")
        industry = context.get("industry", "Technology")
        style_preferences = context.get("style_preferences", "Modern, professional, clean")
        target_audience = context.get("target_audience", f"{industry} decision makers")

        prompt = f"""Create a visual design specification for a professional proposal presentation:

Project: {project_name}
Industry: {industry}
Style Preferences: {style_preferences}
Target Audience: {target_audience}

Provide detailed recommendations for:
1. Color palette (primary, secondary, accent, background)
2. Typography (headings and body)
3. Layout guidelines
4. Visual elements and imagery
5. Slide design templates"""

        try:
            result = await self._llm.generate_json(
                prompt=prompt,
                system_prompt="You are an expert visual designer specializing in business proposals and presentations.",
            )

            visual_spec = self._build_visual_spec(
                project_name, industry, style_preferences, target_audience, result,
            )

            context.set("visual_prompt", visual_spec)
            context.add_artifact("visual_spec", visual_spec)

            return AgentResult(
                success=True,
                output=visual_spec,
                metadata={"project_name": project_name},
            )
        except Exception as e:
            return AgentResult(success=False, error=str(e))

    @staticmethod
    def _build_visual_spec(
        project_name: str,
        industry: str,
        style_preferences: str,
        target_audience: str,
        llm_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build a complete visual specification."""
        return {
            "project_name": project_name,
            "industry": industry,
            "color_palette": {
                "primary": "#1a73e8",
                "secondary": "#4285f4",
                "accent": "#34a853",
                "background": "#ffffff",
                "text": "#202124",
                "light_gray": "#f8f9fa",
                "dark_gray": "#5f6368",
            },
            "typography": {
                "headings": {
                    "font": "Inter",
                    "weights": [700, 800],
                    "sizes": {
                        "h1": "2.5rem",
                        "h2": "2rem",
                        "h3": "1.5rem",
                        "h4": "1.25rem",
                    },
                },
                "body": {
                    "font": "Inter",
                    "weights": [400, 500],
                    "size": "1rem",
                    "line_height": "1.6",
                },
            },
            "layout": {
                "grid": "12-column grid with 24px gutters",
                "max_width": "1200px",
                "margins": {"desktop": "80px", "tablet": "48px", "mobile": "24px"},
                "spacing_scale": "8px base unit (8, 16, 24, 32, 48, 64, 96)",
            },
            "visual_elements": [
                "Clean geometric shapes with subtle gradients",
                "Professional data visualizations with consistent chart styling",
                "Outlined icon set with 2px stroke weight",
                "Photography: Professional, well-lit, with warm undertones",
                "Subtle background patterns for visual interest",
            ],
            "slide_templates": {
                "title": {
                    "layout": "Full-bleed hero with gradient overlay",
                    "elements": "Large heading, subtitle, date, company logo",
                },
                "section": {
                    "layout": "Left-aligned heading with accent bar",
                    "elements": "Section title, brief description, navigation indicator",
                },
                "content": {
                    "layout": "Two-column with heading and bullet points",
                    "elements": "Heading, key points, supporting visual",
                },
                "data": {
                    "layout": "Dashboard-style grid",
                    "elements": "Charts, KPIs, metric highlights, trend indicators",
                },
                "case_study": {
                    "layout": "Card-based with image header",
                    "elements": "Client logo, challenge/solution/results, key metrics",
                },
                "closing": {
                    "layout": "Centered minimal design",
                    "elements": "Call-to-action, contact information, thank you",
                },
            },
            "style_preferences": style_preferences,
            "target_audience": target_audience,
        }
