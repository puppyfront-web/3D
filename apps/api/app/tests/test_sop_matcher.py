"""SOP matcher service tests (PRESALE_DELIVERY_SPEC §4.3 / P0 D3).

The matcher resolves which SOPWorkflow a presale project should run under,
given (industry, project_type, scene). Falls back to a default presale SOP
when no industry-specific match exists. The default SOP carries a
quality_review checklist the export gate reads (Task 13).
"""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.workflow import SOPWorkflow


@pytest_asyncio.fixture
async def default_presale_sop(db_session) -> uuid.UUID:
    """Seed the default presale SOP with a quality_review checklist.

    The matcher's fallback looks this up by category='presale' + a sentinel
    name. Tests that want to exercise the fallback rely on this row existing.
    """
    sop = SOPWorkflow(
        id=uuid.uuid4(),
        name="default_presale_sop",
        description="售前主链默认 SOP —— 行业无匹配时使用。",
        version="1.0",
        category="presale",
        is_active=True,
        pipeline_stages=[
            {
                "stage": "quality_review",
                "name": "质量审核",
                "description": "导出门控检查项",
                "checklist": [
                    "所有章节 status = approved",
                    "不存在阻断性 missing_info",
                    "参考案例均有有效 case_id",
                    "报价 / 工期类内容已人工确认",
                ],
            }
        ],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(sop)
    await db_session.flush()
    return sop.id


@pytest.mark.asyncio
async def test_match_returns_industry_specific_sop(db_session, default_presale_sop):
    """An industry-specific active SOP wins over the default."""
    from app.services.sop_matcher_service import sop_matcher_service

    tech_sop = SOPWorkflow(
        id=uuid.uuid4(),
        name="科技行业售前 SOP",
        version="1.0",
        category="presale",
        is_active=True,
        bound_agent="proposal",
        pipeline_stages=[
            {"stage": "quality_review", "name": "质量审核", "checklist": ["科技专属检查项"]}
        ],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    # Stash the industry tag on the SOP via the steps_json field (the model
    # has no dedicated metadata column; we use the steps payload).
    tech_sop.steps = [{"industry": "科技", "project_type": "裸眼3D"}]
    db_session.add(tech_sop)
    await db_session.flush()

    matched = await sop_matcher_service.match(
        db_session, industry="科技", project_type="裸眼3D"
    )
    assert matched is not None
    assert matched.id == tech_sop.id


@pytest.mark.asyncio
async def test_match_falls_back_to_default(db_session, default_presale_sop):
    """No industry match → return the default presale SOP."""
    from app.services.sop_matcher_service import sop_matcher_service

    matched = await sop_matcher_service.match(
        db_session, industry="从未见过的行业", project_type="whatever"
    )
    assert matched is not None
    assert matched.id == default_presale_sop
    assert matched.category == "presale"


@pytest.mark.asyncio
async def test_match_returns_none_when_no_default_seeded(db_session):
    """No industry match AND no default → None (caller degrades)."""
    from app.services.sop_matcher_service import sop_matcher_service

    matched = await sop_matcher_service.match(
        db_session, industry="科技", project_type="裸眼3D"
    )
    assert matched is None


@pytest.mark.asyncio
async def test_default_sop_carries_quality_review_checklist(
    db_session, default_presale_sop
):
    """The default SOP's quality_review stage exposes a checklist (Task 13)."""
    result = await db_session.execute(
        select(SOPWorkflow).where(SOPWorkflow.id == default_presale_sop)
    )
    sop = result.scalar_one()
    stages = sop.pipeline_stages or []
    qr = next((s for s in stages if s.get("stage") == "quality_review"), None)
    assert qr is not None, "default presale SOP must have a quality_review stage"
    assert isinstance(qr.get("checklist"), list) and qr["checklist"]
