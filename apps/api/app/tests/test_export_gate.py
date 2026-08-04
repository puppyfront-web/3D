"""Export gate service tests (PRESALE_DELIVERY_SPEC §9.2 / P0 F2 配置化).

Covers the SOP-checklist-driven extension to the export gate: the gate still
blocks on未审核 sections (legacy), but now ALSO reads the matched SOP's
quality_review checklist and surfaces those items as advisory blockers. Also
covers the canvas-node-fill gate (at least one filled node per default board).
"""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio

from app.models.generation import GenerationOutput, GenerationTask
from app.models.workflow import SOPWorkflow
from app.services.export_gate_service import export_gate_service


@pytest_asyncio.fixture
async def gate_output_factory(db_session, sample_project_id):
    """Build a GenerationOutput with a configurable sections_meta."""

    async def _build(sections_meta=None):
        task = GenerationTask(
            id=uuid.uuid4(),
            project_id=sample_project_id,
            type="proposal",
            status="completed",
        )
        db_session.add(task)
        await db_session.flush()
        output = GenerationOutput(
            id=uuid.uuid4(),
            task_id=task.id,
            content_type="text/markdown",
            content="x",
            sections_meta=sections_meta,
        )
        db_session.add(output)
        await db_session.flush()
        return output

    return _build


@pytest.mark.asyncio
async def test_gate_blocks_on_unapproved_section(db_session, gate_output_factory):
    output = await gate_output_factory(
        sections_meta=[{"title": "需求理解", "order": 1, "status": "draft"}]
    )
    result = await export_gate_service.check(db_session, output)
    assert not result["eligible"]
    assert any("未审核通过" in b for b in result["blocking"])


@pytest.mark.asyncio
async def test_gate_blocks_on_unconfirmed_human_review(db_session, gate_output_factory):
    output = await gate_output_factory(
        sections_meta=[
            {
                "title": "风险",
                "order": 10,
                "status": "approved",
                "require_human_review": True,
                "human_confirmed": False,
            }
        ]
    )
    result = await export_gate_service.check(db_session, output)
    assert not result["eligible"]
    assert any("需人工确认" in b for b in result["blocking"])


@pytest.mark.asyncio
async def test_gate_passes_when_all_approved_and_confirmed(
    db_session, gate_output_factory
):
    output = await gate_output_factory(
        sections_meta=[
            {"title": "需求理解", "order": 1, "status": "approved"},
            {
                "title": "风险",
                "order": 10,
                "status": "approved",
                "require_human_review": True,
                "human_confirmed": True,
            },
        ]
    )
    result = await export_gate_service.check(db_session, output)
    assert result["eligible"], result
    assert result["blocking"] == []


@pytest.mark.asyncio
async def test_gate_surfaces_sop_checklist_as_advisory(
    db_session, gate_output_factory
):
    """SOP quality_review checklist items appear in advisory (not blocking)."""
    output = await gate_output_factory(
        sections_meta=[{"title": "x", "order": 1, "status": "approved"}]
    )
    sop = SOPWorkflow(
        id=uuid.uuid4(),
        name="default_presale_sop",
        version="1.0",
        category="presale",
        is_active=True,
        pipeline_stages=[
            {
                "stage": "quality_review",
                "name": "质量审核",
                "checklist": [
                    "所有章节 status = approved",
                    "参考案例均有有效 case_id",
                ],
            }
        ],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    result = await export_gate_service.check(db_session, output, sop=sop)
    assert result["eligible"], "advisory items must not block export"
    assert any("SOP 检查项" in a for a in result["advisory"])
    assert len([a for a in result["advisory"] if "SOP 检查项" in a]) == 2


@pytest.mark.asyncio
async def test_gate_blocks_when_canvas_board_empty(
    db_session, gate_output_factory
):
    """An all-empty canvas board blocks export (Brief built without data)."""
    output = await gate_output_factory(
        sections_meta=[{"title": "x", "order": 1, "status": "approved"}]
    )
    # Only one of three required boards is filled.
    canvas_boards = [
        {
            "board_key": "company_intro",
            "nodes": [{"node_key": "company_profile", "points": ["国内 LED 龙头"]}],
        },
    ]
    result = await export_gate_service.check(
        db_session, output, canvas_boards=canvas_boards
    )
    assert not result["eligible"]
    blockers = " ".join(result["blocking"])
    assert "product_tech_scenarios" in blockers
    assert "future_social_responsibility" in blockers


@pytest.mark.asyncio
async def test_gate_blocks_when_board_has_nodes_but_no_planning(
    db_session, gate_output_factory
):
    """Boards with placeholder nodes (no points/planning content) block export.

    Regression for the old check that only verified the board had any node —
    an auto-fill that produced zero usable points must not pass the gate.
    """
    output = await gate_output_factory(
        sections_meta=[{"title": "x", "order": 1, "status": "approved"}]
    )
    canvas_boards = [
        {"board_key": "company_intro", "nodes": [{"node_key": "x"}]},  # no points
        {"board_key": "product_tech_scenarios", "nodes": [{"node_key": "y", "points": []}]},
        {
            "board_key": "future_social_responsibility",
            "nodes": [{"node_key": "z", "points": ["   "]}],  # whitespace only
        },
    ]
    result = await export_gate_service.check(
        db_session, output, canvas_boards=canvas_boards
    )
    assert not result["eligible"]
    assert len(result["blocking"]) == 3


@pytest.mark.asyncio
async def test_gate_passes_when_all_required_boards_filled(
    db_session, gate_output_factory
):
    output = await gate_output_factory(
        sections_meta=[{"title": "x", "order": 1, "status": "approved"}]
    )
    canvas_boards = [
        {"board_key": "company_intro", "nodes": [{"node_key": "x", "points": ["a"]}]},
        {"board_key": "product_tech_scenarios", "nodes": [{"node_key": "y", "points": ["b"]}]},
        {"board_key": "future_social_responsibility", "nodes": [{"node_key": "z", "points": ["c"]}]},
    ]
    result = await export_gate_service.check(
        db_session, output, canvas_boards=canvas_boards
    )
    assert result["eligible"], result


@pytest.mark.asyncio
async def test_gate_accepts_planning_list_shape(
    db_session, gate_output_factory
):
    """Tolerates the raw canvas-node ``planning`` shape (content.planning)."""
    output = await gate_output_factory(
        sections_meta=[{"title": "x", "order": 1, "status": "approved"}]
    )
    canvas_boards = [
        {"board_key": "company_intro", "nodes": [{"node_key": "x", "planning": ["a"]}]},
        {"board_key": "product_tech_scenarios", "nodes": [{"node_key": "y", "planning": ["b"]}]},
        {"board_key": "future_social_responsibility", "nodes": [{"node_key": "z", "planning": ["c"]}]},
    ]
    result = await export_gate_service.check(
        db_session, output, canvas_boards=canvas_boards
    )
    assert result["eligible"], result


# ─── Export-path SOP industry resolution (P0 #3) ──────────────────────────


@pytest.mark.asyncio
async def test_resolve_project_industry_reads_company_industry(
    db_session, sample_project_id
):
    """`_resolve_project_industry` returns the project's company.industry.

    Regression: the export path used to call sop_matcher with project_type=None
    and always hit the default SOP. The helper now plumbs company.industry so
    industry-specific SOPs (Phase 3) actually fire on export.
    """
    from app.routers.exports import _resolve_project_industry

    industry = await _resolve_project_industry(db_session, sample_project_id)
    # conftest's sample_company_id sets industry="Technology".
    assert industry == "Technology"


@pytest.mark.asyncio
async def test_resolve_project_industry_returns_none_for_missing_project(
    db_session,
):
    """A missing project must not raise — soft-fail to None."""
    from app.routers.exports import _resolve_project_industry

    industry = await _resolve_project_industry(db_session, uuid.uuid4())
    assert industry is None


@pytest.mark.asyncio
async def test_enforce_export_gate_uses_industry_for_sop_match(
    db_session, sample_project_id
):
    """The export gate passes the resolved industry into sop_matcher.match.

    Patches the matcher so we can assert the call without seeding an
    industry-specific SOP (which would also need a quality_review stage to be
    useful). This isolates the wiring fix from the matcher's own behaviour.
    """
    from app.models.generation import GenerationOutput, GenerationTask
    from app.routers import exports as exports_module

    captured = {}

    class _StubMatcher:
        async def match(self, db, industry=None, project_type=None, scene=None):
            captured["industry"] = industry
            return None  # let gate fall through to legacy checks

    # Replace the module-level singleton reference (the router imports the
    # singleton lazily, so this takes effect when _enforce_export_gate runs).
    import app.services.sop_matcher_service as sms

    original_singleton = sms.sop_matcher_service
    sms.sop_matcher_service = _StubMatcher()
    try:
        task = GenerationTask(
            id=uuid.uuid4(),
            project_id=sample_project_id,
            type="proposal",
            status="completed",
        )
        db_session.add(task)
        await db_session.flush()
        output = GenerationOutput(
            id=uuid.uuid4(),
            task_id=task.id,
            content_type="text/markdown",
            content="x",
            sections_meta=[{"title": "x", "order": 1, "status": "approved"}],
        )
        db_session.add(output)
        await db_session.flush()

        # Should pass (no SOP, section approved, no canvas).
        await exports_module._enforce_export_gate(db_session, task, output)
    finally:
        sms.sop_matcher_service = original_singleton

    assert captured.get("industry") == "Technology"
