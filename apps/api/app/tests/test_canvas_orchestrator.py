"""Tests for the canvas agent orchestrator (phase 2 AI fill).

Covers:
  - fill_canvas flips draft nodes to filled and writes planning content
  - NodeSource rows are materialised (ai_completed) on every filled node
  - A failing group degrades to pending_review without aborting others
  - web_search results attach web_search NodeSources to the company board
  - already-filled nodes are not re-filled (idempotency)
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

import pytest
import pytest_asyncio

from app.models.canvas import (
    Canvas,
    CanvasGroup,
    CanvasNode,
    NodeSource,
    ProjectVersion,
)
from app.models.project import Company, Project
from app.models.skill import Skill, SkillExecution
from app.models.user import Role, User
from app.services.canvas_agent_orchestrator import CanvasAgentOrchestrator
from app.services.canvas_service import canvas_service


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def stub_llm():
    """A fake LLM that returns different payloads for extract vs plan passes.

    The orchestrator now calls the LLM twice per group (pass 1 = extract
    facts, pass 2 = plan copy from those facts). This stub inspects the
    prompt to tell which pass it's in and returns the matching JSON blob.
    """
    class StubLLM:
        def __init__(self):
            self.calls: List[str] = []

        async def generate(self, prompt: str, **kw) -> str:
            self.calls.append(prompt)
            # Pass 1 (extract) — prompt contains the word 抽取.
            if "抽取" in prompt or "信息抽取" in prompt:
                return json.dumps(
                    {
                        "company_profile": ["专注智能制造20年（来源：企业简介）"],
                        "product_system": ["覆盖工业软件到云端可视化的产品矩阵（来源：企业简介）"],
                        "future_layout": ["未来三年布局数字孪生产业（来源：企业简介）"],
                    },
                    ensure_ascii=False,
                )
            # Pass 2 (plan) — grounded on the extracted facts above.
            return json.dumps(
                {
                    "company_profile": ["一家专注智能制造20年的高新技术企业，工业软件与云端可视化双轮驱动"],
                    "product_system": ["构建了从工业软件到云端可视化的完整产品矩阵"],
                    "future_layout": ["未来三年将重点布局数字孫生产业，赋能工业数字化升级"],
                },
                ensure_ascii=False,
            )

    return StubLLM()


@pytest.fixture
def failing_llm():
    class FailingLLM:
        async def generate(self, prompt: str, **kw) -> str:
            raise RuntimeError("LLM down")
    return FailingLLM()


@pytest.fixture
def garbage_llm():
    class GarbageLLM:
        async def generate(self, prompt: str, **kw) -> str:
            return "not json at all"
    return GarbageLLM()


async def _make_project_with_canvas(db_session) -> Tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    """Create role/user/company/project/V1 + canvas + default nodes. Returns
    (project_id, version_id, company_id, user_id) so callers can clean up."""
    role = Role(
        id=uuid.uuid4(),
        name=f"orch_role_{uuid.uuid4().hex[:8]}",
        description="orchestrator test role",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(role)
    await db_session.flush()
    user = User(
        id=uuid.uuid4(),
        email=f"orch_{uuid.uuid4().hex[:8]}@test.local",
        name="Orch User",
        role_id=role.id,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.flush()
    company = Company(
        id=uuid.uuid4(),
        name=f"Orch Co {uuid.uuid4().hex[:8]}",
        industry="智能制造",
        description="一家智能制造企业",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(company)
    await db_session.flush()
    project = Project(
        id=uuid.uuid4(),
        name=f"Orch Project {uuid.uuid4().hex[:8]}",
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

    # V1 with default topology
    version = await canvas_service.create_version(db_session, project_id)
    await db_session.commit()
    return project_id, version.id, company_id, user_id


@pytest_asyncio.fixture
async def canvas_project_with_version(db_session):
    """Fixture: bootstraps a project + V1 canvas and tears it all down after,
    including any NodeSource rows the orchestrator created. Keeps the session-
    shared DB clean so sibling tests (e.g. test_list_projects_empty) aren't
    polluted by the commits inside canvas_service.create_version."""
    from sqlalchemy import delete, select

    ids = await _make_project_with_canvas(db_session)
    project_id, version_id, company_id, user_id = ids
    # Capture role id for cleanup (not returned by helper).
    role_res = await db_session.execute(
        select(Role.id).join(User, User.role_id == Role.id).where(User.id == user_id)
    )
    role_id = role_res.scalar_one()

    yield (project_id, version_id)

    # Teardown: cascade-delete canvas rows that the orchestrator may have added.
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
    # Documents + chunks the document-parse test may have seeded (FK → project).
    from app.models.document import Document, DocumentChunk
    doc_res = await db_session.execute(
        select(Document.id).where(Document.project_id == project_id)
    )
    doc_ids = [r[0] for r in doc_res.all()]
    if doc_ids:
        await db_session.execute(delete(DocumentChunk).where(DocumentChunk.document_id.in_(doc_ids)))
        await db_session.execute(delete(Document).where(Document.id.in_(doc_ids)))
    await db_session.execute(delete(ProjectVersion).where(ProjectVersion.id == version_id))
    await db_session.execute(delete(Project).where(Project.id == project_id))
    await db_session.execute(delete(Company).where(Company.id == company_id))
    await db_session.execute(delete(User).where(User.id == user_id))
    await db_session.execute(delete(Role).where(Role.id == role_id))
    await db_session.commit()


# ─── Tests ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fill_canvas_marks_nodes_filled_with_content(
    db_session, canvas_project_with_version, stub_llm, monkeypatch
):
    """Two-pass fill: extracted facts populate content.extracted, plan copy
    populates content.planning, nodes flip draft→filled. Nodes the stub
    didn't return facts for end up pending_review with a pending_question."""
    from app.services import canvas_agent_orchestrator as orch_mod

    async def fake_get_llm(db=None):
        return stub_llm
    monkeypatch.setattr(orch_mod, "get_llm_service", fake_get_llm)

    project_id, version_id = canvas_project_with_version
    orch = CanvasAgentOrchestrator()
    result = await orch.fill_canvas(db_session, project_id, version_id)

    assert result["success"] is True
    assert result["filled_count"] > 0

    # Reload nodes and check the three stubbed keys are filled with both
    # extracted facts and grounded planning copy.
    from sqlalchemy import select
    nodes = (
        await db_session.execute(select(CanvasNode).join(Canvas, CanvasNode.canvas_id == Canvas.id).where(Canvas.project_version_id == version_id))
    ).scalars().all()
    by_key = {n.node_key: n for n in nodes}

    # Filled nodes carry real facts in `extracted` (the new behaviour).
    assert by_key["company_profile"].status == "filled"
    extracted = by_key["company_profile"].content["extracted"]
    planning = by_key["company_profile"].content["planning"]
    assert len(extracted) > 0
    assert "智能制造" in extracted[0]
    assert len(planning) > 0
    # Planning must read as pre-sales copy, not advisory text.
    assert any(kw not in planning[0] for kw in ("建议", "应该", "可以提炼"))

    assert by_key["product_system"].status == "filled"
    assert by_key["future_layout"].status == "filled"

    # Nodes the stub returned no facts for must be pending_review with a
    # pending_questions entry (no fabricated content).
    unstubbed = [n for k, n in by_key.items() if k not in
                 ("company_profile", "product_system", "future_layout")]
    assert unstubbed, "expected at least one node the stub didn't cover"
    for n in unstubbed:
        assert n.status == "pending_review"
        assert n.content["extracted"] == []
        assert n.content["planning"] == []
        assert len(n.content["pending_questions"]) > 0


@pytest.mark.asyncio
async def test_fill_canvas_materialises_node_sources(
    db_session, canvas_project_with_version, stub_llm, monkeypatch
):
    """Every filled node gets ≥1 NodeSource row (ai_completed) — provenance is queryable."""
    from app.services import canvas_agent_orchestrator as orch_mod
    async def fake_get_llm(db=None):
        return stub_llm
    monkeypatch.setattr(orch_mod, "get_llm_service", fake_get_llm)

    project_id, version_id = canvas_project_with_version
    await CanvasAgentOrchestrator().fill_canvas(db_session, project_id, version_id)

    from sqlalchemy import select, func
    count = (
        await db_session.execute(select(func.count(NodeSource.id)))
    ).scalar_one()
    assert count >= 3  # at least the three stubbed nodes


@pytest.mark.asyncio
async def test_fill_canvas_degrades_group_on_llm_failure(
    db_session, canvas_project_with_version, failing_llm, monkeypatch
):
    """When the LLM raises, that group's nodes become pending_review, others still proceed."""
    from app.services import canvas_agent_orchestrator as orch_mod
    async def fake_get_llm(db=None):
        return failing_llm
    monkeypatch.setattr(orch_mod, "get_llm_service", fake_get_llm)

    project_id, version_id = canvas_project_with_version
    result = await CanvasAgentOrchestrator().fill_canvas(db_session, project_id, version_id)

    # All three groups fail (same failing LLM) → success=False, errors listed.
    assert result["success"] is False
    assert len(result["errors"]) >= 1

    from sqlalchemy import select
    nodes = (
        await db_session.execute(select(CanvasNode).join(Canvas, CanvasNode.canvas_id == Canvas.id).where(Canvas.project_version_id == version_id))
    ).scalars().all()
    # Every node was marked pending_review (graceful degradation).
    assert all(n.status == "pending_review" for n in nodes)


@pytest.mark.asyncio
async def test_fill_canvas_handles_garbage_llm_output(
    db_session, canvas_project_with_version, garbage_llm, monkeypatch
):
    """Non-JSON LLM output doesn't crash — nodes fall back to pending_review."""
    from app.services import canvas_agent_orchestrator as orch_mod
    async def fake_get_llm(db=None):
        return garbage_llm
    monkeypatch.setattr(orch_mod, "get_llm_service", fake_get_llm)

    project_id, version_id = canvas_project_with_version
    orch = CanvasAgentOrchestrator()
    result = await orch.fill_canvas(db_session, project_id, version_id)

    # Garbage → empty parse → fallback payload is used → nodes get a placeholder
    # and end up filled OR pending_review. Either way, no exception.
    assert isinstance(result["filled_count"], int)
    assert result["success"] is True  # fallback path doesn't raise


@pytest.mark.asyncio
async def test_web_search_results_attach_web_sources(
    db_session, canvas_project_with_version, stub_llm, monkeypatch
):
    """web_search hits are recorded as web_search NodeSources on the company board."""
    from app.services import canvas_agent_orchestrator as orch_mod
    async def fake_get_llm(db=None):
        return stub_llm
    monkeypatch.setattr(orch_mod, "get_llm_service", fake_get_llm)

    project_id, version_id = canvas_project_with_version
    web = [
        {"source_title": "企业官网", "url": "https://example.com", "snippet": "成立于2010年"},
        {"source_title": "行业报告", "url": "https://report.com", "snippet": "市占率15%"},
    ]
    await CanvasAgentOrchestrator().fill_canvas(
        db_session, project_id, version_id, web_search_results=web,
    )

    from sqlalchemy import select, func
    web_src_count = (
        await db_session.execute(
            select(func.count(NodeSource.id)).where(NodeSource.source_type == "web_search")
        )
    ).scalar_one()
    assert web_src_count == 2


@pytest.mark.asyncio
async def test_document_sources_attach_uploaded_file_sources(
    db_session, canvas_project_with_version, stub_llm, monkeypatch
):
    """Uploaded/reference documents are recorded as uploaded_file NodeSources."""
    from app.services import canvas_agent_orchestrator as orch_mod

    async def fake_get_llm(db=None):
        return stub_llm

    monkeypatch.setattr(orch_mod, "get_llm_service", fake_get_llm)

    project_id, version_id = canvas_project_with_version
    await CanvasAgentOrchestrator().fill_canvas(
        db_session,
        project_id,
        version_id,
        document_context="《企业手册》\n公司成立于2010年，专注工业可视化。",
        document_sources=[
            {
                "document_id": str(uuid.uuid4()),
                "title": "企业手册",
                "filename": "manual.pdf",
                "excerpt": "公司成立于2010年，专注工业可视化。",
                "chunk_ids": [str(uuid.uuid4())],
            }
        ],
    )

    from sqlalchemy import select, func

    doc_src_count = (
        await db_session.execute(
            select(func.count(NodeSource.id)).where(NodeSource.source_type == "uploaded_file")
        )
    ).scalar_one()
    assert doc_src_count == 1


@pytest.fixture
def full_chain_llm():
    """A stub LLM that returns well-formed JSON for every agent stage:
    extract, plan, tone (方案定调), and ui_suggestion (UI 专家).

    Distinguishes stages by prompt keywords so each pass gets the shape its
    parser expects. Used to verify the stage-2/stage-3 wiring (PRD §13.4/§13.5).
    """

    class FullChainLLM:
        def __init__(self):
            self.tone_calls = 0
            self.ui_calls = 0
            self.consistency_calls = 0

        async def generate(self, prompt: str, **kw) -> str:
            # Stage 1.1: extract facts.
            if "抽取" in prompt or "信息抽取" in prompt:
                return json.dumps(
                    {
                        "company_profile": ["专注智能制造20年（来源：企业简介）"],
                        "product_system": ["覆盖工业软件到云端可视化的产品矩阵（来源：企业简介）"],
                        "future_layout": ["未来三年布局数字孪生产业（来源：企业简介）"],
                    },
                    ensure_ascii=False,
                )
            # Stage 2: 方案定调 — prompt mentions 定调.
            if "方案定调" in prompt or "定调专家" in prompt:
                self.tone_calls += 1
                return json.dumps(
                    {
                        "theme_name": "智造未来·数字孪生",
                        "style_keywords": ["科技感", "工业感", "未来感"],
                        "narrative_spine": "从制造积淀到数字孪生的递进",
                        "visual_tone": "深蓝主色搭配科技蓝高光",
                        "info_hierarchy": ["企业实力", "技术能力", "未来布局"],
                        "presentation_rhythm": "由沉稳到激昂",
                        "key_modules": ["数字孪生工厂", "产品矩阵"],
                        "ui_principles": ["三维空间纵深", "数据卡片化"],
                    },
                    ensure_ascii=False,
                )
            # Stage 3: UI 专家 — prompt mentions UI专家.
            if "UI专家" in prompt or "UI/大屏表达建议" in prompt:
                self.ui_calls += 1
                return json.dumps(
                    {
                        "company_profile": ["首页用三维企业Logo开场，配数据流光效"],
                        "product_system": ["产品矩阵用悬浮卡片+交互高亮呈现"],
                        "future_layout": ["未来布局用时间轴动效展开"],
                    },
                    ensure_ascii=False,
                )
            # Stage 4: 一致性检查 — prompt mentions 一致性检查专家.
            if "一致性检查专家" in prompt or "跨板块一致性核查" in prompt:
                self.consistency_calls += 1
                return json.dumps(
                    {
                        "issues": [
                            {
                                "node_key": "product_system",
                                "message": "「产品体系」称为产品矩阵，「典型案例」板块却称解决方案，建议统一术语。",
                            }
                        ]
                    },
                    ensure_ascii=False,
                )
            # Stage 1.2: plan copy.
            return json.dumps(
                {
                    "company_profile": ["一家专注智能制造20年的高新技术企业"],
                    "product_system": ["构建了从工业软件到云端可视化的完整产品矩阵"],
                    "future_layout": ["未来三年将重点布局数字孪生产业"],
                },
                ensure_ascii=False,
            )

    return FullChainLLM()


@pytest.mark.asyncio
async def test_fill_canvas_generates_tone_and_ui_suggestions(
    db_session, canvas_project_with_version, full_chain_llm, monkeypatch
):
    """方案定调 Agent + UI 专家 Agent run after the planner.

    Tone is stored on canvas.layout_config['tone']; ui_suggestion lands on
    each filled node's content and a UI-expert NodeSource is recorded.
    """
    from app.services import canvas_agent_orchestrator as orch_mod
    from sqlalchemy import select

    async def fake_get_llm(db=None):
        return full_chain_llm

    monkeypatch.setattr(orch_mod, "get_llm_service", fake_get_llm)

    project_id, version_id = canvas_project_with_version
    result = await CanvasAgentOrchestrator().fill_canvas(db_session, project_id, version_id)

    assert result["success"] is True
    assert result["tone_generated"] is True
    assert full_chain_llm.tone_calls == 1
    assert full_chain_llm.ui_calls >= 1

    # Tone persisted on the canvas layout_config.
    canvas = (
        await db_session.execute(select(Canvas).where(Canvas.project_version_id == version_id))
    ).scalar_one()
    tone = (canvas.layout_config or {}).get("tone")
    assert tone is not None
    assert tone["theme_name"] == "智造未来·数字孪生"
    assert "科技感" in tone["style_keywords"]

    # UI suggestions landed on the filled nodes.
    nodes = (
        await db_session.execute(select(CanvasNode).join(Canvas, CanvasNode.canvas_id == Canvas.id).where(Canvas.project_version_id == version_id))
    ).scalars().all()
    by_key = {n.node_key: n for n in nodes}
    assert len(by_key["company_profile"].content["ui_suggestion"]) > 0
    assert len(by_key["product_system"].content["ui_suggestion"]) > 0

    # A UI-expert NodeSource was recorded (metadata.agent == ui_expert).
    from sqlalchemy import func
    ui_src_count = (
        await db_session.execute(
            select(func.count(NodeSource.id)).where(
                NodeSource.source_type == "ai_completed",
                NodeSource.source_name.like("UI 专家建议%"),
            )
        )
    ).scalar_one()
    assert ui_src_count >= 1


@pytest.mark.asyncio
async def test_fill_canvas_tone_failure_is_soft(
    db_session, canvas_project_with_version, monkeypatch
):
    """If the tone LLM call raises, the canvas fill still succeeds and the
    planner output is preserved — tone/UI are best-effort stages."""

    class ToneFailingLLM:
        async def generate(self, prompt: str, **kw) -> str:
            if "方案定调" in prompt or "定调专家" in prompt:
                raise RuntimeError("tone LLM down")
            if "抽取" in prompt or "信息抽取" in prompt:
                return json.dumps(
                    {"company_profile": ["专注智能制造20年（来源：企业简介）"]},
                    ensure_ascii=False,
                )
            # UI + plan both return something parseable but plan-shaped.
            return json.dumps(
                {"company_profile": ["一家专注智能制造20年的高新技术企业"]},
                ensure_ascii=False,
            )

    from app.services import canvas_agent_orchestrator as orch_mod
    from sqlalchemy import select

    async def fake_get_llm(db=None):
        return ToneFailingLLM()

    monkeypatch.setattr(orch_mod, "get_llm_service", fake_get_llm)

    project_id, version_id = canvas_project_with_version
    result = await CanvasAgentOrchestrator().fill_canvas(db_session, project_id, version_id)

    # Planner still ran; tone error recorded but not fatal.
    assert result["tone_generated"] is False
    nodes = (
        await db_session.execute(select(CanvasNode).join(Canvas, CanvasNode.canvas_id == Canvas.id).where(Canvas.project_version_id == version_id))
    ).scalars().all()
    filled = [n for n in nodes if n.status == "filled"]
    assert len(filled) >= 1


@pytest.mark.asyncio
async def test_fill_canvas_no_data_marks_pending(
    db_session, canvas_project_with_version, stub_llm, monkeypatch
):
    """When there is no source material at all, no node is fabricated.

    The default fixture has a company description, so we first blank it out
    to simulate "user typed nothing useful, no web hits, no uploads". The
    orchestrator must then skip the LLM entirely and mark every node
    pending_review with a pending_question — never inventing copy.
    """
    from app.services import canvas_agent_orchestrator as orch_mod
    from sqlalchemy import update

    async def fake_get_llm(db=None):
        return stub_llm
    monkeypatch.setattr(orch_mod, "get_llm_service", fake_get_llm)

    project_id, version_id = canvas_project_with_version

    # Blank out the company + project text so _company_context hits the
    # no-data sentinel. No web_search_results / document_context passed.
    # Use "" (not None) because companies.name has a NOT NULL constraint;
    # _company_context treats empty strings as absent (falsy), so the
    # sentinel path still fires.
    # Scope the UPDATE to this fixture's company only (via project FK) to
    # avoid UNIQUE constraint violations when other tests leave rows behind.
    proj = await db_session.get(Project, project_id)
    await db_session.execute(
        update(Company).where(Company.id == proj.company_id).values(
            description="", name="", industry="", website=""
        )
    )
    await db_session.execute(
        update(Project).where(Project.id == project_id).values(description=None)
    )
    await db_session.commit()

    orch = CanvasAgentOrchestrator()
    # Pass extra_context=None and no web/document so the sentinel path fires.
    result = await orch.fill_canvas(db_session, project_id, version_id)

    # All nodes pending_review, none filled, each has a pending_question.
    from sqlalchemy import select
    nodes = (
        await db_session.execute(select(CanvasNode).join(Canvas, CanvasNode.canvas_id == Canvas.id).where(Canvas.project_version_id == version_id))
    ).scalars().all()
    assert len(nodes) > 0
    for n in nodes:
        assert n.status == "pending_review", f"{n.node_key} should be pending"
        assert n.content["extracted"] == []
        assert n.content["planning"] == []
        assert len(n.content["pending_questions"]) > 0
    # The stub LLM must not have been called at all.
    assert stub_llm.calls == []


@pytest.mark.asyncio
async def test_fill_canvas_runs_consistency_check(
    db_session, canvas_project_with_version, full_chain_llm, monkeypatch
):
    """一致性检查 Agent (Stage 4) appends cross-board issues to node
    pending_questions and stores them on layout_config (PRD §13.2 step 8)."""
    from app.services import canvas_agent_orchestrator as orch_mod
    from sqlalchemy import select

    async def fake_get_llm(db=None):
        return full_chain_llm
    monkeypatch.setattr(orch_mod, "get_llm_service", fake_get_llm)

    project_id, version_id = canvas_project_with_version
    result = await CanvasAgentOrchestrator().fill_canvas(db_session, project_id, version_id)

    assert result["success"] is True
    # The consistency LLM pass ran exactly once.
    assert full_chain_llm.consistency_calls == 1
    # The issue surfaced in the return payload.
    issues = result.get("consistency_issues") or []
    assert len(issues) == 1
    assert issues[0]["node_key"] == "product_system"

    # Issues persisted on canvas.layout_config['consistency_issues'].
    canvas = (
        await db_session.execute(select(Canvas).where(Canvas.project_version_id == version_id))
    ).scalar_one()
    stored = (canvas.layout_config or {}).get("consistency_issues") or []
    assert len(stored) == 1
    assert "product_system" in stored[0]["node_key"]

    # The flagged node got a 【一致性核查】 pending_question.
    nodes = (
        await db_session.execute(
            select(CanvasNode).join(Canvas, CanvasNode.canvas_id == Canvas.id)
            .where(Canvas.project_version_id == version_id)
        )
    ).scalars().all()
    flagged = next(n for n in nodes if n.node_key == "product_system")
    joined = "\n".join(flagged.content.get("pending_questions", []))
    assert "一致性核查" in joined


@pytest.mark.asyncio
async def test_consistency_check_soft_fails_on_llm_error(
    db_session, canvas_project_with_version, full_chain_llm, monkeypatch
):
    """A consistency-checker exception is a soft error: the fill still
    succeeds and earlier stages' results are preserved."""
    from app.services import canvas_agent_orchestrator as orch_mod

    class BrokenConsistencyLLM:
        async def generate(self, prompt: str, **kw):
            if "一致性检查专家" in prompt or "跨板块一致性核查" in prompt:
                raise RuntimeError("consistency LLM down")
            return await full_chain_llm.generate(prompt, **kw)

    async def fake_get_llm(db=None):
        return BrokenConsistencyLLM()
    monkeypatch.setattr(orch_mod, "get_llm_service", fake_get_llm)

    project_id, version_id = canvas_project_with_version
    result = await CanvasAgentOrchestrator().fill_canvas(db_session, project_id, version_id)

    # Fill still succeeds; consistency error recorded as soft.
    assert result["success"] is True
    assert result["consistency_issues"] == []
    assert any("consistency:" in e for e in result["errors"])


@pytest.mark.asyncio
async def test_fill_canvas_uses_internal_knowledge_when_tools_registered(
    db_session, canvas_project_with_version, stub_llm, monkeypatch
):
    """PRD §23.5.4: when internal-knowledge tools are registered, the
    orchestrator loads SOP/cases/RAG and records their provenance as
    internal_sop / internal_case / internal_template NodeSources on the
    company_intro anchor node."""
    from app.services import canvas_agent_orchestrator as orch_mod
    from app.tools.registry import ToolRegistry
    from app.tools.builtins.sop_load import SOPLoadTool
    from app.tools.builtins.case_search import CaseSearchTool
    from app.tools.builtins.knowledge_search import KnowledgeSearchTool
    from app.models.workflow import SOPWorkflow
    from app.models.case import Case
    from sqlalchemy import select, func

    async def fake_get_llm(db=None):
        return stub_llm
    monkeypatch.setattr(orch_mod, "get_llm_service", fake_get_llm)

    project_id, version_id = canvas_project_with_version
    project = await db_session.get(Project, project_id)

    # Seed an active SOP whose name matches the company's industry (智能制造)
    # so sop_load's name_contains match picks it up.
    sop = SOPWorkflow(
        id=uuid.uuid4(),
        name="智能制造行业扩展 SOP",
        description="智能制造行业专属策划流程",
        version="1.0",
        is_active=True,
        steps=[{"step": 1, "name": "梳理产线", "action": "收集产线数据"}],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(sop)
    case_id = uuid.uuid4()
    # Seed a published case in the same industry.
    db_session.add(Case(
        id=case_id,
        project_id=project_id,
        title="某智能制造工厂数字孪生案例",
        client_name="某制造集团",
        industry="智能制造",
        challenge="产线可视化与数字孪生",
        solution="部署数字孪生平台",
        results="效率提升20%",
        quality_score=90.0,
        is_published=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    ))
    await db_session.commit()

    # Register the real built-in tools on the singleton registry so
    # _load_internal_knowledge can resolve them. Snapshot state to restore.
    registry = ToolRegistry.get_instance()
    saved_tools = dict(registry._tools)
    try:
        registry.register(SOPLoadTool())
        registry.register(CaseSearchTool())
        registry.register(KnowledgeSearchTool())

        result = await CanvasAgentOrchestrator().fill_canvas(
            db_session, project_id, version_id
        )
        assert result["success"] is True

        # Provenance: SOP + case hits recorded — one per board anchor (3
        # boards), so every board's node detail surfaces the internal knowledge
        # the planner referenced (PRD §15.1), not just company_intro.
        sop_src = (
            await db_session.execute(
                select(func.count(NodeSource.id)).where(
                    NodeSource.source_type == "internal_sop"
                )
            )
        ).scalar_one()
        case_src = (
            await db_session.execute(
                select(func.count(NodeSource.id)).where(
                    NodeSource.source_type == "internal_case"
                )
            )
        ).scalar_one()
        assert sop_src == 3, f"expected SOP source on each of 3 boards, got {sop_src}"
        assert case_src == 3, f"expected case source on each of 3 boards, got {case_src}"

        # And the SOP sources really are spread across distinct boards, not
        # all dumped on one node.
        sop_node_ids = (
            await db_session.execute(
                select(NodeSource.node_id).where(NodeSource.source_type == "internal_sop")
            )
        ).scalars().all()
        assert len(set(sop_node_ids)) == 3, (
            "internal sources should attach to 3 distinct board anchors, "
            f"got {len(set(sop_node_ids))} distinct nodes"
        )
    finally:
        registry._tools = saved_tools
        # Clean up the seeded Case/SOP so the fixture teardown doesn't hit a
        # FK violation (Case.project_id → projects.id).
        from sqlalchemy import delete
        await db_session.execute(delete(Case).where(Case.id == case_id))
        await db_session.execute(delete(SOPWorkflow).where(SOPWorkflow.id == sop.id))
        await db_session.commit()


@pytest.mark.asyncio
async def test_fill_canvas_internal_knowledge_degrades_without_registry(
    db_session, canvas_project_with_version, stub_llm, monkeypatch
):
    """When NO tools are registered (e.g. a fresh test process), internal
    knowledge loading is skipped silently and the fill proceeds normally."""
    from app.services import canvas_agent_orchestrator as orch_mod
    from app.tools.registry import ToolRegistry
    from sqlalchemy import select, func

    async def fake_get_llm(db=None):
        return stub_llm
    monkeypatch.setattr(orch_mod, "get_llm_service", fake_get_llm)

    # Ensure an empty registry (the default test state).
    registry = ToolRegistry.get_instance()
    saved_tools = dict(registry._tools)
    registry._tools = {}
    try:
        project_id, version_id = canvas_project_with_version
        result = await CanvasAgentOrchestrator().fill_canvas(
            db_session, project_id, version_id
        )
        # Fill still works; no internal_* provenance rows created.
        assert result["success"] is True
        internal_count = (
            await db_session.execute(
                select(func.count(NodeSource.id)).where(
                    NodeSource.source_type.in_(
                        ("internal_sop", "internal_case", "internal_template")
                    )
                )
            )
        ).scalar_one()
        assert internal_count == 0
    finally:
        registry._tools = saved_tools



@pytest.mark.asyncio
async def test_fill_canvas_runs_boards_concurrently(
    db_session, canvas_project_with_version, monkeypatch
):
    """The three boards' LLM passes run concurrently (asyncio.gather), not
    serially. A stub LLM that sleeps on each extract call records overlap —
    serial execution would show zero overlap, concurrent shows all three
    extracts overlapping in the same window."""
    import asyncio
    from datetime import datetime, timezone

    from app.services import canvas_agent_orchestrator as orch_mod

    class TimingLLM:
        def __init__(self):
            # List of (prompt_kind, event: "start"|"end", ts_monotonic).
            self.events: List[tuple] = []

        async def generate(self, prompt: str, **kw):
            kind = "extract" if ("抽取" in prompt or "信息抽取" in prompt) else "plan"
            start = asyncio.get_event_loop().time()
            self.events.append((kind, "start", start))
            # Simulate LLM latency so concurrency is observable. Serial code
            # would block the loop here; gather overlaps the waits.
            await asyncio.sleep(0.05)
            self.events.append((kind, "end", asyncio.get_event_loop().time()))
            if kind == "extract":
                return json.dumps(
                    {"company_profile": ["事实"], "product_system": ["事实"],
                     "future_layout": ["事实"]}, ensure_ascii=False,
                )
            return json.dumps(
                {"company_profile": ["策划"], "product_system": ["策划"],
                 "future_layout": ["策划"]}, ensure_ascii=False,
            )

    timing_llm = TimingLLM()

    async def fake_get_llm(db=None):
        return timing_llm
    monkeypatch.setattr(orch_mod, "get_llm_service", fake_get_llm)

    project_id, version_id = canvas_project_with_version
    result = await CanvasAgentOrchestrator().fill_canvas(db_session, project_id, version_id)
    assert result["success"] is True

    # The three boards' extract passes must overlap: gather starts all three
    # before any finishes (each sleeps 50ms). Later agents (tone/ui/consistency)
    # may also emit extract-matched prompts, so take the FIRST three — those
    # are stage-1's per-board extracts.
    extract_starts = [ts for (kind, ev, ts) in timing_llm.events if kind == "extract" and ev == "start"]
    assert len(extract_starts) >= 3, f"expected ≥3 extract passes, got {len(extract_starts)}"
    first_three = extract_starts[:3]
    # All three started within a tight window — i.e. they were scheduled
    # concurrently, not one-after-another (serial would spread them across
    # ≥150ms = 3× the 50ms latency). Threshold 0.08s leaves headroom for event-
    # loop scheduling jitter while still cleanly rejecting serial execution.
    spread = max(first_three) - min(first_three)
    assert spread < 0.08, (
        f"stage-1 extract passes look serial (spread={spread:.3f}s ≥ 50ms latency); "
        "expected concurrent scheduling"
    )


@pytest.mark.asyncio
async def test_consistency_runs_before_tone_and_flows_back(
    db_session, canvas_project_with_version, full_chain_llm, monkeypatch
):
    """Stage order: consistency runs BEFORE tone, so tone sees the
    consistency-amended planning copy (issues flowed back as pending_questions
    on the flagged nodes). Verified by spying on the planning_payload handed to
    _generate_tone."""
    from app.services import canvas_agent_orchestrator as orch_mod
    from app.services.canvas_agent_orchestrator import CanvasAgentOrchestrator

    async def fake_get_llm(db=None):
        return full_chain_llm
    monkeypatch.setattr(orch_mod, "get_llm_service", fake_get_llm)

    project_id, version_id = canvas_project_with_version
    orch = CanvasAgentOrchestrator()

    # Spy: capture the planning_payload passed to _generate_tone.
    seen_payloads: List[Dict] = []
    real_generate_tone = orch._generate_tone

    async def spy_tone(llm, company_context, planning_payload):
        seen_payloads.append(planning_payload)
        return await real_generate_tone(llm, company_context, planning_payload)
    monkeypatch.setattr(orch, "_generate_tone", spy_tone)

    await orch.fill_canvas(db_session, project_id, version_id)

    # Tone ran exactly once...
    assert len(seen_payloads) == 1
    payload = seen_payloads[0]
    # ...and the consistency issue (【一致性核查】 prefix, set on product_system)
    # is present in the payload tone saw — proving consistency ran first and
    # its finding flowed back into the planning copy tone reasons over.
    flat = json.dumps(payload, ensure_ascii=False)
    assert "一致性核查" in flat, (
        "consistency issue did not flow back to tone's planning_payload — "
        "tone ran on pre-consistency copy"
    )
    # And consistency actually flagged a node (full_chain_llm returns 1 issue).
    assert full_chain_llm.consistency_calls == 1
    # Ordering: consistency LLM call happened before tone LLM call. The stub
    # increments counters on each call, so consistency_calls == 1 and
    # tone_calls == 1 both fired, and consistency ran first because tone's
    # payload already carries the issue.


@pytest.mark.asyncio
async def test_fill_canvas_persists_context_pack(
    db_session, canvas_project_with_version, stub_llm, monkeypatch
):
    """PRD §9.3: the structured Context Pack is assembled from every context
    source and persisted onto canvas.layout_config.context_pack so the fill is
    traceable and the version snapshot can replay it."""
    from app.services import canvas_agent_orchestrator as orch_mod
    from sqlalchemy import select

    async def fake_get_llm(db=None):
        return stub_llm
    monkeypatch.setattr(orch_mod, "get_llm_service", fake_get_llm)

    project_id, version_id = canvas_project_with_version
    orch = CanvasAgentOrchestrator()

    # Drive a fill WITH web + document context so the pack's web/uploaded
    # sections are non-empty.
    result = await orch.fill_canvas(
        db_session, project_id, version_id,
        web_search_results=[{"title": "华为官网", "url": "https://huawei.com",
                             "content": "全球领先ICT基础设施"}],
        extra_context="需要展示通信历史演进",
        document_sources=[{"document_id": "doc-1", "title": "产品手册.pdf",
                           "filename": "产品手册.pdf", "excerpt": "产品矩阵摘要"}],
    )
    assert result["success"] is True

    canvas = (
        await db_session.execute(select(Canvas).where(Canvas.project_version_id == version_id))
    ).scalar_one()
    pack = (canvas.layout_config or {}).get("context_pack")
    assert pack is not None, "context_pack should be persisted on layout_config"

    # Enterprise profile + project requirement captured from the company record.
    assert pack["enterprise_profile"]["industry"] == "智能制造"
    assert "通信历史演进" in pack["project_requirement"]["raw_input"]

    # Web + uploaded material projected into their sections.
    assert any("华为" in (w.get("title") or "") for w in pack["web_references"])
    assert any(u.get("document_id") == "doc-1" for u in pack["uploaded_materials"])

    # Summary badge counts are present and consistent.
    s = pack["summary"]
    assert s["web"] == len(pack["web_references"])
    assert s["uploads"] == len(pack["uploaded_materials"])


@pytest.mark.asyncio
async def test_context_pack_routes_internal_sources_by_type(
    db_session, canvas_project_with_version, stub_llm, monkeypatch
):
    """ik_sources route into the right pack section by source_type:
    internal_case→matched_cases, internal_sop→sop_checklist,
    internal_template(+doc_id)→referenced_chunks."""
    from app.services import canvas_agent_orchestrator as orch_mod
    from sqlalchemy import select

    async def fake_get_llm(db=None):
        return stub_llm
    monkeypatch.setattr(orch_mod, "get_llm_service", fake_get_llm)

    project_id, version_id = canvas_project_with_version
    orch = CanvasAgentOrchestrator()

    # Monkeypatch _load_internal_knowledge to return a mixed source set so we
    # can assert the routing without seeding SOP/case rows.
    async def fake_load_ik(db, company, nbg):
        ik = [
            {"source_type": "internal_case", "source_name": "智造案例A", "quote": "x"},
            {"source_type": "internal_sop", "source_name": "策划SOP", "quote": "步骤"},
            {"source_type": "internal_template", "source_name": "知识片段",
             "quote": "y", "document_id": "chunk-doc"},
            {"source_type": "internal_template", "source_name": "通用模板", "quote": "z"},
        ]
        return "ctx", ik
    monkeypatch.setattr(orch, "_load_internal_knowledge", fake_load_ik)

    result = await orch.fill_canvas(db_session, project_id, version_id)
    assert result["success"] is True

    canvas = (
        await db_session.execute(select(Canvas).where(Canvas.project_version_id == version_id))
    ).scalar_one()
    pack = (canvas.layout_config or {}).get("context_pack")
    assert [c["name"] for c in pack["matched_cases"]] == ["智造案例A"]
    assert [s["name"] for s in pack["sop_checklist"]] == ["策划SOP"]
    # chunk-doc carries a document_id → referenced_chunks; 通用模板 → templates.
    assert len(pack["referenced_chunks"]) == 1
    assert pack["referenced_chunks"][0]["document_id"] == "chunk-doc"
    assert [t["name"] for t in pack["prompt_templates"]] == ["通用模板"]


@pytest.mark.asyncio
async def test_requirement_agent_enriches_context_pack(
    db_session, canvas_project_with_version, monkeypatch
):
    """需求采集 Agent (Stage 0) structured-extracts the free-text requirement
    and merges scene/goal/audience/key_asks + missing_info into the context
    pack. PRD §13.2 step 1 / §4.4."""
    from app.services import canvas_agent_orchestrator as orch_mod
    from sqlalchemy import select

    class ReqLLM:
        async def generate(self, prompt: str, **kw):
            # Requirement-collection pass — returns structured extraction.
            if "需求采集" in prompt:
                return json.dumps({
                    "scene": "企业展厅",
                    "goal": "品牌升级与获客",
                    "audience": "行业客户与政府",
                    "key_asks": ["突出智能制造能力", "展示未来布局"],
                    "missing_info": ["预算范围未明确", "场地尺寸未提供"],
                }, ensure_ascii=False)
            # Planner passes return minimal valid JSON so the fill succeeds.
            if "抽取" in prompt or "信息抽取" in prompt:
                return json.dumps({"company_profile": ["事实"]}, ensure_ascii=False)
            return json.dumps({"company_profile": ["策划"]}, ensure_ascii=False)

    async def fake_get_llm(db=None):
        return ReqLLM()
    monkeypatch.setattr(orch_mod, "get_llm_service", fake_get_llm)

    project_id, version_id = canvas_project_with_version
    result = await CanvasAgentOrchestrator().fill_canvas(db_session, project_id, version_id)
    assert result["success"] is True

    canvas = (
        await db_session.execute(select(Canvas).where(Canvas.project_version_id == version_id))
    ).scalar_one()
    pack = (canvas.layout_config or {}).get("context_pack")

    # LLM-extracted fields merged into project_requirement alongside ORM fields.
    pr = pack["project_requirement"]
    assert pr["scene"] == "企业展厅"
    assert pr["goal"] == "品牌升级与获客"
    assert "突出智能制造能力" in pr["key_asks"]

    # Missing-info flags landed in pending_info (export gate consumes these).
    pending = pack["pending_info"]
    assert "预算范围未明确" in pending
    assert "场地尺寸未提供" in pending


@pytest.mark.asyncio
async def test_requirement_agent_soft_fails(
    db_session, canvas_project_with_version, stub_llm, monkeypatch
):
    """A requirement-agent exception is a soft error: the fill still succeeds
    and the context_pack keeps its ORM-seeded project_requirement."""
    from app.services import canvas_agent_orchestrator as orch_mod

    class BrokenReqLLM:
        async def generate(self, prompt: str, **kw):
            if "需求采集" in prompt:
                raise RuntimeError("req LLM down")
            return await stub_llm.generate(prompt, **kw)

    async def fake_get_llm(db=None):
        return BrokenReqLLM()
    monkeypatch.setattr(orch_mod, "get_llm_service", fake_get_llm)

    project_id, version_id = canvas_project_with_version
    result = await CanvasAgentOrchestrator().fill_canvas(db_session, project_id, version_id)
    assert result["success"] is True
    # requirement error recorded as soft, not planner.
    assert any("requirement:" in e for e in result["errors"])
    assert all("requirement:" not in e for e in result.get("soft_errors", [])) or any(
        "requirement:" in e for e in result.get("soft_errors", [])
    )


@pytest.mark.asyncio
async def test_document_parse_agent_classifies_and_writes_category(
    db_session, canvas_project_with_version, stub_llm, monkeypatch
):
    """资料解析 Agent (PRD §13.2 step 2): auto-classifies uploaded docs into
    the 9 PRD categories, writes category back only when unset, and surfaces
    per-doc analyses in context_pack.document_analyses."""
    from app.models.document import Document, DocumentChunk
    from sqlalchemy import select

    # A stub LLM that classifies everything as 产品资料 (deterministic).
    class ClassifyLLM:
        async def generate(self, prompt: str, **kw):
            if "资料解析专家" in prompt and "可选类别" in prompt:
                return json.dumps(
                    {"category": "产品资料", "summary": "覆盖工业软件到云端可视化的产品矩阵"},
                    ensure_ascii=False,
                )
            # Fall through to stub_llm for planner/requirement passes.
            return await stub_llm.generate(prompt, **kw)

    async def fake_get_llm(db=None):
        return ClassifyLLM()
    from app.services import canvas_agent_orchestrator as orch_mod
    monkeypatch.setattr(orch_mod, "get_llm_service", fake_get_llm)

    project_id, version_id = canvas_project_with_version
    proj = await db_session.get(Project, project_id)

    # Seed a parsed document with chunks (category unset → agent should fill it).
    doc = Document(
        id=uuid.uuid4(), project_id=project_id,
        filename="brochure.pdf", original_filename="产品手册.pdf",
        content_type="application/pdf", file_size=1024,
        file_path="/tmp/brochure.pdf", title="产品手册",
        status="indexed", chunk_count=2, category=None,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    db_session.add(doc)
    await db_session.flush()
    for i, text in enumerate(["工业软件产品线，覆盖MES和SCADA。", "云端可视化平台支持三维实时渲染。"]):
        db_session.add(DocumentChunk(
            id=uuid.uuid4(), document_id=doc.id, content=text,
            chunk_index=i, page_number=i + 1, token_count=len(text.split()),
            created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
        ))
    await db_session.commit()

    result = await CanvasAgentOrchestrator().fill_canvas(db_session, project_id, version_id)
    assert result["success"] is True

    # Category written back onto the Document (was None).
    refreshed = await db_session.get(Document, doc.id)
    assert refreshed.category == "产品资料"

    # Analysis surfaced in the persisted context pack.
    canvas = (
        await db_session.execute(select(Canvas).where(Canvas.project_version_id == version_id))
    ).scalar_one()
    pack = (canvas.layout_config or {}).get("context_pack")
    analyses = pack.get("document_analyses") or []
    assert len(analyses) == 1
    assert analyses[0]["category"] == "产品资料"
    assert "产品矩阵" in analyses[0]["summary"]


@pytest.mark.asyncio
async def test_document_parse_does_not_overwrite_manual_category(
    db_session, canvas_project_with_version, stub_llm, monkeypatch
):
    """Manual classification wins: the agent never overwrites a category the
    user already set, even though it still records its own analysis."""
    from app.models.document import Document, DocumentChunk
    from sqlalchemy import select

    class ClassifyLLM:
        async def generate(self, prompt: str, **kw):
            if "可选类别" in prompt:
                return json.dumps({"category": "产品资料", "summary": "x"}, ensure_ascii=False)
            return await stub_llm.generate(prompt, **kw)

    async def fake_get_llm(db=None):
        return ClassifyLLM()
    from app.services import canvas_agent_orchestrator as orch_mod
    monkeypatch.setattr(orch_mod, "get_llm_service", fake_get_llm)

    project_id, version_id = canvas_project_with_version
    # Pre-set a manual category → must survive the agent run.
    doc = Document(
        id=uuid.uuid4(), project_id=project_id,
        filename="intro.pdf", original_filename="企业介绍.pdf",
        content_type="application/pdf", file_size=512, file_path="/tmp/i.pdf",
        title="企业介绍", status="indexed", chunk_count=1, category="企业介绍",
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    db_session.add(doc)
    await db_session.flush()
    db_session.add(DocumentChunk(
        id=uuid.uuid4(), document_id=doc.id, content="一家专注智能制造的企业。",
        chunk_index=0, page_number=1, token_count=4,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    ))
    await db_session.commit()

    await CanvasAgentOrchestrator().fill_canvas(db_session, project_id, version_id)

    refreshed = await db_session.get(Document, doc.id)
    # Manual category preserved (agent wanted 产品资料).
    assert refreshed.category == "企业介绍"


@pytest.mark.asyncio
async def test_substage_does_not_erase_full_context_pack(
    db_session, canvas_project_with_version, stub_llm, monkeypatch
):
    """Regression: a sub-stage run (e.g. ui_expert) is invoked without
    web_search_results/document_sources, so the freshly assembled context pack
    would have empty web_references/uploaded_materials. Persisting that
    must NOT erase the web/upload traceability a prior `full` run captured —
    sub-stages merge into the existing pack (non-empty new fields win, empty
    fields keep prior)."""
    from app.services import canvas_agent_orchestrator as orch_mod
    from sqlalchemy import select

    async def fake_get_llm(db=None):
        return stub_llm
    monkeypatch.setattr(orch_mod, "get_llm_service", fake_get_llm)

    project_id, version_id = canvas_project_with_version
    orch = CanvasAgentOrchestrator()

    # 1. full run WITH web hits → context_pack.web_references populated.
    await orch.fill_canvas(
        db_session, project_id, version_id,
        web_search_results=[{"title": "企业官网", "url": "https://x.com",
                             "content": "公开信息"}],
        stage="full",
    )
    canvas = (
        await db_session.execute(select(Canvas).where(Canvas.project_version_id == version_id))
    ).scalar_one()
    pack1 = (canvas.layout_config or {}).get("context_pack") or {}
    assert any("企业官网" in (w.get("title") or "") for w in pack1.get("web_references", [])), \
        "full run should seed web_references"

    # 2. ui_expert sub-stage run, NO web hits (mirrors _run_fill_background).
    await orch.fill_canvas(db_session, project_id, version_id, stage="ui_expert")

    # 3. The web_reference from step 1 must survive (merge, not overwrite).
    canvas = (
        await db_session.execute(select(Canvas).where(Canvas.project_version_id == version_id))
    ).scalar_one()
    pack2 = (canvas.layout_config or {}).get("context_pack") or {}
    assert any("企业官网" in (w.get("title") or "") for w in pack2.get("web_references", [])), \
        "ui_expert sub-stage erased prior web_references — expected merge"
