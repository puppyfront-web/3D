"""SOP matcher service — resolves which SOPWorkflow a presale project runs under.

PRESALE_DELIVERY_SPEC §4.3 / P0 D3. Matching rules:

1. Industry-specific: an active SOP whose ``steps`` payload carries
   ``{"industry": <x>, "project_type": <y>}`` matching the request. The first
   active match wins (most-specific first — caller can order by priority if
   needed in a later iteration).
2. Fallback: the active SOP with ``category='presale'`` named
   ``default_presale_sop`` (seeded by init_db / tests). This carries the
   ``quality_review`` checklist the export gate reads (Task 13).
3. No match → ``None``; the caller (proposal_generation, export gate) degrades
   to a hard-coded baseline rather than failing.

The matcher never raises — a malformed steps payload or missing DB just means
"no industry match, try fallback".
"""

import logging
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workflow import SOPWorkflow

logger = logging.getLogger(__name__)


DEFAULT_SOP_NAME = "default_presale_sop"
DEFAULT_SOP_CATEGORY = "presale"


class SOPMatcherService:
    """Resolve the SOPWorkflow for a presale project."""

    async def match(
        self,
        db: AsyncSession,
        industry: Optional[str] = None,
        project_type: Optional[str] = None,
        scene: Optional[str] = None,
    ) -> Optional[SOPWorkflow]:
        """Return the best-fit active SOPWorkflow, or the default, or None.

        Tries industry-specific first (matching on the steps payload's
        industry/project_type tags), then falls back to the default presale
        SOP. ``scene`` is accepted for forward-compat but not yet matched.
        """
        # 1) Industry-specific active SOPs in the presale category.
        industry_match = await self._match_industry(
            db, industry=industry, project_type=project_type
        )
        if industry_match is not None:
            return industry_match

        # 2) Default presale SOP.
        return await self._match_default(db)

    # ─── Internals ─────────────────────────────────────────────────────────

    async def _match_industry(
        self,
        db: AsyncSession,
        industry: Optional[str],
        project_type: Optional[str],
    ) -> Optional[SOPWorkflow]:
        if not industry and not project_type:
            return None
        result = await db.execute(
            select(SOPWorkflow).where(
                SOPWorkflow.is_active.is_(True),
                SOPWorkflow.category == DEFAULT_SOP_CATEGORY,
            )
        )
        for sop in result.scalars().all():
            tags = self._extract_step_tags(sop)
            if not tags:
                continue
            if self._tags_match(tags, industry=industry, project_type=project_type):
                return sop
        return None

    async def _match_default(self, db: AsyncSession) -> Optional[SOPWorkflow]:
        result = await db.execute(
            select(SOPWorkflow).where(
                SOPWorkflow.is_active.is_(True),
                SOPWorkflow.category == DEFAULT_SOP_CATEGORY,
                SOPWorkflow.name == DEFAULT_SOP_NAME,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _extract_step_tags(sop: SOPWorkflow) -> Dict[str, Any]:
        """Pull industry/project_type tags from the SOP's steps payload.

        Steps is a list of arbitrary dicts; the first entry carrying an
        ``industry`` or ``project_type`` key supplies the tags. Malformed
        payloads return an empty dict (no match).
        """
        try:
            for step in (sop.steps or []):
                if isinstance(step, dict) and (
                    step.get("industry") or step.get("project_type")
                ):
                    return {
                        "industry": step.get("industry"),
                        "project_type": step.get("project_type"),
                    }
        except Exception:
            logger.exception("sop_matcher: malformed steps payload on SOP %s", sop.id)
        return {}

    @staticmethod
    def _tags_match(
        tags: Dict[str, Any],
        industry: Optional[str],
        project_type: Optional[str],
    ) -> bool:
        """A SOP matches when every tag it specifies equals the request."""
        if industry and tags.get("industry") and tags["industry"] != industry:
            return False
        if (
            project_type
            and tags.get("project_type")
            and tags["project_type"] != project_type
        ):
            return False
        # At least one tag must be specified and matched.
        return bool(tags.get("industry") or tags.get("project_type"))


sop_matcher_service = SOPMatcherService()
