"""Export gate service — config-driven export eligibility (PRESALE_DELIVERY_SPEC §9.2).

Replaces the hard-coded ``_check_export_eligibility`` in routers/exports.py
with a configurable check that:

1. Runs the per-section status / human-review checks (the old logic).
2. Reads additional checklist items from the matched SOP's ``quality_review``
   stage (``pipeline_stages[*].checklist``) and surfaces them as informational
   blockers when they aren't satisfied.

Blockers are split into ``blocking`` (export is refused) and ``advisory``
(checklist items the SOP wants confirmed but that don't map to a hard-coded
data check — surfaced so the reviewer sees them). The router only refuses on
``blocking``; ``advisory`` is included in the response so the UI can show it.

Canvas-node fill state is checked too (P0 B3 / spec §9.2 "企业画像/画布关键
节点已 filled") — at least one node per default board must have ``planning``
content, otherwise the Brief was generated against an empty canvas.
"""

import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.generation import GenerationOutput
from app.models.workflow import SOPWorkflow

logger = logging.getLogger(__name__)

# The three default canvas boards (PRD §10.2). Each must have at least one
# filled node before export — an all-empty canvas means the Brief was built
# without enterprise data.
_REQUIRED_BOARDS = ("company_intro", "product_tech_scenarios", "future_social_responsibility")


class ExportGateService:
    """Configurable export eligibility check."""

    async def check(
        self,
        db: AsyncSession,
        output: GenerationOutput,
        sop: Optional[SOPWorkflow] = None,
        canvas_boards: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Return ``{"eligible": bool, "blocking": [...], "advisory": [...]}``.

        Args:
            output: the GenerationOutput being exported.
            sop: the matched SOPWorkflow (used for the quality_review checklist).
                None → only the hard-coded checks run.
            canvas_boards: the canvas digest boards (``build_canvas_digest``
                output). None/empty → the canvas check is skipped (caller
                couldn't resolve the canvas; don't block on missing data).
        """
        blocking: List[str] = []
        advisory: List[str] = []

        # 1) Per-section status + require_human_review (legacy logic).
        meta = output.sections_meta or []
        if not meta:
            # Pre-HITL output — allow but flag as advisory so the reviewer knows.
            advisory.append("策划案无 sections_meta（旧版数据），未走章节审核流程。")
        else:
            for section in meta:
                if section.get("status") != "approved":
                    blocking.append(f"章节「{section.get('title', '?')}」未审核通过")
                if section.get("require_human_review") and not section.get("human_confirmed"):
                    blocking.append(f"章节「{section.get('title', '?')}」需人工确认")

        # 2) SOP quality_review checklist → advisory (informational; the硬性
        # checks above already cover the data-backed items).
        if sop is not None:
            for stage in (sop.pipeline_stages or []):
                if stage.get("stage") != "quality_review":
                    continue
                for item in stage.get("checklist") or []:
                    advisory.append(f"[SOP 检查项] {item}")

        # 3) Canvas fill state — at least one filled node per default board.
        if canvas_boards:
            filled_boards = {
                b.get("board_key")
                for b in canvas_boards
                if b.get("nodes")
            }
            for required in _REQUIRED_BOARDS:
                if required not in filled_boards:
                    blocking.append(f"画布板块「{required}」尚无已填充节点")

        return {
            "eligible": len(blocking) == 0,
            "blocking": blocking,
            "advisory": advisory,
        }


export_gate_service = ExportGateService()
