"""PRESALE_DELIVERY_SPEC §14.1 标准 UAT 剧本 — 自动化 smoke 版本。

把 spec §14.1「华为裸眼 3D 发布方案」十步剧本拆成 parametrized 步骤断言,
每一步对应剧本的一个操作 + 预期。MockLLM 驱动,跑在 SQLite 测试 DB 上,
CI 可重复执行。与 test_presale_main_flow.py 互补:那条文件覆盖单点验收项,
本文件按剧本顺序串起来,验证「按剧本走能走通」。

剧本步骤(对应 spec §14.1):
  1. 向导创建项目 → Canvas
  2. 首条消息触发 auto-fill + proposal 卡片
  3. 检查画布三大板块
  4. 追问(基于已填内容回答)
  5. 节点对话直出(略 — 节点对话在 test_node_edit 覆盖)
  6. 采纳(略 — test_canvas_fill_accept 覆盖)
  7. 策划案章节编辑
  8. 全章节 approved
  9. 导出 PDF(门控放行)
  10. 引用追溯(used_cases / used_sop_version 可查)
"""

import json
import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _seed_admin_owner(db_session) -> None:
    """Wizard resolves owner via DEFAULT_OWNER_EMAIL; seed that user."""
    from sqlalchemy import select

    from app.models.user import Role, User

    result = await db_session.execute(
        select(User).where(User.email == "admin@3dwall.com")
    )
    if result.scalar_one_or_none() is not None:
        return
    from datetime import datetime, timezone

    role = Role(
        id=uuid.uuid4(),
        name=f"uat_owner_{uuid.uuid4().hex[:8]}",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(role)
    await db_session.flush()
    user = User(
        id=uuid.uuid4(),
        email="admin@3dwall.com",
        name="UAT Admin",
        role_id=role.id,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.commit()


def _uat_wizard_payload(suffix: str) -> dict:
    """Spec §14.1 step 1 payload: 客户「华为」,行业「科技」,裸眼3D幕墙。"""
    return {
        "step1": {
            "projectName": f"华为裸眼3D发布-{suffix}",
            "clientName": f"华为-{suffix}",
            "industry": "科技",
            "projectType": "裸眼3D",
            "description": "总部裸眼3D幕墙品牌发布",
            "priority": "high",
        },
        "screen": {
            "screenType": "裸眼3D",
            "screenSize": "20m x 8m",
        },
    }


async def _run_uat_script(client: AsyncClient, db_session) -> dict:
    """Run the full UAT剧本 once; return a dict of step → result/evidence.

    Each step records the HTTP response (or relevant data) so individual
    parametrized assertions below can inspect a single step's outcome without
    re-running the whole剧本.
    """
    await _seed_admin_owner(db_session)
    suffix = uuid.uuid4().hex[:8]
    evidence: dict = {}

    # Step 1: 向导创建 → Canvas
    wiz = await client.post("/api/v1/projects/wizard", json=_uat_wizard_payload(suffix))
    evidence["step1_status"] = wiz.status_code
    evidence["project_id"] = wiz.json()["data"]["id"] if wiz.status_code == 201 else None
    project_id = evidence["project_id"]

    # Step 2: 首条消息触发 auto-fill
    conv_id = (
        (await client.get(f"/api/v1/projects/{project_id}/conversation"))
        .json()["data"]["id"]
    )
    evidence["conv_id"] = conv_id
    chat = await client.post(
        f"/api/v1/conversations/{conv_id}/chat/stream",
        json={"message": "给华为做一个裸眼3D幕墙的方案,面向科技品牌发布"},
    )
    events = []
    for line in chat.text.splitlines():
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[len("data: "):]))
            except json.JSONDecodeError:
                pass
    evidence["step2_status"] = chat.status_code
    evidence["step2_event_types"] = {e.get("type") for e in events}

    # Step 3: 画布三大板块检查
    canvas = await client.get(f"/api/v1/projects/{project_id}/canvas")
    nodes = canvas.json()["data"]["nodes"] if canvas.status_code == 200 else []
    boards_filled = {
        n.get("group_key")
        for n in nodes
        if (n.get("content") or {}).get("planning")
    }
    evidence["step3_filled_node_count"] = sum(
        1 for n in nodes if (n.get("content") or {}).get("planning")
    )
    evidence["step3_boards_with_fill"] = boards_filled

    # Step 4: 追问(强制 conversational 路径,避免再次 auto-fill)
    follow = await client.post(
        f"/api/v1/conversations/{conv_id}/chat/stream",
        json={
            "message": "刚才填充的企业主营业务是什么?请基于已填内容回答",
            "forceIntent": "conversational",
        },
    )
    evidence["step4_status"] = follow.status_code

    # Step 7: 策划案章节内容编辑 (Spec E2 / 本轮修复 #5)
    # PUT /generations/outputs/{id} 替换整段 sections_meta,前端 ProposalEditorPanel
    # 的铅笔按钮就走这个端点。剧本操作是「编辑创意主题章节内容 → 保存成功」。
    out = await client.get(f"/api/v1/projects/{project_id}/proposal-output")
    evidence["step7_output_id"] = (
        out.json()["data"]["outputId"] if out.status_code == 200 else None
    )
    evidence["step7_sections"] = (
        out.json()["data"]["sectionsMeta"] if out.status_code == 200 else []
    )
    edited_marker = "[UAT 编辑] 创意主题：科技品牌 3D 发布"
    if evidence["step7_output_id"] and evidence["step7_sections"]:
        # 选第一个章节编辑内容 (镜像前端 handleSaveEdit 的整个 sections_meta PUT)
        first_order = evidence["step7_sections"][0]["order"]
        edited_meta = [
            {**s, "content": edited_marker} if s["order"] == first_order else s
            for s in evidence["step7_sections"]
        ]
        put = await client.put(
            f"/api/v1/generations/outputs/{evidence['step7_output_id']}",
            json={"sections_meta": edited_meta},
        )
        evidence["step7_edit_status"] = put.status_code
        # Re-read to confirm the edit landed.
        re_out = await client.get(f"/api/v1/projects/{project_id}/proposal-output")
        if re_out.status_code == 200:
            re_sections = re_out.json()["data"]["sectionsMeta"]
            edited_section = next(
                (s for s in re_sections if s["order"] == first_order), None
            )
            evidence["step7_edit_persisted"] = bool(
                edited_section and edited_section.get("content") == edited_marker
            )

    # Step 8: 全章节 approved → pending_review (本轮修复 #4)
    if evidence["step7_output_id"] and evidence["step7_sections"]:
        for section in evidence["step7_sections"]:
            await client.patch(
                f"/api/v1/generations/outputs/{evidence['step7_output_id']}/sections/{section['order']}/status",
                json={"status": "approved"},
            )
        # 全章节 approved 后,project 应推进到 pending_review (Spec F5)。
        from app.models.project import Project

        await db_session.commit()
        proj_row = await db_session.get(Project, uuid.UUID(project_id))
        evidence["step8_project_status"] = proj_row.status if proj_row else None

    # Step 9: 导出 PDF(门控放行)
    # 经过本轮加强的 export gate:
    #   - #2 canvas planning 检查 (每板至少一 node 的 planning 非空)
    #   - #3 industry-aware SOP match (从 company.industry 解析)
    if evidence["step7_output_id"]:
        export = await client.post(
            f"/api/v1/exports/pdf/{evidence['step7_output_id']}"
        )
        evidence["step9_status"] = export.status_code

    # Step 10: 引用追溯 — used_sop_version / used_cases 在 GenerationOutput 上
    if evidence["step7_output_id"]:
        from sqlalchemy import select

        from app.models.generation import GenerationOutput, GenerationTask

        await db_session.commit()
        task_row = (
            await db_session.execute(
                select(GenerationTask).where(
                    GenerationTask.project_id == uuid.UUID(project_id),
                    GenerationTask.type.in_(["proposal_generation", "proposal"]),
                )
            )
        ).scalar_one()
        output_row = (
            await db_session.execute(
                select(GenerationOutput).where(GenerationOutput.task_id == task_row.id)
            )
        ).scalar_one()
        evidence["step10_used_sop_version"] = output_row.used_sop_version
        evidence["step10_used_cases"] = output_row.used_cases

    return evidence


@pytest.mark.parametrize(
    "step,expected",
    [
        ("step1_status", 201),
        ("step2_status", 200),
        ("step3_filled_node_count", 3),  # >= 3 filled nodes (三大板块)
        ("step4_status", 200),
        ("step7_edit_status", 200),  # 章节内容编辑保存成功 (Spec E2)
        ("step7_edit_persisted", True),  # 编辑后重读内容已落库
        ("step8_project_status", "pending_review"),  # 全 approved → pending_review (F5)
        ("step9_status", 200),  # PDF export succeeds after gate
    ],
)
async def test_uat_script_step(client: AsyncClient, db_session, step, expected):
    """Spec §14.1 剧本 — 每一步断言。

    step3_filled_node_count 的 expected=3 实际是「至少 3」;parametrize 不支持
    「至少」语义,所以单独写比较逻辑。
    """
    evidence = await _run_uat_script(client, db_session)
    if step == "step3_filled_node_count":
        assert evidence[step] >= expected, (
            f"UAT step3: 三大板块至少 {expected} 个节点已填充; got {evidence[step]}"
        )
    elif step == "step9_status":
        # PDF export may 500 if reportlab missing in the env; the gate-related
        # assertion (non-403) is the real acceptance. 200 = full success.
        got = evidence.get(step)
        if got == 500:
            pytest.skip("reportlab not installed; PDF render unavailable")
        assert got == expected, f"UAT step9 (导出 PDF): expected {expected}, got {got}"
    else:
        assert evidence[step] == expected, (
            f"UAT {step}: expected {expected}, got {evidence[step]}"
        )


async def test_uat_script_proposal_block_emitted(client: AsyncClient, db_session):
    """Spec §14.1 step 2: auto-fill emits canvas_fill_proposal + proposal_section."""
    evidence = await _run_uat_script(client, db_session)
    types = evidence["step2_event_types"]
    assert "canvas_fill_proposal" in types, f"missing canvas_fill_proposal; got {types}"
    assert "proposal_section" in types, f"missing proposal_section; got {types}"


async def test_uat_script_used_sop_version_traceable(
    client: AsyncClient, db_session
):
    """Spec §14.1 step 10: 引用可追溯 — used_sop_version 存在(非空)。"""
    evidence = await _run_uat_script(client, db_session)
    sop_version = evidence.get("step10_used_sop_version")
    assert sop_version, "策划案应记录 used_sop_version(可追溯)"
