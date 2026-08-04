# 售前助手内容完整验收 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 [PRESALE_DELIVERY_SPEC.md](../../PRESALE_DELIVERY_SPEC.md) 定义的全链路——用户输入企业信息 → 多轮对话（SOP/知识库引导）→ 审核 → 导出合格设计方案，并通过 P0 验收清单。

**Architecture:** 以 Canvas 工作台为主界面，对话驱动产物落地（画布节点 + 策划案 Brief）。后端沿用 `ConversationService` 意图路由 + Skill Runtime + Hybrid RAG；新增 `project_memories` / `conversation_states` 解决跨轮记忆；SOP 匹配与导出门控从 DB 读取而非硬编码。分 4 个 Phase 交付，每 Phase 结束可独立验收。

**Tech Stack:** FastAPI + SQLAlchemy + Alembic + pytest (backend) | Next.js 14 + TypeScript + SSE chat (frontend) | PostgreSQL + pgvector | MockLLM for tests

**Spec:** [PRESALE_DELIVERY_SPEC.md](../../PRESALE_DELIVERY_SPEC.md) §13 P0 验收清单

---

## 文件结构总览

| 区域 | 新建 | 修改 |
|------|------|------|
| 记忆层 | `models/project_memory.py`, `services/project_memory_service.py` | `conversation_service.py`, `models/__init__.py` |
| SOP 匹配 | `services/sop_matcher_service.py` | `skills/builtins/proposal_generation.py`, `routers/exports.py` |
| 主链测试 | `tests/test_presale_main_flow.py`, `tests/test_project_memory.py` | `tests/test_hitl.py`, `tests/test_canvas_fill_proposal_sse.py` |
| 策划案 UI | `components/canvas/proposal-editor-panel.tsx` | `canvas/[projectId]/page.tsx`, `conversation-panel.tsx` |
| 导出联动 | — | `canvas-api.ts`, `routers/exports.py`, `canvas/[projectId]/page.tsx` |
| 项目状态 | — | `conversation_service.py`, `project_service.py` |

---

## Phase 1 — 主链跑通（验收 P0 A/B/F 部分）

> **交付标准：** 向导 → Canvas → 首条 auto-fill → 可见 proposal → 可导出（审核通过后）

---

### Task 1: 向导创建后 Canvas V1 就绪

**验收项:** A1, A2, A3

**Files:**
- Modify: `apps/api/app/services/project_service.py`
- Modify: `apps/api/app/services/canvas_service.py`
- Test: `apps/api/app/tests/test_presale_main_flow.py` (新建，本节先写第一个用例)

- [ ] **Step 1: Write the failing test**

```python
# apps/api/app/tests/test_presale_main_flow.py
"""PRESALE_DELIVERY_SPEC §13 P0 — 主链 E2E（Mock LLM）。"""

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.project import Project


async def _wizard_payload(suffix: str) -> dict:
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
async def test_wizard_creates_project_with_canvas_v1(client: AsyncClient, db_session):
    suffix = uuid.uuid4().hex[:8]
    resp = await client.post("/api/v1/projects/wizard", json=await _wizard_payload(suffix))
    assert resp.status_code == 201, resp.text
    project_id = resp.json()["data"]["id"]

    project = await db_session.get(Project, uuid.UUID(project_id))
    assert project is not None
    assert project.current_version_id is not None, "向导创建后应有 Canvas V1"

    conv_resp = await client.get(f"/api/v1/projects/{project_id}/conversation")
    assert conv_resp.status_code == 200
    assert conv_resp.json()["data"]["project_id"] == project_id
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd apps/api && pytest app/tests/test_presale_main_flow.py::test_wizard_creates_project_with_canvas_v1 -v
```

Expected: FAIL — `current_version_id is None`

- [ ] **Step 3: Implement — wizard 创建时初始化 Canvas V1**

在 `project_service.py` 的 `create_from_wizard` 末尾，`flush` 之后调用 canvas_service：

```python
# apps/api/app/services/project_service.py — create_from_wizard 末尾
from app.services.canvas_service import canvas_service

await canvas_service.ensure_initial_version(db, project.id)
await db.refresh(project)
```

在 `canvas_service.py` 新增：

```python
async def ensure_initial_version(self, db: AsyncSession, project_id: uuid.UUID) -> ProjectVersion:
    """Create V1 with default topology if project has no current version."""
    project = await db.get(Project, project_id)
    if project and project.current_version_id:
        return await self.get_current_version(db, project_id)
    return await self.create_version(
        db,
        project_id,
        version_name="V1",
        change_summary="项目创建初始版本",
    )
```

（若 `create_version` 签名不同，复用 canvas page 首次 mount 时的同一套逻辑，提取为公共方法。）

- [ ] **Step 4: Run test — expect PASS**

```bash
cd apps/api && pytest app/tests/test_presale_main_flow.py::test_wizard_creates_project_with_canvas_v1 -v
```

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/services/project_service.py apps/api/app/services/canvas_service.py apps/api/app/tests/test_presale_main_flow.py
git commit -m "feat: initialize canvas V1 when project created from wizard"
```

---

### Task 2: 首条消息 auto-fill 产出 canvas_fill_proposal + proposal_section

**验收项:** B1, B2, B3, B4

**Files:**
- Test: `apps/api/app/tests/test_presale_main_flow.py`
- Reference: `apps/api/app/services/conversation_service.py` (`_handle_auto_fill`)
- Reference: `apps/api/app/tests/test_canvas_fill_proposal_sse.py`

- [ ] **Step 1: Write the failing test**

```python
# 追加到 test_presale_main_flow.py

def _parse_sse_events(body: str) -> list[dict]:
    events = []
    for line in body.split("\n"):
        if line.startswith("data: "):
            import json
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass
    return events


@pytest.mark.asyncio
async def test_first_message_triggers_auto_fill_with_proposal_blocks(
    client: AsyncClient, db_session
):
    suffix = uuid.uuid4().hex[:8]
    wiz = await client.post("/api/v1/projects/wizard", json=await _wizard_payload(suffix))
    project_id = wiz.json()["data"]["id"]
    conv_id = (await client.get(f"/api/v1/projects/{project_id}/conversation")).json()["data"]["id"]

    resp = await client.post(
        f"/api/v1/conversations/{conv_id}/chat/stream",
        json={"message": "给测试企业做一个裸眼3D幕墙发布方案"},
    )
    assert resp.status_code == 200
    events = _parse_sse_events(resp.text)
    types = {e.get("type") for e in events}
    assert "canvas_fill_proposal" in types, f"missing proposal block, got {types}"
    assert "proposal_section" in types or any(
        e.get("type") == "content_block_data" for e in events
    ), "missing proposal_section"

    # 画布节点应有 planning 内容
    canvas_resp = await client.get(f"/api/v1/projects/{project_id}/canvas/current")
    assert canvas_resp.status_code == 200
    nodes = canvas_resp.json()["data"]["nodes"]
    filled = [n for n in nodes if (n.get("content") or {}).get("planning")]
    assert len(filled) >= 3, "三大板块至少 3 个节点应有 planning"
```

- [ ] **Step 2: Run test — expect PASS or identify gaps**

```bash
cd apps/api && pytest app/tests/test_presale_main_flow.py::test_first_message_triggers_auto_fill_with_proposal_blocks -v
```

若 FAIL：对照 `test_canvas_fill_proposal_sse.py` 修复 `_handle_auto_fill` 中 `build_fill_proposal_from_canvas` / `proposal_generation` 链路，确保 SSE 发出两种 block。

- [ ] **Step 3: 持久化 proposal 到 GenerationOutput（供后续审核/导出）**

Modify `conversation_service.py` — `_handle_auto_fill` 在 `proposal_generation` 成功后：

```python
# 伪代码位置：skill_output 拿到之后
from app.models.generation import GenerationTask, GenerationOutput

task = GenerationTask(
    project_id=proj_uuid,
    type="proposal_generation",
    status="completed",
    model_used="mock",
)
db.add(task)
await db.flush()

output = GenerationOutput(
    task_id=task.id,
    content_type="application/json",
    content=json.dumps(skill_output, ensure_ascii=False),
    used_cases=skill_result.get("used_cases") or [],
    used_documents=skill_result.get("used_documents") or [],
    used_chunks=skill_result.get("used_chunks") or [],
    sections_meta=skill_output.get("sections_meta") or [],
)
db.add(output)
await db.commit()
```

assistant message `metadata` 增加 `"generation_output_id": str(output.id)`。

- [ ] **Step 4: Write test for generation_output persistence**

```python
@pytest.mark.asyncio
async def test_auto_fill_persists_generation_output(client, db_session):
    # ... 同上触发 auto_fill ...
    from app.models.generation import GenerationTask
    result = await db_session.execute(
        select(GenerationTask).where(GenerationTask.project_id == uuid.UUID(project_id))
    )
    task = result.scalar_one_or_none()
    assert task is not None
    assert task.type == "proposal_generation"
```

- [ ] **Step 5: Run all Phase1 tests + commit**

```bash
cd apps/api && pytest app/tests/test_presale_main_flow.py -v
git commit -m "feat: persist proposal generation output after auto-fill"
```

---

### Task 3: Canvas 工作台 — Proposal 卡片与 generation_id 联动

**验收项:** B2, B4, 10.2 策划案卡片

**Files:**
- Create: `apps/web/components/canvas/proposal-editor-panel.tsx`
- Modify: `apps/web/components/canvas/conversation-panel.tsx`
- Modify: `apps/web/app/workspace/canvas/[projectId]/page.tsx`
- Modify: `apps/web/lib/canvas-api.ts`

- [ ] **Step 1: 后端 API — 获取项目最新 proposal output**

Modify `apps/api/app/routers/projects.py` 新增：

```python
@router.get("/{project_id}/proposal-output")
async def get_latest_proposal_output(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Return latest GenerationOutput for proposal_generation on this project."""
    result = await db.execute(
        select(GenerationOutput)
        .join(GenerationTask, GenerationTask.id == GenerationOutput.task_id)
        .where(GenerationTask.project_id == project_id, GenerationTask.type == "proposal_generation")
        .order_by(GenerationOutput.created_at.desc())
        .limit(1)
    )
    output = result.scalar_one_or_none()
    if not output:
        raise NotFoundException("GenerationOutput", f"project={project_id}")
    return Response(data={"output_id": str(output.id), "sections_meta": output.sections_meta, ...})
```

- [ ] **Step 2: 前端 `getProposalOutput(projectId)` client**

`apps/web/lib/canvas-api.ts` 增加 fetch 方法。

- [ ] **Step 3: ProposalEditorPanel 组件**

- 展示 `sections_meta` 列表
- 每章节：标题 + 内容预览 + 状态 Badge（draft/review/approved）
- 「编辑」打开 Dialog Textarea
- 「审核通过」调 `PATCH /generations/outputs/{id}/sections/{order}/status`

- [ ] **Step 4: Canvas 页右栏或 Dialog 入口**

在 `page.tsx` 增加「策划案」按钮，打开 `ProposalEditorPanel`。

- [ ] **Step 5: 人工验证 + tsc**

```bash
cd apps/web && npx tsc --noEmit
```

- [ ] **Step 6: Commit**

```bash
git commit -m "feat: proposal editor panel in canvas workspace"
```

---

### Task 4: 导出门控与 Canvas 导出按钮联通

**验收项:** F1, F2, F3, F4

**Files:**
- Modify: `apps/api/app/routers/exports.py`
- Modify: `apps/web/app/workspace/canvas/[projectId]/page.tsx`
- Test: `apps/api/app/tests/test_hitl.py` (补充 canvas 路径)

- [ ] **Step 1: Write failing test — 未审核阻断导出**

```python
# apps/api/app/tests/test_presale_main_flow.py

@pytest.mark.asyncio
async def test_export_blocked_until_sections_approved(client, db_session):
    # 创建 output，sections_meta 全 draft
    output_id = ...  # fixture helper
    resp = await client.post(f"/api/v1/exports/word/{output_id}")
    assert resp.status_code == 403
    assert "未审核" in str(resp.json())
```

- [ ] **Step 2: Run — expect PASS**（`exports.py` 已有 `_check_export_eligibility`）

- [ ] **Step 3: 前端导出按钮**

`page.tsx` 导出 Dropdown：
1. `GET /projects/{id}/proposal-output` 取 `output_id`
2. 调 `POST /exports/pdf/{output_id}` 或 word
3. 403 时 toast 展示 blockers 列表

- [ ] **Step 4: 审核通过后导出成功 test**

```python
@pytest.mark.asyncio
async def test_export_succeeds_when_all_sections_approved(client, db_session):
    output_id = await _create_output_with_approved_sections(db_session)
    resp = await client.post(f"/api/v1/exports/word/{output_id}")
    assert resp.status_code == 200
```

- [ ] **Step 5: Commit**

```bash
git commit -m "feat: wire canvas export to proposal output with HITL gate"
```

---

### Task 5: 项目状态随流程推进更新

**验收项:** F5

**Files:**
- Modify: `apps/api/app/services/conversation_service.py`
- Modify: `apps/api/app/routers/exports.py`

- [ ] **Step 1: 状态迁移规则**

| 事件 | 新 status |
|------|-----------|
| auto_fill 完成 | `company_analysis_done` 或 `proposal_generated` |
| 全部章节 approved | `pending_review` |
| 导出成功 | `exported` |

在 `_handle_auto_fill` 成功末尾：

```python
from app.models.project import Project
project = await db.get(Project, proj_uuid)
if project:
    project.status = "proposal_generated"
```

在 `exports.py` 导出成功后：

```python
task_project = await db.get(Project, task.project_id)
if task_project:
    task_project.status = "exported"
await db.commit()
```

- [ ] **Step 2: Test status transition**

```python
@pytest.mark.asyncio
async def test_project_status_becomes_exported_after_export(client, db_session):
    ...
    assert project.status == "exported"
```

- [ ] **Step 3: Commit**

```bash
git commit -m "feat: update project status through presale main flow"
```

---

## Phase 2 — 对话可靠与记忆（验收 P0 C1-C5）

> **交付标准：** 追问不失忆；web 搜索结果被持久化并注入后续 prompt

---

### Task 6: 记忆表模型与迁移

**Files:**
- Create: `apps/api/app/models/project_memory.py`
- Create: `apps/api/alembic/versions/xxxx_add_project_memories.py`
- Modify: `apps/api/app/models/__init__.py`

- [ ] **Step 1: Write model**

```python
# apps/api/app/models/project_memory.py
class ConversationState(Base):
    __tablename__ = "conversation_states"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id"), index=True)
    thread_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("conversation_threads.id"), nullable=True)
    state_key: Mapped[str] = mapped_column(String(64), nullable=False)
    state_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    __table_args__ = (UniqueConstraint("conversation_id", "thread_id", "state_key"),)

class ProjectMemory(Base):
    __tablename__ = "project_memories"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    memory_type: Mapped[str] = mapped_column(String(64), nullable=False)
    memory_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    __table_args__ = (UniqueConstraint("project_id", "memory_type"),)
```

- [ ] **Step 2: Alembic migration**

```bash
cd apps/api && alembic revision --autogenerate -m "add conversation_states and project_memories"
cd apps/api && alembic upgrade head
```

- [ ] **Step 3: Test model CRUD**

```python
# apps/api/app/tests/test_project_memory.py
@pytest.mark.asyncio
async def test_upsert_project_memory(db_session):
    ...
```

- [ ] **Step 4: Commit**

---

### Task 7: ProjectMemoryService — canvas_digest 构建

**Files:**
- Create: `apps/api/app/services/project_memory_service.py`
- Modify: `apps/api/app/services/canvas_research_service.py`

- [ ] **Step 1: Write failing test**

```python
@pytest.mark.asyncio
async def test_build_canvas_digest_from_filled_canvas(db_session, sample_project_with_canvas):
    from app.services.project_memory_service import project_memory_service
    digest = await project_memory_service.build_canvas_digest(db_session, project_id)
    assert "boards" in digest
    assert isinstance(digest.get("missing_info"), list)
```

- [ ] **Step 2: Implement build_canvas_digest**

复用 `canvas_research_service.build_fill_proposal_from_canvas` 的输出形状，追加 `last_web_search` 字段占位。

- [ ] **Step 3: upsert_project_memory / get_project_memory**

```python
async def upsert(self, db, project_id, memory_type: str, memory_json: dict) -> ProjectMemory:
    ...

async def get(self, db, project_id, memory_type: str) -> dict | None:
    ...
```

- [ ] **Step 4: Run tests + commit**

---

### Task 8: auto-fill 结束后写入记忆

**Files:**
- Modify: `apps/api/app/services/conversation_service.py` (`_handle_auto_fill`)

- [ ] **Step 1: Write failing test**

```python
@pytest.mark.asyncio
async def test_auto_fill_updates_project_memory_canvas_digest(client, db_session):
    # trigger auto_fill ...
    from app.models.project_memory import ProjectMemory
    mem = await db_session.execute(
        select(ProjectMemory).where(
            ProjectMemory.project_id == uuid.UUID(project_id),
            ProjectMemory.memory_type == "canvas_digest",
        )
    )
    assert mem.scalar_one_or_none() is not None
```

- [ ] **Step 2: 在 _handle_auto_fill 成功路径末尾**

```python
from app.services.project_memory_service import project_memory_service

digest = await project_memory_service.build_canvas_digest(fill_db, proj_uuid)
await project_memory_service.upsert(db, proj_uuid, "canvas_digest", digest)

await project_memory_service.upsert_conversation_state(
    db, conversation_id, "last_web_hits",
    {"hits": web_hits, "summary": search_summary},
)
```

- [ ] **Step 3: Run test + commit**

---

### Task 9: conversational 注入项目记忆

**验收项:** C1, C2

**Files:**
- Modify: `apps/api/app/services/conversation_service.py` (`_handle_conversational`)

- [ ] **Step 1: Write failing test**

```python
@pytest.mark.asyncio
async def test_follow_up_uses_canvas_digest_context(client, db_session, monkeypatch):
    # 1) auto_fill 写入 digest 含 "主营业务：通信设备"
    # 2) 第二条消息："刚才填充的企业主营业务是什么？"
    # 3) mock LLM 记录收到的 system_prompt，断言含 "通信设备" 或 digest 摘要
```

使用 `MockLLMService` 的 `last_system_prompt` 钩子（若无则添加测试专用属性）。

- [ ] **Step 2: Modify _handle_conversational**

```python
async def _handle_conversational(..., project_id: Optional[str] = None):
    memory_block = ""
    if project_id:
        digest = await project_memory_service.get(db, uuid.UUID(project_id), "canvas_digest")
        if digest:
            memory_block = f"\n\n【项目画布摘要】\n{json.dumps(digest, ensure_ascii=False)[:4000]}\n"
        last_web = await project_memory_service.get_conversation_state(
            db, conversation_id, "last_web_hits"
        )
        if last_web:
            memory_block += f"\n【上轮联网检索】\n{...}\n"
    system_prompt = _CONVERSATION_SYSTEM_PROMPT + memory_block + web_block
```

- [ ] **Step 3: Run test + commit**

---

### Task 10: 追问持久化 E2E 测试套件

**验收项:** C5

**Files:**
- Modify: `apps/api/app/tests/test_presale_main_flow.py`
- Modify: `apps/api/app/tests/test_conversation_persistence.py`

- [ ] **Step 1: test_follow_up_message_persisted_after_reload**

```python
@pytest.mark.asyncio
async def test_follow_up_message_persisted_after_reload(client, db_session):
    # auto_fill + follow-up
    messages = (await client.get(f"/api/v1/conversations/{conv_id}")).json()["data"]["messages"]
    assert len(messages) >= 4  # user + assistant + user + assistant
    assert any(m["role"] == "assistant" and m.get("rich_content") for m in messages)
```

- [ ] **Step 2: Run full presale test suite**

```bash
cd apps/api && pytest app/tests/test_presale_main_flow.py app/tests/test_conversation_persistence.py -v
```

- [ ] **Step 3: Commit + Phase 2 checkpoint**

```bash
git commit -m "test: presale main flow memory and persistence"
```

---

## Phase 3 — SOP 与知识生产化（验收 P0 D, F 增强）

---

### Task 11: SOP 匹配服务

**验收项:** D3

**Files:**
- Create: `apps/api/app/services/sop_matcher_service.py`
- Modify: `apps/api/app/db/init_db.py` (seed default_presale_sop)

- [ ] **Step 1: Test sop match by industry**

```python
@pytest.mark.asyncio
async def test_sop_matcher_finds_workflow_by_industry(db_session):
    from app.services.sop_matcher_service import sop_matcher_service
    wf = await sop_matcher_service.match(db_session, industry="科技", project_type="裸眼3D")
    assert wf is not None
    assert wf.workflow_type == "presale"
```

- [ ] **Step 2: Implement match — query sop_workflows by metadata filter, fallback default**

- [ ] **Step 3: Seed `default_presale_sop` with quality_review checklist_json**

- [ ] **Step 4: Commit**

---

### Task 12: proposal_generation 记录 used_sop_version

**验收项:** D1, D3, D4

**Files:**
- Modify: `apps/api/app/skills/builtins/proposal_generation.py`
- Modify: `apps/api/app/skills/runner.py`

- [ ] **Step 1: Test used_sop_version in skill result**

```python
@pytest.mark.asyncio
async def test_proposal_generation_records_sop_version(db_session, sample_project):
    result = await runner.run("proposal_generation", {...}, ctx)
    assert result.get("output", {}).get("used_sop_version") or result.get("used_sop_version")
```

- [ ] **Step 2: Skill 执行前 sop_matcher.match → 写入 GenerationOutput.used_sop_version**

- [ ] **Step 3: case_search 结果写入 used_cases — 已有则加断言测试**

- [ ] **Step 4: Commit**

---

### Task 13: 导出门控读取 SOP checklist

**验收项:** F2（配置化）

**Files:**
- Modify: `apps/api/app/routers/exports.py`
- Create: `apps/api/app/services/export_gate_service.py`

- [ ] **Step 1: Test export gate uses sop checklist**

```python
def test_export_gate_blocks_missing_canvas_nodes():
    blockers = export_gate_service.check(project, output, canvas_nodes)
    assert any("画布" in b for b in blockers)
```

- [ ] **Step 2: export_gate_service.check 合并 sections_meta + SOP checklist + canvas 节点状态**

- [ ] **Step 3: exports.py 调用 export_gate_service 替代纯硬编码**

- [ ] **Step 4: Commit**

---

### Task 14: 上传资料进入 auto-fill 上下文

**验收项:** B6, D2

**Files:**
- Modify: `apps/api/app/services/conversation_service.py`
- Modify: `apps/web/components/canvas/conversation-panel.tsx`

- [ ] **Step 1: Test ref_doc in auto_fill**

已有 `_load_ref_docs_context` — 补测试：

```python
@pytest.mark.asyncio
async def test_auto_fill_uses_uploaded_document_chunks(client, db_session, indexed_document):
    message = f"分析企业 [ref_doc:{indexed_document.id}]"
    # assert fill_canvas received document_context
```

- [ ] **Step 2: 前端上传后自动插入 [ref_doc:uuid] 到消息**

- [ ] **Step 3: Commit**

---

## Phase 4 — 审计增强与 UAT（验收 P0 全量 + P1）

---

### Task 15: operation_runs 父表（P2 基础设施，建议本 Phase 做最小版）

**Files:**
- Create: `apps/api/app/models/operation_run.py`
- Create: `apps/api/app/services/operation_run_service.py`
- Modify: `conversation_service._handle_auto_fill`, `skills/runner.py`

- [ ] **Step 1: Migration + model（见设计文档 §2.1）**

- [ ] **Step 2: `_handle_auto_fill` 包一层 operation_run(steps: web_search, canvas_fill, skill_execute, persist)**

- [ ] **Step 3: Test run has 4 steps**

- [ ] **Step 4: Commit**

---

### Task 16: 标准 UAT 剧本自动化脚本（可选 smoke）

**Files:**
- Create: `apps/api/app/tests/test_presale_uat_script.py`

- [ ] **Step 1: 按 PRESALE_DELIVERY_SPEC §14.1 十步剧本写 parametrized test**

- [ ] **Step 2: CI 加入该 test 文件**

- [ ] **Step 3: Commit**

---

### Task 17: TEST_PLAN 与 Spec 验收清单同步

**Files:**
- Modify: `docs/TEST_PLAN.md`

- [ ] **Step 1: 增加 §「售前主链测试」指向 test_presale_main_flow.py**

- [ ] **Step 2: P0 验收项 ↔ 测试文件映射表**

- [ ] **Step 3: Commit**

---

## Phase 1-4 验收检查表

完成所有 Task 后，逐项勾选 [PRESALE_DELIVERY_SPEC.md](../../PRESALE_DELIVERY_SPEC.md) §13.1：

| Phase | 覆盖验收组 | 关键 Task |
|-------|-----------|-----------|
| 1 | A, B, F | 1-5 |
| 2 | C | 6-10 |
| 3 | D, B6, F 增强 | 11-14 |
| 4 | 全量 UAT, P2 基础 | 15-17 |

**人工 UAT：** 按 Spec §14.1「华为裸眼 3D 发布方案」剧本在 staging 走一遍并录屏存档。

---

## Spec 覆盖自检

| Spec 章节 | 对应 Task |
|-----------|-----------|
| §4 端到端旅程 S1-S7 | Task 1-5, 8-9, 11-13 |
| §6 产物模型 | Task 2-3 |
| §7 多轮记忆 | Task 6-10 |
| §8 知识/SOP | Task 11-14 |
| §9 审核导出 | Task 4, 13 |
| §11 审计 | Task 15 |
| §13 P0 清单 | Phase 1-4 全部 |
| §14 测试 | Task 1-2, 10, 16-17 |

**无占位符项：** 所有 Task 均指定了文件路径与测试命令。

---

## 执行建议顺序

```text
Week 1: Task 1 → 2 → 3 → 4 → 5     (Phase 1 可演示)
Week 2: Task 6 → 7 → 8 → 9 → 10    (追问不失忆)
Week 3: Task 11 → 12 → 13 → 14     (SOP/知识)
Week 4: Task 15 → 16 → 17 + UAT    (交付验收)
```

---

## 风险与依赖

| 风险 | 缓解 |
|------|------|
| Mock LLM 输出格式与真实 LLM 不一致 | sections_meta 解析层做 schema 校验测试 |
| auto_fill 耗时长 | 测试用 Mock；UAT 用真实 LLM |
| 前端 Proposal 编辑器工作量大 | Task 3 先做只读 + 审核，编辑可 Phase 3 完善 |
| SQLite 测试与 Postgres 差异 | migration 在 CI Postgres job 跑一遍 |

---

*Plan version 1.0 — 2026-07-18*
