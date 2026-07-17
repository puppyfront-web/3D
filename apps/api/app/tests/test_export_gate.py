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
        {"board_key": "company_intro", "nodes": [{"node_key": "company_profile"}]},
    ]
    result = await export_gate_service.check(
        db_session, output, canvas_boards=canvas_boards
    )
    assert not result["eligible"]
    blockers = " ".join(result["blocking"])
    assert "product_tech_scenarios" in blockers
    assert "future_social_responsibility" in blockers


@pytest.mark.asyncio
async def test_gate_passes_when_all_required_boards_filled(
    db_session, gate_output_factory
):
    output = await gate_output_factory(
        sections_meta=[{"title": "x", "order": 1, "status": "approved"}]
    )
    canvas_boards = [
        {"board_key": "company_intro", "nodes": [{"node_key": "x"}]},
        {"board_key": "product_tech_scenarios", "nodes": [{"node_key": "y"}]},
        {"board_key": "future_social_responsibility", "nodes": [{"node_key": "z"}]},
    ]
    result = await export_gate_service.check(
        db_session, output, canvas_boards=canvas_boards
    )
    assert result["eligible"], result
