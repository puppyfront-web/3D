"""POST /api/v1/projects/{pid}/canvas/fill-accept 版本化写回。

用 `client` fixture(conftest.py:159,auth 在测试里已旁路,无需 headers,见 test_canvas.py)。
`canvas_project_with_version` yield (project_id, version_id)。
"""
from datetime import datetime, timezone
from typing import Tuple

import pytest
import pytest_asyncio
import uuid

from app.models.canvas import Canvas, CanvasGroup, CanvasNode, NodeSource, ProjectVersion
from app.models.project import Company, Project
from app.models.user import Role, User
from app.services.canvas_service import canvas_service

pytestmark = pytest.mark.asyncio


# ─── Fixtures (self-contained copy with Task-4-extended teardown) ────────────


async def _make_project_with_canvas(db_session) -> Tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    """Create role/user/company/project/V1 + canvas + default nodes. Returns
    (project_id, version_id, company_id, user_id) so callers can clean up."""
    role = Role(
        id=uuid.uuid4(),
        name=f"accept_role_{uuid.uuid4().hex[:8]}",
        description="accept test role",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(role)
    await db_session.flush()
    user = User(
        id=uuid.uuid4(),
        email=f"accept_{uuid.uuid4().hex[:8]}@test.local",
        name="Accept User",
        role_id=role.id,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.flush()
    company = Company(
        id=uuid.uuid4(),
        name=f"Accept Co {uuid.uuid4().hex[:8]}",
        industry="智能制造",
        description="一家智能制造企业",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(company)
    await db_session.flush()
    project = Project(
        id=uuid.uuid4(),
        name=f"Accept Project {uuid.uuid4().hex[:8]}",
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

    # V1 with default topology (creates the company_profile node the test targets).
    version = await canvas_service.create_version(db_session, project_id)
    await db_session.commit()
    return project_id, version.id, company_id, user_id


@pytest_asyncio.fixture
async def canvas_project_with_version(db_session):
    """Fixture: bootstraps a project + V1 canvas and tears it all down after,
    including any NodeSource rows the accept endpoint creates. Mirrors the
    fixture in test_canvas_research_service.py (Task-4-extended teardown that
    sweeps ALL project canvases/versions, since this endpoint also creates a
    new ProjectVersion via accept_fill_proposal)."""
    from sqlalchemy import delete, select

    ids = await _make_project_with_canvas(db_session)
    project_id, version_id, company_id, user_id = ids
    # Capture role id for cleanup (not returned by helper).
    role_res = await db_session.execute(
        select(Role.id).join(User, User.role_id == Role.id).where(User.id == user_id)
    )
    role_id = role_res.scalar_one()

    yield (project_id, version_id)

    # Teardown: cascade-delete canvas rows that the accept endpoint may have
    # added. accept_fill_proposal creates a NEW ProjectVersion + cloned canvas,
    # so we must sweep ALL canvases/versions for this project.
    cv_res = await db_session.execute(
        select(Canvas.id).join(
            ProjectVersion, ProjectVersion.id == Canvas.project_version_id
        ).where(ProjectVersion.project_id == project_id)
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
    await db_session.execute(
        delete(ProjectVersion).where(ProjectVersion.project_id == project_id)
    )
    await db_session.execute(delete(Project).where(Project.id == project_id))
    await db_session.execute(delete(Company).where(Company.id == company_id))
    await db_session.execute(delete(User).where(User.id == user_id))
    await db_session.execute(delete(Role).where(Role.id == role_id))
    await db_session.commit()


# ─── Test (verbatim from task-5-brief) ───────────────────────────────────────


async def test_fill_accept_writes_versioned_and_returns_filled_canvas(
    client, canvas_project_with_version
):
    project_id, version_id = canvas_project_with_version
    body = {
        "boards": [{
            "board_key": "company_intro",
            "nodes": [{
                "node_key": "company_profile",
                "points": ["成立于 2017 年"],
                "citations": [{"name": "官网", "url": "https://x", "snippet": "..."}],
            }],
        }],
        "change_summary": "采集填充：1 节点",
    }
    resp = await client.post(
        f"/api/v1/projects/{project_id}/canvas/fill-accept", json=body
    )
    assert resp.status_code == 200, resp.text
    canvas = resp.json()["data"]  # CanvasOut(camelCase): groups/nodes/edges
    cp = next(n for n in canvas["nodes"] if n["nodeKey"] == "company_profile")
    assert cp["status"] == "filled"
    assert "成立于 2017 年" in cp["content"]["planning"]
