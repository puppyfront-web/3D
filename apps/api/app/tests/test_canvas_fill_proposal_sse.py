"""auto/ask 模式的 canvas_fill_proposal SSE 触发 + 门槛。

直接调用内部 handler(_handle_auto_fill / _handle_conversational),mock 掉
save_message / llm / 搜索 / fill_canvas,断言裸 SSE 事件。注意:
  - ConversationService() 无参构造(见 conversation_service.py:132)。
  - _handle_auto_fill 的签名是 (db, conversation_id, user_message, project_id, force=False)。
  - _handle_auto_fill 内 acquire_web_context 与 canvas_agent_orchestrator 都是【局部 import】,
    故 patch 源:app.services.search_helper.acquire_web_context、
    app.services.canvas_agent_orchestrator.canvas_agent_orchestrator.fill_canvas。
  - _handle_conversational 用【模块级】acquire_web_context(conversation_service.py:17),
    故 patch:app.services.conversation_service.acquire_web_context。

fixtures(canvas_project_with_version + _make_project_with_canvas)逐字拷贝自
apps/api/app/tests/test_node_adopt.py(同 Task 1 模式),保证本模块自包含。
"""
import json
import uuid as _uuid
from datetime import datetime, timezone
from typing import Tuple
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
import uuid

from app.models.canvas import Canvas, CanvasGroup, CanvasNode, NodeSource, ProjectVersion
from app.models.project import Company, Project
from app.models.skill import Skill, SkillExecution  # noqa: F401 — keep import parity
from app.models.user import Role, User
from app.services import canvas_research_service as crs
from app.services.canvas_service import canvas_service
from app.services.conversation_service import ConversationService

pytestmark = pytest.mark.asyncio


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
    # auto-fill now persists proposal GenerationTask/GenerationOutput (Plan
    # Task 2). These reference the project via FK, so delete them BEFORE the
    # project row or the teardown trips a FOREIGN KEY constraint.
    from app.models.generation import GenerationOutput, GenerationTask

    gen_task_ids_res = await db_session.execute(
        select(GenerationTask.id).where(GenerationTask.project_id == project_id)
    )
    gen_task_ids = [r[0] for r in gen_task_ids_res.all()]
    if gen_task_ids:
        await db_session.execute(
            delete(GenerationOutput).where(GenerationOutput.task_id.in_(gen_task_ids))
        )
        await db_session.execute(
            delete(GenerationTask).where(GenerationTask.id.in_(gen_task_ids))
        )
    await db_session.execute(delete(Project).where(Project.id == project_id))
    await db_session.execute(delete(Company).where(Company.id == company_id))
    await db_session.execute(delete(User).where(User.id == user_id))
    await db_session.execute(delete(Role).where(Role.id == role_id))
    await db_session.commit()


# ─── Helpers ──────────────────────────────────────────────────────────────────


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


# ─── Test (verbatim from task-2-brief) ────────────────────────────────────────


async def test_auto_fill_emits_canvas_fill_proposal(
    canvas_project_with_version, db_session, monkeypatch
):
    """首条 auto-fill 后 emit canvas_fill_proposal(mode=auto)。"""
    project_id, version_id = canvas_project_with_version
    proposal = {
        "mode": "auto",
        "boards": [{
            "board_key": "company_intro", "board_title": "企业介绍",
            "nodes": [{
                "node_key": "company_profile", "node_title": "企业简介",
                "points": ["成立于 2015 年"], "citations": [], "pending_questions": [],
            }],
        }],
        "summary": {"key_points": [], "missing_info": []},
    }
    svc = ConversationService()
    monkeypatch.setattr(svc, "save_message", AsyncMock())          # 不落库
    monkeypatch.setattr(svc, "_load_ref_docs_context", AsyncMock(return_value=(None, [])))
    with patch("app.services.search_helper.acquire_web_context",
               AsyncMock(return_value=([], {"status": "ok", "key_points": [], "missing_info": []}))), \
         patch("app.services.canvas_agent_orchestrator.canvas_agent_orchestrator.fill_canvas",
               AsyncMock(return_value={"success": True, "filled_count": 1, "node_ids": [], "errors": []})), \
         patch.object(crs, "build_fill_proposal_from_canvas", AsyncMock(return_value=proposal)):
        events = _parse_events(await _collect(svc._handle_auto_fill(
            db_session, _uuid.uuid4(), "帮我介绍一下甲公司", str(project_id)
        )))
    types = [e.get("type") for e in events]
    assert "canvas_fill_proposal" in types
    block = next(e for e in events if e.get("type") == "canvas_fill_proposal")
    assert block["data"]["mode"] == "auto"
    assert block["data"]["boards"][0]["nodes"][0]["points"]


# ─── Task 6: ask 模式引擎接入 _handle_conversational ───────────────────────────


async def test_conversational_emits_ask_proposal_on_new_info(
    canvas_project_with_version, db_session, monkeypatch
):
    """后续问答搜到模块相关新增要点 → 直答后 emit canvas_fill_proposal(mode=ask)。"""
    project_id, version_id = canvas_project_with_version
    ask_proposal = {
        "mode": "ask",
        "boards": [{
            "board_key": "company_intro", "board_title": "企业介绍",
            "nodes": [{
                "node_key": "company_scale", "node_title": "企业规模",
                "points": ["员工 500 人"], "citations": [], "pending_questions": [],
            }],
        }],
        "summary": {"key_points": [], "missing_info": []},
    }
    # 假 LLM：走 fallback 流式路径（置 rich=None，触发 generate_with_history_stream）
    fake_llm = AsyncMock()
    fake_llm.generate_with_history_stream_rich = None
    async def _stream(*a, **k):
        yield "已为你查到相关信息。"
    fake_llm.generate_with_history_stream = _stream
    svc = ConversationService()
    monkeypatch.setattr(svc, "save_message", AsyncMock())
    with patch("app.services.conversation_service.get_llm_service",
               AsyncMock(return_value=fake_llm)), \
         patch("app.services.conversation_service.acquire_web_context",
               AsyncMock(return_value=([{"title": "t", "url": "https://x", "snippet": "s",
                  "domain": "x", "published_at": None, "source_type": "article",
                  "confidence": 0.5}], {"status": "ok", "key_points": [], "missing_info": []}))), \
         patch.object(crs, "research_and_propose", AsyncMock(return_value=ask_proposal)):
        events = _parse_events(await _collect(svc._handle_conversational(
            db_session, _uuid.uuid4(), "甲公司有多少员工", [], str(project_id)
        )))
    types = [e.get("type") for e in events]
    assert "canvas_fill_proposal" in types
    block = next(e for e in events if e.get("type") == "canvas_fill_proposal")
    assert block["data"]["mode"] == "ask"


async def test_conversational_no_proposal_when_all_dup(
    canvas_project_with_version, db_session, monkeypatch
):
    """全重复要点 → filter_new_points 清空 boards → 不 emit。

    注意：本用例的 acquire_web_context 必须返回非空 hits，否则 guard
    `if project_id and web_hits and ...` 会因空列表短路，引擎根本不执行，
    测试将变成「因 gate 短路而非去重」的同义反复。故这里复用与上一用例相同
    的非空 hits，让 guard 通过、让（被 mock 的）research_and_propose 返回
    与画布已有要点完全重复的提案，再由真实的 filter_new_points 清空 boards。
    """
    # canvas_service 已在文件顶部作为实例导入（from ...canvas_service import
    # canvas_service），不要在此处 `from app.services import canvas_service` ——
    # 那会拿到模块对象而非 CanvasService 实例，导致 AttributeError。
    project_id, version_id = canvas_project_with_version
    # 预置 company_profile 节点已有该要点，使 filter_new_points 判定为重复
    ver = await canvas_service.get_current_version(db_session, project_id)
    cv = await canvas_service.get_canvas(db_session, ver.id)
    for g in cv.groups:
        for n in g.nodes:
            if (n.node_key or n.title) == "company_profile":
                n.content = {"extracted": [], "planning": ["已存在的要点"],
                             "ui_suggestion": [], "pending_questions": []}
    await db_session.commit()

    dup_proposal = {
        "mode": "ask",
        "boards": [{
            "board_key": "company_intro", "board_title": "企业介绍",
            "nodes": [{
                "node_key": "company_profile", "node_title": "企业简介",
                "points": ["已存在的要点"], "citations": [], "pending_questions": [],
            }],
        }],
        "summary": {"key_points": [], "missing_info": []},
    }
    fake_llm = AsyncMock()
    fake_llm.generate_with_history_stream_rich = None
    async def _stream2(*a, **k):
        yield "已知。"
    fake_llm.generate_with_history_stream = _stream2
    svc = ConversationService()
    monkeypatch.setattr(svc, "save_message", AsyncMock())
    with patch("app.services.conversation_service.get_llm_service",
               AsyncMock(return_value=fake_llm)), \
         patch("app.services.conversation_service.acquire_web_context",
               AsyncMock(return_value=([{"title": "t", "url": "https://x", "snippet": "s",
                  "domain": "x", "published_at": None, "source_type": "article",
                  "confidence": 0.5}], {"status": "ok", "key_points": [], "missing_info": []}))), \
         patch.object(crs, "research_and_propose", AsyncMock(return_value=dup_proposal)):
        events = _parse_events(await _collect(svc._handle_conversational(
            db_session, _uuid.uuid4(), "甲公司情况", [], str(project_id)
        )))
    types = [e.get("type") for e in events]
    assert "canvas_fill_proposal" not in types
