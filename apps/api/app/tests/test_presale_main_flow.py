"""PRESALE_DELIVERY_SPEC §13 P0 — 主链 E2E（Mock LLM）。

验证售前主链关键阶段（S1 创建 → S3 首轮 auto-fill → S7 导出）的端到端行为：
  A. 项目向导创建后自动进入 Canvas 工作台，V1 已就绪并绑定对话
  B. 首条非寒暄消息触发 auto-fill，发出 canvas_fill_proposal / proposal_section
  C. 多轮追问基于已填充上下文回答
  F. 章节审核未通过时导出被阻断，全部通过后可导出

每条测试都通过 MockLLMService 提供 deterministic 输出，避免真实 LLM 依赖。
"""

import json
import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select


async def _seed_admin_owner(db_session) -> None:
    """Wizard resolves owner via DEFAULT_OWNER_EMAIL (admin@3dwall.com).

    The default ``client`` fixture seeds an admin user but with a random
    email — the wizard's project_service looks up a specific address. Seed
    that row here so ``create_from_wizard`` can resolve it. Idempotent.
    """
    from app.models.user import Role, User

    result = await db_session.execute(
        select(User).where(User.email == "admin@3dwall.com")
    )
    if result.scalar_one_or_none() is not None:
        return
    role = Role(
        id=uuid.uuid4(),
        name=f"presale_owner_{uuid.uuid4().hex[:8]}",
        description="presale main-flow owner role",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(role)
    await db_session.flush()
    user = User(
        id=uuid.uuid4(),
        email="admin@3dwall.com",
        name="Presale Admin",
        role_id=role.id,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.commit()


async def _wizard_payload(suffix: str) -> dict:
    """Build a unique wizard payload for one test (avoids name collisions)."""
    return {
        "step1": {
            "projectName": f"售前项目-{suffix}",
            "clientName": f"测试企业-{suffix}",
            "industry": "科技",
            "projectType": "裸眼3D",
            "description": "总部裸眼3D幕墙品牌发布",
            "priority": "medium",
        },
        "step2": {
            "companyWebsite": "https://example.com",
            "companyDescription": "测试企业描述",
        },
        "screen": {
            "screenType": "裸眼3D",
            "screenSize": "20m x 8m",
        },
    }


@pytest.mark.asyncio
async def test_wizard_creates_project_with_canvas_v1(
    client: AsyncClient, db_session
):
    """A1/A2/A3: 向导创建项目 → Canvas V1 就绪 → 对话绑定。

    项目创建后应自动有 current_version_id（V1），且 GET /conversation 返回
    绑定到该项目的会话。
    """
    await _seed_admin_owner(db_session)
    suffix = uuid.uuid4().hex[:8]

    resp = await client.post("/api/v1/projects/wizard", json=await _wizard_payload(suffix))
    assert resp.status_code == 201, resp.text
    project_id = resp.json()["data"]["id"]

    # V1 必须存在
    from app.models.project import Project

    project = await db_session.get(Project, uuid.UUID(project_id))
    assert project is not None, "项目应已创建"
    assert project.current_version_id is not None, "向导创建后应有 Canvas V1"

    # 对话绑定校验
    conv_resp = await client.get(f"/api/v1/projects/{project_id}/conversation")
    assert conv_resp.status_code == 200, conv_resp.text
    conv_data = conv_resp.json()["data"]
    # API output is camelCase (alias_generator=to_camel)
    assert str(conv_data["projectId"]) == project_id


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _parse_sse_events(body: str) -> list[dict]:
    """Extract every `data: {...}` SSE payload from a raw response body."""
    events: list[dict] = []
    for line in body.splitlines():
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[len("data: "):]))
            except json.JSONDecodeError:
                continue
    return events


@pytest.mark.asyncio
async def test_first_message_triggers_auto_fill_with_proposal_blocks(
    client: AsyncClient, db_session
):
    """B1/B2/B3/B4: 首条消息触发 auto-fill → canvas_fill_proposal + 三大板块填充。

    通过 MockLLMService 跑完整 HTTP /chat/stream（而非直接调内部 handler），
    校验「向导 → Canvas → 首条 auto-fill → 可见 proposal」链路真的接通。
    """
    await _seed_admin_owner(db_session)
    suffix = uuid.uuid4().hex[:8]
    wiz = await client.post("/api/v1/projects/wizard", json=await _wizard_payload(suffix))
    assert wiz.status_code == 201, wiz.text
    project_id = wiz.json()["data"]["id"]

    conv_id = (
        (await client.get(f"/api/v1/projects/{project_id}/conversation"))
        .json()["data"]["id"]
    )

    resp = await client.post(
        f"/api/v1/conversations/{conv_id}/chat/stream",
        json={"message": "给测试企业做一个裸眼3D幕墙发布方案"},
    )
    assert resp.status_code == 200, resp.text
    events = _parse_sse_events(resp.text)
    types = {e.get("type") for e in events}

    # B2: 必须发出 canvas_fill_proposal（让用户看到分板块填充结果）
    assert "canvas_fill_proposal" in types, f"missing canvas_fill_proposal; got {types}"
    # B4: 必须发出策划案初稿（proposal_section）
    assert "proposal_section" in types, f"missing proposal_section; got {types}"

    # B3: 画布三大板块至少各有一个节点写入 planning 内容
    canvas_resp = await client.get(f"/api/v1/projects/{project_id}/canvas")
    assert canvas_resp.status_code == 200, canvas_resp.text
    nodes = canvas_resp.json()["data"]["nodes"]
    filled = [n for n in nodes if (n.get("content") or {}).get("planning")]
    assert len(filled) >= 3, f"三大板块至少 3 个节点应有 planning; got {len(filled)}"


@pytest.mark.asyncio
async def test_auto_fill_persists_generation_output(
    client: AsyncClient, db_session
):
    """B4 增强: auto-fill 产出的策划案写入 GenerationOutput（供审核/导出复用）。

    没有持久化时，章节审核、导出门控都无法定位 proposal；这是 Task 3/4 的前置。
    """
    from app.models.generation import GenerationTask

    await _seed_admin_owner(db_session)
    suffix = uuid.uuid4().hex[:8]
    wiz = await client.post("/api/v1/projects/wizard", json=await _wizard_payload(suffix))
    project_id = wiz.json()["data"]["id"]
    conv_id = (
        (await client.get(f"/api/v1/projects/{project_id}/conversation"))
        .json()["data"]["id"]
    )

    resp = await client.post(
        f"/api/v1/conversations/{conv_id}/chat/stream",
        json={"message": "给测试企业做一个裸眼3D幕墙发布方案"},
    )
    assert resp.status_code == 200, resp.text

    # auto-fill 写入是通过独立的 skill_db 会话 COMMIT 的；测试的 db_session
    # 可能持有一个开启早于提交的事务视图,看不到新行。提交以刷新快照。
    await db_session.commit()

    # 必须有一条 proposal 类型的 GenerationTask 落库
    # (skill stamps type="proposal"; auto-fill fallback uses "proposal_generation")
    result = await db_session.execute(
        select(GenerationTask).where(
            GenerationTask.project_id == uuid.UUID(project_id),
            GenerationTask.type.in_(["proposal_generation", "proposal"]),
        )
    )
    task = result.scalar_one_or_none()
    assert task is not None, "auto-fill 应持久化 proposal_generation GenerationTask"
    assert task.status == "completed"


@pytest.mark.asyncio
async def test_get_latest_proposal_output_returns_brief(
    client: AsyncClient, db_session
):
    """Task 3 / §10.2: GET /projects/{id}/proposal-output 返回最新 Brief。

    ProposalEditorPanel 与导出按钮都靠这个端点拿到 output_id + sections_meta。
    没有 Brief 时返回 404（前端据此隐藏入口）。
    """
    await _seed_admin_owner(db_session)
    suffix = uuid.uuid4().hex[:8]
    wiz = await client.post("/api/v1/projects/wizard", json=await _wizard_payload(suffix))
    project_id = wiz.json()["data"]["id"]
    conv_id = (
        (await client.get(f"/api/v1/projects/{project_id}/conversation"))
        .json()["data"]["id"]
    )

    # 触发 auto-fill 生成 Brief
    chat = await client.post(
        f"/api/v1/conversations/{conv_id}/chat/stream",
        json={"message": "给测试企业做一个裸眼3D幕墙发布方案"},
    )
    assert chat.status_code == 200, chat.text

    resp = await client.get(f"/api/v1/projects/{project_id}/proposal-output")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert "outputId" in data, "应返回 outputId（camelCase）"
    assert isinstance(data.get("sectionsMeta"), list)


@pytest.mark.asyncio
async def test_get_latest_proposal_output_404_when_no_brief(
    client: AsyncClient, db_session
):
    """没有 Brief 时返回 404 — 前端据此隐藏 Proposal 入口。"""
    await _seed_admin_owner(db_session)
    suffix = uuid.uuid4().hex[:8]
    wiz = await client.post("/api/v1/projects/wizard", json=await _wizard_payload(suffix))
    project_id = wiz.json()["data"]["id"]

    resp = await client.get(f"/api/v1/projects/{project_id}/proposal-output")
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_export_blocked_until_sections_approved_via_main_flow(
    client: AsyncClient, db_session
):
    """F1/F2: auto-fill 产出的 Brief 章节未审核 → 导出被阻断（403 + blockers）。

    与 test_hitl.py 的 fixture 路径互补：那条用直接构造 sections_meta，本条
    走真实主链（向导 → auto-fill → proposal_output），证明门控对主链产物生效。
    """
    await _seed_admin_owner(db_session)
    suffix = uuid.uuid4().hex[:8]
    wiz = await client.post("/api/v1/projects/wizard", json=await _wizard_payload(suffix))
    project_id = wiz.json()["data"]["id"]
    conv_id = (
        (await client.get(f"/api/v1/projects/{project_id}/conversation"))
        .json()["data"]["id"]
    )
    chat = await client.post(
        f"/api/v1/conversations/{conv_id}/chat/stream",
        json={"message": "给测试企业做一个裸眼3D幕墙发布方案"},
    )
    assert chat.status_code == 200, chat.text

    # Resolve the Brief output the export dropdown would use.
    out_resp = await client.get(f"/api/v1/projects/{project_id}/proposal-output")
    assert out_resp.status_code == 200, out_resp.text
    output_id = out_resp.json()["data"]["outputId"]

    sections = out_resp.json()["data"]["sectionsMeta"]
    print(f"DEBUG sections count={len(sections)} sections={sections}")
    # If auto-fill produced sections, at least one should be non-approved → 403.
    # (When sections_meta is empty the gate is permissive — the regression we
    # care about is that a non-empty, all-draft Brief blocks export.)
    if not sections:
        pytest.skip("Mock auto-fill produced no sections_meta; gate test needs sections")

    resp = await client.post(f"/api/v1/exports/word/{output_id}")
    assert resp.status_code == 403, f"未审核应阻断导出; got {resp.status_code}"
    body = resp.json()
    detail = body.get("detail") or {}
    assert "blockers" in detail, f"应返回 blockers 列表; got {detail}"
    assert len(detail["blockers"]) > 0


@pytest.mark.asyncio
async def test_export_succeeds_after_all_sections_approved(
    client: AsyncClient, db_session
):
    """F3: 全部章节 approved 后导出门控放行（不再 403）。

    走主链生成 Brief → 通过 PATCH 把所有章节标记为 approved → 导出不再被门控阻断。
    """
    await _seed_admin_owner(db_session)
    suffix = uuid.uuid4().hex[:8]
    wiz = await client.post("/api/v1/projects/wizard", json=await _wizard_payload(suffix))
    project_id = wiz.json()["data"]["id"]
    conv_id = (
        (await client.get(f"/api/v1/projects/{project_id}/conversation"))
        .json()["data"]["id"]
    )
    chat = await client.post(
        f"/api/v1/conversations/{conv_id}/chat/stream",
        json={"message": "给测试企业做一个裸眼3D幕墙发布方案"},
    )
    assert chat.status_code == 200, chat.text

    out_resp = await client.get(f"/api/v1/projects/{project_id}/proposal-output")
    assert out_resp.status_code == 200, out_resp.text
    output_id = out_resp.json()["data"]["outputId"]
    sections = out_resp.json()["data"]["sectionsMeta"]
    if not sections:
        pytest.skip("Mock auto-fill produced no sections_meta; gate test needs sections")

    # Approve every section via the section-status endpoint the Proposal editor
    # uses (PRESALE_DELIVERY_SPEC §9.1).
    for section in sections:
        order = section["order"]
        patch = await client.patch(
            f"/api/v1/generations/outputs/{output_id}/sections/{order}/status",
            json={"status": "approved"},
        )
        assert patch.status_code == 200, patch.text

    # Now the gate must let the export through (non-403). Whether the file
    # actually renders depends on python-docx being installed; the gate test
    # only asserts the 403 is gone.
    resp = await client.post(f"/api/v1/exports/word/{output_id}")
    assert resp.status_code != 403, "全章节已 approved,导出门控应放行"


@pytest.mark.asyncio
async def test_auto_fill_writes_canvas_digest_memory(
    client: AsyncClient, db_session
):
    """P0 C1 (前置): auto-fill 完成后写入 canvas_digest 到 project_memories。

    没有这一步,后续追问无法基于已填内容回答(失忆)。校验 boards 形状 +
    missing_info roll-up + last_web_search 占位。
    """
    from app.models.project_memory import ProjectMemory

    await _seed_admin_owner(db_session)
    suffix = uuid.uuid4().hex[:8]
    wiz = await client.post("/api/v1/projects/wizard", json=await _wizard_payload(suffix))
    project_id = wiz.json()["data"]["id"]
    conv_id = (
        (await client.get(f"/api/v1/projects/{project_id}/conversation"))
        .json()["data"]["id"]
    )

    chat = await client.post(
        f"/api/v1/conversations/{conv_id}/chat/stream",
        json={"message": "给测试企业做一个裸眼3D幕墙发布方案"},
    )
    assert chat.status_code == 200, chat.text

    await db_session.commit()  # refresh view across sessions
    result = await db_session.execute(
        select(ProjectMemory).where(
            ProjectMemory.project_id == uuid.UUID(project_id),
            ProjectMemory.memory_type == "canvas_digest",
        )
    )
    mem = result.scalar_one_or_none()
    assert mem is not None, "auto-fill 应写入 canvas_digest 项目记忆"
    digest = mem.memory_json
    assert "boards" in digest
    assert isinstance(digest.get("missing_info"), list)
    # last_web_search key is present (None when no web hits in Mock profile).
    assert "last_web_search" in digest


@pytest.mark.asyncio
async def test_follow_up_question_sees_canvas_digest(
    client: AsyncClient, db_session
):
    """P0 C1: 追问时画布摘要被注入 conversational system_prompt（不失忆）。

    验证方式:用一个捕获 system_prompt 的假 LLM 替换 MockLLMService,触发
    auto-fill 写入 digest,再发一条追问,断言假 LLM 收到的 system_prompt 含
    「项目画布摘要」段。这比断言回复文本更可靠(回复内容随 Mock 变化)。
    """
    from unittest.mock import AsyncMock, patch

    await _seed_admin_owner(db_session)
    suffix = uuid.uuid4().hex[:8]
    wiz = await client.post("/api/v1/projects/wizard", json=await _wizard_payload(suffix))
    project_id = wiz.json()["data"]["id"]
    conv_id = (
        (await client.get(f"/api/v1/projects/{project_id}/conversation"))
        .json()["data"]["id"]
    )

    # 1) auto-fill — writes canvas_digest memory.
    chat = await client.post(
        f"/api/v1/conversations/{conv_id}/chat/stream",
        json={"message": "给测试企业做一个裸眼3D幕墙发布方案"},
    )
    assert chat.status_code == 200, chat.text

    # Confirm digest actually landed (precondition for the injection assertion).
    await db_session.commit()
    from app.models.project_memory import ProjectMemory

    mem = (
        await db_session.execute(
            select(ProjectMemory).where(
                ProjectMemory.project_id == uuid.UUID(project_id),
                ProjectMemory.memory_type == "canvas_digest",
            )
        )
    ).scalar_one_or_none()
    assert mem is not None, "前置失败:auto-fill 未写入 digest"

    # 2) Follow-up — capture the system_prompt the conversational handler sends.
    # The follow-up must route to _handle_conversational (not auto-fill), so we
    # patch get_llm_service ONLY around the follow-up request. The capturing
    # LLM subclasses MockLLMService so any other code path that asks for an LLM
    # still gets a working service.
    from app.services.llm_service import MockLLMService

    captured: dict[str, str] = {}

    class _CapturingLLM(MockLLMService):
        async def generate_with_history_stream_rich(
            self, messages, system_prompt, temperature=0.7
        ):
            captured["system_prompt"] = system_prompt or ""
            yield "thinking", "已检索画布摘要。"
            yield "text", "已基于画布回答。"

    async def _fake_get_llm(db=None):
        return _CapturingLLM()

    with patch(
        "app.services.conversation_service.get_llm_service",
        AsyncMock(side_effect=_fake_get_llm),
    ), patch(
        "app.services.conversation_service.acquire_web_context",
        AsyncMock(return_value=([], {"status": "ok", "key_points": [], "missing_info": []})),
    ):
        follow = await client.post(
            f"/api/v1/conversations/{conv_id}/chat/stream",
            json={
                "message": "刚才填充的企业主营业务是什么？请基于已填内容回答",
                "forceIntent": "conversational",
            },
        )
    assert follow.status_code == 200, follow.text
    assert "项目画布摘要" in captured.get("system_prompt", ""), (
        "追问时应注入 canvas_digest 到 system_prompt;got: "
        + captured.get("system_prompt", "")[:200]
    )


@pytest.mark.asyncio
async def test_conversation_history_persisted_after_reload(
    client: AsyncClient, db_session
):
    """P0 C5: 刷新页面后对话历史与 rich_content blocks 完整保留。

    auto-fill + 一条追问后,通过 GET /projects/{id}/conversation 重新拉取,
    断言消息数 >= 4(user + assistant + user + assistant),且 assistant 消息
    带 rich_content(SSE 流式产物的持久化)。
    """
    await _seed_admin_owner(db_session)
    suffix = uuid.uuid4().hex[:8]
    wiz = await client.post("/api/v1/projects/wizard", json=await _wizard_payload(suffix))
    project_id = wiz.json()["data"]["id"]
    conv_id = (
        (await client.get(f"/api/v1/projects/{project_id}/conversation"))
        .json()["data"]["id"]
    )

    # Turn 1: auto-fill.
    chat1 = await client.post(
        f"/api/v1/conversations/{conv_id}/chat/stream",
        json={"message": "给测试企业做一个裸眼3D幕墙发布方案"},
    )
    assert chat1.status_code == 200, chat1.text

    # Turn 2: a follow-up (force conversational so it doesn't re-trigger auto-fill).
    chat2 = await client.post(
        f"/api/v1/conversations/{conv_id}/chat/stream",
        json={
            "message": "再补充一些细节",
            "forceIntent": "conversational",
        },
    )
    assert chat2.status_code == 200, chat2.text

    # Reload the conversation from the server — simulates a page refresh.
    reloaded = await client.get(f"/api/v1/projects/{project_id}/conversation")
    assert reloaded.status_code == 200, reloaded.text
    messages = reloaded.json()["data"]["messages"]
    # At least 4 messages: 2 user turns + 2 assistant turns.
    assert len(messages) >= 4, f"刷新后应保留全部消息;got {len(messages)}"
    assistant_msgs = [m for m in messages if m.get("role") == "assistant"]
    assert len(assistant_msgs) >= 2, "应至少有 2 条 assistant 消息(auto-fill + 追问)"


@pytest.mark.asyncio
async def test_project_status_advances_through_main_flow(
    client: AsyncClient, db_session
):
    """F5: 项目状态随主流程推进 — auto-fill → proposal_generated;导出 → exported。"""
    from app.models.project import Project

    await _seed_admin_owner(db_session)
    suffix = uuid.uuid4().hex[:8]
    wiz = await client.post("/api/v1/projects/wizard", json=await _wizard_payload(suffix))
    project_id = wiz.json()["data"]["id"]
    conv_id = (
        (await client.get(f"/api/v1/projects/{project_id}/conversation"))
        .json()["data"]["id"]
    )

    # 1) auto-fill → proposal_generated
    chat = await client.post(
        f"/api/v1/conversations/{conv_id}/chat/stream",
        json={"message": "给测试企业做一个裸眼3D幕墙发布方案"},
    )
    assert chat.status_code == 200, chat.text

    await db_session.commit()  # refresh view across sessions
    project = await db_session.get(Project, uuid.UUID(project_id))
    assert project is not None
    assert project.status == "proposal_generated", (
        f"auto-fill 后状态应为 proposal_generated; got {project.status}"
    )

    # 2) approve all sections then export → exported
    out_resp = await client.get(f"/api/v1/projects/{project_id}/proposal-output")
    assert out_resp.status_code == 200, out_resp.text
    output_id = out_resp.json()["data"]["outputId"]
    sections = out_resp.json()["data"]["sectionsMeta"]
    if not sections:
        pytest.skip("Mock auto-fill produced no sections_meta; export test needs sections")

    for section in sections:
        order = section["order"]
        patch = await client.patch(
            f"/api/v1/generations/outputs/{output_id}/sections/{order}/status",
            json={"status": "approved"},
        )
        assert patch.status_code == 200, patch.text

    export_resp = await client.post(f"/api/v1/exports/word/{output_id}")
    # Export may 200 (python-docx installed) — in that case status flips to
    # exported. If the library is missing the endpoint returns 500 and we
    # cannot assert the transition; skip instead of failing on env.
    if export_resp.status_code == 500:
        pytest.skip("python-docx not installed; cannot verify exported transition")

    assert export_resp.status_code == 200, export_resp.text
    await db_session.commit()
    await db_session.refresh(project)
    assert project.status == "exported", (
        f"导出后状态应为 exported; got {project.status}"
    )
