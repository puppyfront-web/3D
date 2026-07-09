"""画布「采集→智能归档」引擎/派生/写回 单测。"""
import json
from datetime import datetime, timezone
from typing import Tuple

import pytest
import pytest_asyncio
import uuid
from unittest.mock import AsyncMock, patch

from app.models.canvas import Canvas, CanvasGroup, CanvasNode, NodeSource, ProjectVersion
from app.models.project import Company, Project
from app.models.skill import Skill, SkillExecution  # noqa: F401 — keep import parity
from app.models.user import Role, User
from app.services import canvas_research_service as crs
from app.services.canvas_research_service import (
    accept_fill_proposal,
    build_fill_proposal_from_canvas,
    filter_new_points,
    research_and_propose,
)
from app.services.canvas_service import canvas_service

pytestmark = pytest.mark.asyncio


# ─── Fixtures (mirror of test_node_adopt / test_canvas_orchestrator) ──────────


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
    fixture in test_canvas_orchestrator.py / test_node_adopt.py so this module
    is self-contained."""
    from sqlalchemy import delete, select

    ids = await _make_project_with_canvas(db_session)
    project_id, version_id, company_id, user_id = ids
    # Capture role id for cleanup (not returned by helper).
    role_res = await db_session.execute(
        select(Role.id).join(User, User.role_id == Role.id).where(User.id == user_id)
    )
    role_id = role_res.scalar_one()

    yield (project_id, version_id)

    # Teardown: cascade-delete canvas rows that the adopt/accept services may
    # have added. accept_fill_proposal (Task 4) creates a NEW ProjectVersion +
    # cloned canvas, so we must sweep ALL canvases/versions for this project,
    # not just the original V1 — otherwise the Project FK delete fails.
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


# ─── Tests (verbatim from task-1-brief) ───────────────────────────────────────


def _fake_llm_returning(payload: dict):
    """Fake LLM whose generate_json returns the given payload."""
    llm = AsyncMock()
    llm.generate_json = AsyncMock(return_value=payload)
    return llm


async def test_research_and_propose_shape_and_no_advice_words(
    db_session, canvas_project_with_version
):
    """引擎返回 Proposal 形状;要点无「建议/应该/可以」。"""
    project_id, version_id = canvas_project_with_version

    hits = [{
        "title": "甲公司简介", "url": "https://example.com/about",
        "snippet": "甲公司成立于 2015 年，专注裸眼 3D 显示。",
        "domain": "example.com", "published_at": None,
        "source_type": "official", "confidence": 0.9,
    }]
    summary = {"status": "ok", "key_points": ["成立于2015"], "missing_info": []}
    organize_payload = {
        "boards": [{
            "board_key": "company_intro",
            "nodes": [{
                "node_key": "company_profile",
                "points": ["成立于 2015 年，专注裸眼 3D 显示"],
                "citations": [{"name": "甲公司简介", "url": "https://example.com/about",
                               "snippet": "甲公司成立于 2015 年"}],
                "pending_questions": [],
            }],
        }],
        "summary": {"key_points": ["成立于2015"], "missing_info": []},
    }
    fake_llm = _fake_llm_returning(organize_payload)
    with patch.object(crs, "acquire_web_context", AsyncMock(return_value=(hits, summary))), \
         patch.object(crs, "get_llm_service", AsyncMock(return_value=fake_llm)):
        proposal = await research_and_propose(
            db_session, project_id, context_hint="甲公司", mode="ask"
        )
    assert proposal["mode"] == "ask"
    assert proposal["boards"][0]["board_key"] == "company_intro"
    node = proposal["boards"][0]["nodes"][0]
    assert node["node_key"] == "company_profile"
    assert node["node_title"] == "企业简介"  # 从画布补全
    assert node["points"] and "成立于" in node["points"][0]
    assert node["citations"][0]["url"].startswith("http")
    blob = json.dumps(proposal, ensure_ascii=False)
    for w in ("建议", "应该", "可以"):
        assert w not in blob, f"Proposal 含禁词 {w}"


async def test_research_and_propose_uses_prefetched_hits_no_double_search(
    db_session, canvas_project_with_version
):
    """传入 web_hits 时不再触发 acquire_web_context。"""
    project_id, version_id = canvas_project_with_version
    hits = [{"title": "t", "url": "https://x", "snippet": "s", "domain": "x",
             "published_at": None, "source_type": "article", "confidence": 0.5}]
    fake_llm = _fake_llm_returning({"boards": [], "summary": {"key_points": [], "missing_info": []}})
    acq = AsyncMock(return_value=(hits, {"status": "ok", "key_points": [], "missing_info": []}))
    with patch.object(crs, "acquire_web_context", acq), \
         patch.object(crs, "get_llm_service", AsyncMock(return_value=fake_llm)):
        await research_and_propose(db_session, project_id, context_hint="x", mode="ask", web_hits=hits)
    acq.assert_not_awaited()  # 不二次搜索


async def test_research_and_propose_degrades_on_search_failure(
    db_session, canvas_project_with_version
):
    """搜索失败 → 返回空 Proposal,不抛异常。"""
    project_id, version_id = canvas_project_with_version
    with patch.object(crs, "acquire_web_context",
                      AsyncMock(return_value=([], {"status": "failed", "key_points": [], "missing_info": []}))), \
         patch.object(crs, "get_llm_service",
                      AsyncMock(return_value=_fake_llm_returning({"boards": [], "summary": {}}))):
        proposal = await research_and_propose(db_session, project_id, context_hint="x", mode="ask")
    assert proposal["boards"] == []


def test_filter_new_points_drops_duplicates():
    """已有 planning 的要点被过滤;全新要点保留。"""
    class N:
        def __init__(self, planning):
            self.content = {"planning": planning}
    nodes_by_key = {"company_profile": N(["成立于 2015 年，专注裸眼 3D 显示"])}
    proposal = {
        "mode": "ask",
        "boards": [
            {"board_key": "company_intro", "board_title": "企业介绍", "nodes": [
                {"node_key": "company_profile", "node_title": "企业简介",
                 "points": ["成立于 2015 年，专注裸眼 3D 显示", "员工 300 人"],
                 "citations": [], "pending_questions": []},
            ]},
        ],
        "summary": {"key_points": [], "missing_info": []},
    }
    out = filter_new_points(proposal, nodes_by_key)
    kept = out["boards"][0]["nodes"][0]["points"]
    assert kept == ["员工 300 人"]


def test_filter_new_points_empty_when_all_dup():
    class N:
        def __init__(self, planning):
            self.content = {"planning": planning}
    nodes_by_key = {"company_profile": N(["已有要点"])}
    proposal = {
        "mode": "ask", "boards": [
            {"board_key": "company_intro", "board_title": "x", "nodes": [
                {"node_key": "company_profile", "node_title": "x",
                 "points": ["已有要点"], "citations": [], "pending_questions": []}],
            }],
        "summary": {"key_points": [], "missing_info": []},
    }
    out = filter_new_points(proposal, nodes_by_key)
    assert out["boards"] == []  # 全重复 → 清空,上层据此不 emit


# ─── accept_fill_proposal (Task 4: 版本化写回) ────────────────────────────────


async def test_accept_fill_proposal_creates_version_and_merges(
    db_session, canvas_project_with_version
):
    """采纳:新建 ProjectVersion(is_current 翻转)、节点 planning 被覆盖、
    ui_suggestion/extracted 保留、status=filled、citation 写 NodeSource。"""
    from sqlalchemy import select
    from app.models.canvas import CanvasNode, NodeSource, ProjectVersion

    project_id, version_id = canvas_project_with_version

    # 先给目标节点塞一点既有 ui_suggestion(验证保留)
    node = await _first_node_in_version(db_session, None, "company_profile", project_id=project_id)
    node.content = {"extracted": ["旧 extracted"], "planning": [],
                    "ui_suggestion": ["旧 ui 建议"], "pending_questions": []}
    await db_session.flush()

    body = {
        "boards": [{
            "board_key": "company_intro",
            "nodes": [{
                "node_key": "company_profile",
                "points": ["成立于 2016 年", "员工 200 人"],
                "citations": [{"name": "官网", "url": "https://x", "snippet": "..."}],
            }],
        }],
        "change_summary": "采集填充：1 个节点",
    }
    new_version = await accept_fill_proposal(db_session, project_id, body, user_id=None)
    await db_session.commit()

    assert isinstance(new_version, ProjectVersion)
    assert new_version.is_current is True
    old = await db_session.get(ProjectVersion, version_id)
    assert old.is_current is False  # 旧版本被 demote

    # 新版本上的节点被合并写回(create_version 克隆了旧画布,故 ui_suggestion/extracted 保留)
    new_node = await _first_node_in_version(db_session, new_version.id, "company_profile")
    c = new_node.content
    assert c["planning"] == ["成立于 2016 年", "员工 200 人"]
    assert c["ui_suggestion"] == ["旧 ui 建议"]  # 保留
    assert c["extracted"] == ["旧 extracted"]    # 保留
    assert new_node.status == "filled"
    srcs = (await db_session.execute(
        select(NodeSource).where(NodeSource.node_id == new_node.id)
    )).scalars().all()
    web_srcs = [s for s in srcs if s.source_type == "web_search"]
    assert any(s.source_name == "官网" for s in web_srcs)


async def test_accept_fill_proposal_rejects_illegal_node_key(
    db_session, canvas_project_with_version
):
    project_id, version_id = canvas_project_with_version
    body = {"boards": [{"board_key": "company_intro",
                        "nodes": [{"node_key": "DOES_NOT_EXIST", "points": ["x"], "citations": []}]}]}
    with pytest.raises(Exception):
        await accept_fill_proposal(db_session, project_id, body)


# --- helpers ---
async def _first_node_in_version(db, version_id, node_key, project_id=None):
    # canvas_service is the singleton instance imported at top of file (not the
    # module). The brief wrote `from app.services import canvas_service` which
    # would resolve to the module here; use the already-imported instance.
    if version_id is None:
        version_id = (await canvas_service.get_current_version(db, project_id)).id
    canvas = await canvas_service.get_canvas(db, version_id)
    for g in canvas.groups:
        for n in g.nodes:
            if (n.node_key or n.title) == node_key:
                return n
    raise AssertionError(f"node {node_key} not found")
