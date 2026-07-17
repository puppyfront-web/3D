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
