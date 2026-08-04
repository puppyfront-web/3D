"""Task 3: adopt endpoint merges draft into the node, sets filled, writes a NodeSource.

The ``canvas_project_with_version`` fixture lives in ``test_canvas_orchestrator.py``
(not in conftest.py) — pytest fixtures defined in a sibling test module are NOT
shared. We mirror a copy here so this module is self-contained, identical to
the orchestrator fixture. (Moving the original into conftest would be a larger
refactor across the orchestrator suite and is out of scope for this task.)
"""

from datetime import datetime, timezone
from typing import Tuple

import pytest
import pytest_asyncio
import uuid

from app.models.canvas import Canvas, CanvasGroup, CanvasNode, NodeSource, ProjectVersion
from app.models.project import Company, Project
from app.models.skill import Skill, SkillExecution  # noqa: F401 — keep import parity
from app.models.user import Role, User
from app.services.canvas_service import canvas_service


# ─── Fixtures (mirror of test_canvas_orchestrator._make_project_with_canvas) ─


async def _make_project_with_canvas(db_session) -> Tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    """Create role/user/company/project/V1 + canvas + default nodes. Returns
    (project_id, version_id, company_id, user_id) so callers can clean up."""
    role = Role(
        id=uuid.uuid4(),
        name=f"adopt_role_{uuid.uuid4().hex[:8]}",
        description="adopt test role",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(role)
    await db_session.flush()
    user = User(
        id=uuid.uuid4(),
        email=f"adopt_{uuid.uuid4().hex[:8]}@test.local",
        name="Adopt User",
        role_id=role.id,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.flush()
    company = Company(
        id=uuid.uuid4(),
        name=f"Adopt Co {uuid.uuid4().hex[:8]}",
        industry="智能制造",
        description="一家智能制造企业",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(company)
    await db_session.flush()
    project = Project(
        id=uuid.uuid4(),
        name=f"Adopt Project {uuid.uuid4().hex[:8]}",
        company_id=company.id,
        owner_id=user.id,
        status="draft",
        description="希望生成企业3D数字化展示方案",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(project)
    await db_session.commit()
    project_id = project.id
    company_id = company.id
    user_id = user.id
    role_id = role.id

    # V1 with default topology (creates the company_profile node the test targets).
    version = await canvas_service.create_version(db_session, project_id)
    await db_session.commit()
    return project_id, version.id, company_id, user_id


@pytest_asyncio.fixture
async def canvas_project_with_version(db_session):
    """Fixture: bootstraps a project + V1 canvas and tears it all down after,
    including any NodeSource rows the adopt service created. Mirrors the
    fixture in test_canvas_orchestrator.py so this module is self-contained."""
    from sqlalchemy import delete, select

    ids = await _make_project_with_canvas(db_session)
    project_id, version_id, company_id, user_id = ids
    # Capture role id for cleanup (not returned by helper).
    role_res = await db_session.execute(
        select(Role.id).join(User, User.role_id == Role.id).where(User.id == user_id)
    )
    role_id = role_res.scalar_one()

    yield (project_id, version_id)

    # Teardown: cascade-delete canvas rows that the adopt service may have added.
    cv_res = await db_session.execute(
        select(Canvas.id).where(Canvas.project_version_id == version_id)
    )
    canvas_ids = [r[0] for r in cv_res.all()]
    if canvas_ids:
        node_res = await db_session.execute(
            select(CanvasNode.id).where(CanvasNode.canvas_id.in_(canvas_ids))
        )
        node_ids = [r[0] for r in node_res.all()]
        if node_ids:
            await db_session.execute(delete(NodeSource).where(NodeSource.node_id.in_(node_ids)))
        from app.models.canvas import CanvasEdge
        await db_session.execute(delete(CanvasEdge).where(CanvasEdge.canvas_id.in_(canvas_ids)))
        await db_session.execute(delete(CanvasNode).where(CanvasNode.canvas_id.in_(canvas_ids)))
        await db_session.execute(delete(CanvasGroup).where(CanvasGroup.canvas_id.in_(canvas_ids)))
        await db_session.execute(delete(Canvas).where(Canvas.id.in_(canvas_ids)))
    await db_session.execute(delete(ProjectVersion).where(ProjectVersion.id == version_id))
    await db_session.execute(delete(Project).where(Project.id == project_id))
    await db_session.execute(delete(Company).where(Company.id == company_id))
    await db_session.execute(delete(User).where(User.id == user_id))
    await db_session.execute(delete(Role).where(Role.id == role_id))
    await db_session.commit()


# ─── Test (verbatim from task-3-brief) ────────────────────────────────────────


@pytest.mark.asyncio
async def test_adopt_writes_merged_content_status_filled_and_source(
    db_session, canvas_project_with_version
):
    # canvas_project_with_version yields (project_id, version_id) — see conftest.
    project_id, version_id = canvas_project_with_version
    from sqlalchemy import select
    from app.models.canvas import CanvasNode, Canvas, NodeSource

    # Pick the company_profile node created by the fixture.
    node = (
        await db_session.execute(
            select(CanvasNode)
            .join(Canvas, CanvasNode.canvas_id == Canvas.id)
            .where(Canvas.project_version_id == version_id)
            .where(CanvasNode.node_key == "company_profile")
        )
    ).scalar_one()
    # Pre-existing ui_suggestion must be preserved on adopt.
    node.content = {"extracted": ["旧事实"], "planning": [], "ui_suggestion": ["保留我"], "pending_questions": []}
    await db_session.flush()

    from app.services.canvas_adopt_service import adopt_node_draft

    updated = await adopt_node_draft(
        db_session,
        project_id=project_id,
        node_id=node.id,
        planning=["XX科技专注智能制造，成立于2010年。"],
        pending_questions=["营业执照上的成立时间"],
        sources=[{"type": "web_search", "name": "公司官网", "quote": "成立于2010年"}],
    )

    assert updated.status == "filled"
    assert updated.content["planning"] == ["XX科技专注智能制造，成立于2010年。"]
    assert updated.content["pending_questions"] == ["营业执照上的成立时间"]
    # ui_suggestion preserved (merge, not blind overwrite).
    assert updated.content["ui_suggestion"] == ["保留我"]
    # A NodeSource row was written.
    srcs = (
        await db_session.execute(select(NodeSource).where(NodeSource.node_id == node.id))
    ).scalars().all()
    assert any(s.source_type == "ai_completed" and s.source_name == "对话采纳" for s in srcs)
