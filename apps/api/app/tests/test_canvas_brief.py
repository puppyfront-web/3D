"""首条 auto-fill 完成后,基于已填画布生成设计 Brief(proposal_generation)。

直接调 _handle_auto_fill;Brief 以【现有 proposal_section block】 emit,data = skill output 整体
(与 _handle_skill_execution:865 一致)。SkillRunner/SkillContext/服务在 _handle_auto_fill 内
局部 import,故 patch 其源模块。
"""
import json
import uuid as _uuid
from datetime import datetime, timezone
from typing import Tuple
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.models.canvas import (
    Canvas,
    CanvasEdge,
    CanvasGroup,
    CanvasNode,
    NodeSource,
    ProjectVersion,
)
from app.models.project import Company, Project
from app.models.skill import Skill, SkillExecution  # noqa: F401 — keep import parity
from app.models.user import Role, User
from app.services import canvas_research_service as crs
from app.services import canvas_research_service
from app.services.canvas_service import canvas_service
from app.services.conversation_service import ConversationService

pytestmark = pytest.mark.asyncio


async def _collect(stream):
    out = []
    async for chunk in stream:
        out.append(chunk)
    return out


def _parse_events(chunks):
    events = []
    for c in chunks:
        text = c.decode() if isinstance(c, (bytes, bytearray)) else c
        for line in text.splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[len("data: "):]))
    return events


class _FakeSkillResult:
    def __init__(self, output):
        self.output = output


# ─── Fixtures (mirror of test_canvas_research_service — Task 4 extended teardown) ──


async def _make_project_with_canvas(db_session) -> Tuple[_uuid.UUID, _uuid.UUID, _uuid.UUID, _uuid.UUID]:
    """Create role/user/company/project/V1 + canvas + default nodes. Returns
    (project_id, version_id, company_id, user_id) so callers can clean up."""
    role = Role(
        id=_uuid.uuid4(),
        name=f"brief_role_{_uuid.uuid4().hex[:8]}",
        description="brief test role",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(role)
    await db_session.flush()
    user = User(
        id=_uuid.uuid4(),
        email=f"brief_{_uuid.uuid4().hex[:8]}@test.local",
        name="Brief User",
        role_id=role.id,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.flush()
    company = Company(
        id=_uuid.uuid4(),
        name=f"Brief Co {_uuid.uuid4().hex[:8]}",
        industry="智能制造",
        description="一家智能制造企业",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(company)
    await db_session.flush()
    project = Project(
        id=_uuid.uuid4(),
        name=f"Brief Project {_uuid.uuid4().hex[:8]}",
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

    version = await canvas_service.create_version(db_session, project_id)
    await db_session.commit()
    return project_id, version.id, company_id, user_id


@pytest_asyncio.fixture
async def canvas_project_with_version(db_session):
    """Fixture: bootstraps a project + V1 canvas and tears it all down after,
    including any NodeSource rows the adopt/accept service created. Mirrors the
    fixture in test_canvas_research_service.py so this module is self-contained.

    Teardown sweeps ALL canvases/versions for this project (accept_fill_proposal
    / Task 4 creates a NEW ProjectVersion + cloned canvas)."""
    from sqlalchemy import delete, select

    ids = await _make_project_with_canvas(db_session)
    project_id, version_id, company_id, user_id = ids
    role_res = await db_session.execute(
        select(Role.id).join(User, User.role_id == Role.id).where(User.id == user_id)
    )
    role_id = role_res.scalar_one()

    yield (project_id, version_id)

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


async def test_auto_fill_then_brief(canvas_project_with_version, db_session, monkeypatch):
    project_id, version_id = canvas_project_with_version
    proposal = {
        "mode": "auto", "boards": [{
            "board_key": "company_intro", "board_title": "企业介绍",
            "nodes": [{"node_key": "company_profile", "node_title": "企业简介",
                       "points": ["成立于 2015 年"], "citations": [], "pending_questions": []}],
        }], "summary": {"key_points": [], "missing_info": []},
    }
    skill_output = {
        "proposal_sections": [{"title": "需求理解", "content": "基于画布画像"}],
        "citations": [], "missing_info": [],
    }
    svc = ConversationService()
    monkeypatch.setattr(svc, "save_message", AsyncMock())
    monkeypatch.setattr(svc, "_load_ref_docs_context", AsyncMock(return_value=(None, [])))
    runner = MagicMock()
    runner.run_with_react = AsyncMock(return_value=_FakeSkillResult(skill_output))
    with patch("app.services.search_helper.acquire_web_context",
               AsyncMock(return_value=([], {"status": "ok", "key_points": [], "missing_info": []}))), \
         patch("app.services.canvas_agent_orchestrator.canvas_agent_orchestrator.fill_canvas",
               AsyncMock(return_value={"success": True, "filled_count": 1, "node_ids": [], "errors": []})), \
         patch.object(crs, "build_fill_proposal_from_canvas", AsyncMock(return_value=proposal)), \
         patch("app.skills.runner.SkillRunner", return_value=runner), \
         patch("app.services.conversation_service.get_llm_service", AsyncMock(return_value=AsyncMock())), \
         patch("app.services.embedding_service.get_embedding_service", AsyncMock(return_value=AsyncMock())), \
         patch("app.services.image_service.get_image_service", AsyncMock(return_value=AsyncMock())):
        events = _parse_events(await _collect(svc._handle_auto_fill(
            db_session, _uuid.uuid4(), "帮我介绍一下甲公司", str(project_id)
        )))
    ps = [e for e in events if e.get("type") == "proposal_section"]
    assert ps, "首条 auto 后应 emit Brief(proposal_section)"
    assert ps[0]["data"]["proposal_sections"]  # data 是完整 skill output
